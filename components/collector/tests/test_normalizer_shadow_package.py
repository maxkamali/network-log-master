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

from network_log_normalizer.shadow import load_inventory, process_source_file


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


if __name__ == "__main__":
    unittest.main()
