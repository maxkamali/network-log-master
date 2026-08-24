#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import textwrap
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
NORMALIZER_SOURCE = ROOT / "components/normalizer/src"
sys.path.insert(0, str(NORMALIZER_SOURCE))


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PACKAGE_DIR = ROOT / "components/collector/normalizer"
INSTALLER = load_script("normalizer_shadow_installer", PACKAGE_DIR / "install-shadow.py")
VERIFIER = load_script("normalizer_shadow_verifier", PACKAGE_DIR / "verify-shadow.py")
HANDOFF_INSTALLER = load_script(
    "normalizer_handoff_installer",
    PACKAGE_DIR / "install-handoff.py",
)
HANDOFF_VERIFIER = load_script(
    "normalizer_handoff_verifier",
    PACKAGE_DIR / "verify-handoff.py",
)

from network_log_normalizer.shadow import load_inventory, process_source_file
from network_log_normalizer.handoff import load_handoff_plan


def make_fake_zstd(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import pathlib
            import sys
            source = pathlib.Path(sys.argv[-1])
            if "-t" in sys.argv:
                source.read_bytes()
            elif "-dc" in sys.argv or "-c" in sys.argv:
                sys.stdout.buffer.write(source.read_bytes())
            else:
                raise SystemExit(2)
            """
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


class NormalizerShadowPackageTests(unittest.TestCase):
    def test_manifest_inventory_and_repository_hashes_are_exact(self):
        manifest = INSTALLER.load_manifest()
        self.assertEqual(
            {str(path) for path in manifest},
            VERIFIER.EXPECTED_TARGETS,
        )
        INSTALLER.validate_repository_artifacts(manifest)

    def test_manifest_contains_only_expected_runtime_targets(self):
        data = json.loads(
            (PACKAGE_DIR / "package-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(set(data["artifacts"]), VERIFIER.EXPECTED_TARGETS)
        self.assertNotIn(str(INSTALLER.MANIFEST_PATH), data["artifacts"])

    def test_installer_is_no_overwrite_and_reusable_for_identical_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            target = root / "target"
            source.write_text("expected", encoding="utf-8")
            INSTALLER.install_or_verify_file(
                source,
                target,
                mode=0o640,
                uid=os.getuid(),
                gid=os.getgid(),
            )
            self.assertEqual(target.read_text(encoding="utf-8"), "expected")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
            self.assertEqual(target.stat().st_nlink, 1)
            INSTALLER.install_or_verify_file(
                source,
                target,
                mode=0o640,
                uid=os.getuid(),
                gid=os.getgid(),
            )
            target.write_text("diverged", encoding="utf-8")
            with self.assertRaisesRegex(INSTALLER.InstallError, "differs"):
                INSTALLER.install_or_verify_file(
                    source,
                    target,
                    mode=0o640,
                    uid=os.getuid(),
                    gid=os.getgid(),
                )

    def test_private_inventory_input_requires_strict_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            path.write_text("{}", encoding="utf-8")
            path.chmod(0o644)
            with self.assertRaisesRegex(INSTALLER.InstallError, "0400 or 0600"):
                INSTALLER.validate_private_inventory_input(path)
            path.chmod(0o600)
            INSTALLER.validate_private_inventory_input(path)

    def test_service_is_shadow_only_hardened_and_source_read_only(self):
        service = (
            PACKAGE_DIR / "systemd/network-log-normalizer-shadow.service"
        ).read_text(encoding="utf-8")
        required = (
            "Type=oneshot",
            "User=network-log-normalizer",
            "SupplementaryGroups=vector",
            "PrivateNetwork=yes",
            "ProtectSystem=strict",
            "NoNewPrivileges=yes",
            "CapabilityBoundingSet=",
            "RestrictAddressFamilies=AF_UNIX",
            "IPAddressDeny=any",
            "ReadOnlyPaths=/var/spool/vector-ai",
            "ReadWritePaths=/var/spool/network-log-normalizer-shadow",
            "ReadWritePaths=/var/lib/network-log-normalizer",
        )
        for value in required:
            self.assertIn(value, service)
        self.assertNotIn("WantedBy=", service)
        self.assertNotIn("Wants=vector.service", service)
        self.assertNotIn("/var/lib/clickhouse", service)
        self.assertNotIn("/var/spool/ai-results", service)

    def test_timer_is_not_enabled_by_staging_installer(self):
        installer = (PACKAGE_DIR / "install-shadow.py").read_text(encoding="utf-8")
        timer = (
            PACKAGE_DIR / "systemd/network-log-normalizer-shadow.timer"
        ).read_text(encoding="utf-8")
        self.assertIn("OnUnitInactiveSec=1min", timer)
        self.assertNotIn("Persistent=true", timer)
        self.assertNotIn("systemctl\", \"enable", installer)
        self.assertNotIn("systemctl\", \"start", installer)
        self.assertIn("require_timer_inactive_disabled()", installer)

    def test_handoff_assets_are_guarded_repository_only_candidates(self):
        service = (
            PACKAGE_DIR
            / "systemd/network-log-normalizer-handoff.service"
        ).read_text(encoding="utf-8")
        timer = (
            PACKAGE_DIR
            / "systemd/network-log-normalizer-handoff.timer"
        ).read_text(encoding="utf-8")
        required = (
            "Type=oneshot",
            "User=network-log-normalizer",
            "After=network-log-normalizer-shadow.service",
            "ConditionPathExists=/etc/network-log-normalizer/handoff-plan.json",
            "PrivateNetwork=yes",
            "NoNewPrivileges=yes",
            "CapabilityBoundingSet=",
            "RestrictAddressFamilies=AF_UNIX",
            "IPAddressDeny=any",
            "ReadOnlyPaths=/var/spool/network-log-normalizer-shadow",
            "ReadOnlyPaths=/var/lib/network-log-normalizer/state.sqlite3",
            "ReadOnlyPaths=/etc/network-log-normalizer/handoff-plan.json",
            "InaccessiblePaths=/var/spool/vector-ai",
            "InaccessiblePaths=/var/lib/clickhouse",
            "InaccessiblePaths=/var/spool/ai-results",
            "ReadWritePaths=/var/spool/network-log-normalizer-handoff",
        )
        for value in required:
            self.assertIn(value, service)
        self.assertNotIn("SupplementaryGroups=vector", service)
        self.assertNotIn("Wants=vector.service", service)
        self.assertIn("OnUnitInactiveSec=1min", timer)
        self.assertNotIn("Persistent=true", timer)

        plan = load_handoff_plan(
            PACKAGE_DIR / "handoff-plan.example.json",
            secure=False,
        )
        self.assertEqual(
            plan.first_normalized_source_path,
            "2026/08/23/12/syslog-20260823-1234.jsonl.zst",
        )

        manifest = INSTALLER.load_manifest()
        self.assertNotIn(
            Path(
                "/usr/local/lib/network-log-normalizer/"
                "network_log_normalizer/handoff.py"
            ),
            manifest,
        )
        self.assertNotIn(
            Path("/usr/local/sbin/network-log-normalizer-handoff"),
            manifest,
        )

    def test_handoff_package_manifest_and_hashes_are_exact(self):
        manifest = HANDOFF_INSTALLER.load_manifest()
        self.assertEqual(set(manifest), HANDOFF_INSTALLER.EXPECTED_TARGETS)
        self.assertEqual(
            {str(path) for path in manifest},
            HANDOFF_VERIFIER.EXPECTED_TARGETS,
        )
        HANDOFF_INSTALLER.validate_repository_artifacts(manifest)
        for target, expected in manifest.items():
            source = HANDOFF_INSTALLER.source_for_target(target)
            self.assertEqual(HANDOFF_INSTALLER.sha256_file(source), expected)

    def test_handoff_installer_is_nonactivating_and_future_bounded(self):
        installer = (
            PACKAGE_DIR / "install-handoff.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"systemctl", "enable"', installer)
        self.assertNotIn('"systemctl", "start"', installer)
        self.assertIn("require_handoff_timer_inactive_disabled()", installer)
        self.assertEqual(
            HANDOFF_INSTALLER.plan_floor_datetime(
                "2026/08/23/12/syslog-20260823-1234.jsonl.zst"
            ).isoformat(),
            "2026-08-23T12:34:00+00:00",
        )
        with self.assertRaisesRegex(
            HANDOFF_INSTALLER.InstallError,
            "path/time differs",
        ):
            HANDOFF_INSTALLER.plan_floor_datetime(
                "2026/08/23/13/syslog-20260823-1234.jsonl.zst"
            )

    def test_handoff_verifier_requires_stable_modes_and_exact_acl(self):
        verifier = (
            PACKAGE_DIR / "verify-handoff.py"
        ).read_text(encoding="utf-8")
        for mode in ("staged", "prepared", "cutover"):
            self.assertIn(f'"{mode}"', verifier)
        self.assertIn("service must be inactive", verifier)
        self.assertIn("handoff root ACL differs", verifier)
        self.assertIn("GX10 SFTP bind source differs", verifier)
        self.assertIn("NORMALIZER_HANDOFF_RUNTIME_VERIFY=PASS", verifier)
        self.assertEqual(
            HANDOFF_VERIFIER.EXPECTED_HANDOFF_ACL.count(
                "group:ai_spool_readers:r-x"
            ),
            2,
        )

    def test_collector_package_versions_pin_reference_dependencies(self):
        values = {}
        for line in (
            ROOT / "components/collector/install/versions.env"
        ).read_text(encoding="utf-8").splitlines():
            key, value = line.split("=", 1)
            values[key] = value
        self.assertEqual(values["PYTHON3_VERSION"], "3.13.5-1")
        self.assertEqual(values["ZSTD_VERSION"], "1.5.7+dfsg-1")
        verifier = (
            ROOT / "components/collector/install/verify-packages.sh"
        ).read_text(encoding="utf-8")
        self.assertRegex(verifier, r'python3 \\\s+"\$PYTHON3_VERSION"')
        self.assertRegex(verifier, r'zstd \\\s+"\$ZSTD_VERSION"')

    def test_staging_installer_refuses_dependency_version_drift(self):
        expected = {
            "python3": "3.13.5-1",
            "zstd": "1.5.7+dfsg-1",
        }
        with mock.patch.object(
            INSTALLER,
            "installed_package_version",
            side_effect=lambda package: expected[package],
        ), mock.patch.object(INSTALLER.os, "access", return_value=True), \
                mock.patch.object(Path, "exists", return_value=True):
            INSTALLER.verify_dependency_versions()
        with mock.patch.object(
            INSTALLER,
            "installed_package_version",
            return_value="unexpected",
        ):
            with self.assertRaisesRegex(INSTALLER.InstallError, "expected="):
                INSTALLER.verify_dependency_versions()

    def test_independent_verifier_checks_completed_output_and_cardinality(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            output_root = root / "output"
            state_root = root / "state"
            source_root.mkdir()
            output_root.mkdir()
            state_root.mkdir()
            inventory_path = root / "inventory.json"
            inventory_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "platforms": {
                            "192.0.2.10": {
                                "vendor_hint": "cisco",
                                "os_family_hint": "nxos",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            inventory_path.chmod(0o600)
            inventory = load_inventory(inventory_path, secure=False)
            source = (
                source_root
                / "2026/08/23/12/syslog-20260823-1234.jsonl.zst"
            )
            source.parent.mkdir(parents=True)
            source.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-08-23T12:34:00Z",
                        "source_ip": "192.0.2.10",
                        "message": "%ETHPORT-5-IF_UP: Interface Ethernet1/1 is up",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            zstd = root / "zstd"
            make_fake_zstd(zstd)
            ledger = state_root / "state.sqlite3"
            process_source_file(
                source,
                source_root=source_root,
                output_root=output_root,
                ledger_path=ledger,
                inventory=inventory,
                zstd_path=zstd,
            )
            with mock.patch.object(VERIFIER, "OUTPUT_ROOT", output_root), \
                    mock.patch.object(VERIFIER, "LEDGER_PATH", ledger), \
                    mock.patch.object(VERIFIER, "ZSTD_PATH", zstd):
                totals = VERIFIER.verify_ledger_and_outputs(
                    os.getuid(),
                    os.getgid(),
                )
                self.assertEqual(totals, {"completed_files": 1, "records": 1})
                output = next(
                    output_root.rglob("*.normalized.jsonl.zst")
                )
                output.write_bytes(b"mutated")
                with self.assertRaisesRegex(
                    VERIFIER.VerifyError,
                    "size differs|hash differs",
                ):
                    VERIFIER.verify_ledger_and_outputs(
                        os.getuid(),
                        os.getgid(),
                    )

    def test_active_verifier_resnapshots_concurrent_completed_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            output_root = root / "output"
            state_root = root / "state"
            source_root.mkdir()
            output_root.mkdir()
            state_root.mkdir()
            inventory_path = root / "inventory.json"
            inventory_path.write_text(
                json.dumps({"schema_version": 1, "platforms": {}}),
                encoding="utf-8",
            )
            inventory_path.chmod(0o600)
            inventory = load_inventory(inventory_path, secure=False)
            zstd = root / "zstd"
            make_fake_zstd(zstd)
            ledger = state_root / "state.sqlite3"

            def source(minute: int) -> Path:
                path = (
                    source_root
                    / f"2026/08/23/12/syslog-20260823-12{minute:02d}.jsonl.zst"
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(
                        {
                            "timestamp": f"2026-08-23T12:{minute:02d}:00Z",
                            "source_ip": "192.0.2.10",
                            "message": "generic observation",
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return path

            first = source(1)
            second = source(2)
            process_source_file(
                first,
                source_root=source_root,
                output_root=output_root,
                ledger_path=ledger,
                inventory=inventory,
                zstd_path=zstd,
            )

            original_count = VERIFIER.count_output_records
            appended = False

            def count_and_append(path):
                nonlocal appended
                count = original_count(path)
                if not appended:
                    appended = True
                    process_source_file(
                        second,
                        source_root=source_root,
                        output_root=output_root,
                        ledger_path=ledger,
                        inventory=inventory,
                        zstd_path=zstd,
                    )
                return count

            with mock.patch.object(VERIFIER, "OUTPUT_ROOT", output_root), \
                    mock.patch.object(VERIFIER, "LEDGER_PATH", ledger), \
                    mock.patch.object(VERIFIER, "ZSTD_PATH", zstd), \
                    mock.patch.object(
                        VERIFIER,
                        "count_output_records",
                        side_effect=count_and_append,
                    ):
                totals = VERIFIER.verify_ledger_and_outputs(
                    os.getuid(),
                    os.getgid(),
                    allow_concurrent=True,
                )

            self.assertTrue(appended)
            self.assertEqual(totals, {"completed_files": 2, "records": 2})


if __name__ == "__main__":
    unittest.main()
