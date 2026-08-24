from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import textwrap

import pytest

from network_log_normalizer.handoff import (
    HANDOFF_FILE_COLUMNS,
    HandoffError,
    connect_handoff_ledger,
    load_handoff_plan,
    publish_handoff,
    verify_handoff,
)
from network_log_normalizer.shadow import (
    load_inventory,
    output_relative_path,
    process_source_file,
)


ROOT = Path(__file__).resolve().parents[3]


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


def write_plan(path: Path, first_path: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "first_normalized_source_path": first_path,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)


def load_gx10_fetcher():
    fake_config = type(sys)("runtime_config")
    fake_config.load_runtime_config = lambda: type(
        "RuntimeConfig",
        (),
        {
            "database_path": Path("/var/lib/network-log-gx10/state/events.sqlite3"),
            "incoming_dir": Path("/var/spool/network-log-gx10/incoming"),
            "processed_dir": Path("/var/spool/network-log-gx10/processed"),
            "temp_dir": Path("/var/spool/network-log-gx10/tmp"),
            "private_key_path": Path(
                "/var/lib/network-log-gx10/.ssh/spool-reader.key"
            ),
            "known_hosts_path": Path(
                "/var/lib/network-log-gx10/.ssh/known_hosts"
            ),
            "sftp_host": "collector.example.invalid",
            "sftp_port": "2222",
            "sftp_user": "spool-reader",
        },
    )()
    previous = sys.modules.get("runtime_config")
    sys.modules["runtime_config"] = fake_config
    try:
        path = ROOT / "components/gx10/sbin/fetch-spool.py"
        spec = importlib.util.spec_from_file_location("handoff_gx10_fetch", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            del sys.modules["runtime_config"]
        else:
            sys.modules["runtime_config"] = previous


@pytest.fixture
def handoff_environment(tmp_path: Path) -> dict[str, object]:
    source_root = tmp_path / "source"
    shadow_root = tmp_path / "shadow"
    handoff_root = tmp_path / "handoff"
    state_root = tmp_path / "state"
    for path in (source_root, shadow_root, handoff_root, state_root):
        path.mkdir()
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "platforms": {}}),
        encoding="utf-8",
    )
    inventory_path.chmod(0o600)
    zstd = tmp_path / "zstd"
    make_fake_zstd(zstd)
    source_paths = []
    for minute in (33, 34, 35):
        relative = Path(
            f"2026/08/23/12/syslog-20260823-12{minute}.jsonl.zst"
        )
        source = source_root / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            json.dumps(
                {
                    "timestamp": f"2026-08-23T12:{minute}:00Z",
                    "source_ip": "192.0.2.10",
                    "message": f"synthetic minute {minute}",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        source_paths.append(relative)
    inventory = load_inventory(inventory_path, secure=False)
    shadow_ledger = state_root / "shadow.sqlite3"
    for relative in source_paths:
        process_source_file(
            source_root / relative,
            source_root=source_root,
            output_root=shadow_root,
            ledger_path=shadow_ledger,
            inventory=inventory,
            zstd_path=zstd,
        )
    plan_path = tmp_path / "handoff-plan.json"
    write_plan(plan_path, source_paths[1].as_posix())
    return {
        "source_paths": source_paths,
        "shadow_root": shadow_root,
        "handoff_root": handoff_root,
        "shadow_ledger": shadow_ledger,
        "handoff_ledger": state_root / "handoff.sqlite3",
        "plan_path": plan_path,
        "zstd": zstd,
    }


def handoff_arguments(environment: dict[str, object]) -> dict[str, object]:
    plan_path = environment["plan_path"]
    assert isinstance(plan_path, Path)
    return {
        "plan": load_handoff_plan(plan_path, secure=False),
        "shadow_ledger_path": environment["shadow_ledger"],
        "handoff_ledger_path": environment["handoff_ledger"],
        "shadow_output_root": environment["shadow_root"],
        "handoff_root": environment["handoff_root"],
        "zstd_path": environment["zstd"],
    }


def test_plan_rejects_duplicate_and_ineligible_paths(tmp_path: Path):
    plan = tmp_path / "plan.json"
    plan.write_text(
        '{"schema_version":1,"schema_version":1,'
        '"first_normalized_source_path":"invalid"}',
        encoding="utf-8",
    )
    with pytest.raises(HandoffError, match="duplicate JSON key"):
        load_handoff_plan(plan, secure=False)
    write_plan(plan, "invalid")
    with pytest.raises(HandoffError, match="ineligible source path"):
        load_handoff_plan(plan, secure=False)


def test_forward_only_publication_is_bounded_atomic_and_exact(
    handoff_environment: dict[str, object],
):
    arguments = handoff_arguments(handoff_environment)
    source_paths = handoff_environment["source_paths"]
    shadow_root = handoff_environment["shadow_root"]
    handoff_root = handoff_environment["handoff_root"]
    assert isinstance(source_paths, list)
    assert isinstance(shadow_root, Path)
    assert isinstance(handoff_root, Path)

    first = publish_handoff(**arguments, max_files=1)
    assert first == {
        "selected_files": 1,
        "published_files": 1,
        "adopted_files": 0,
        "published_records": 1,
        "pending_files": 1,
    }
    second = publish_handoff(**arguments, max_files=1)
    assert second["published_files"] == 1
    assert second["pending_files"] == 0
    assert publish_handoff(**arguments, max_files=1)["selected_files"] == 0

    assert not (handoff_root / source_paths[0]).exists()
    for relative in source_paths[1:]:
        handoff = handoff_root / relative
        shadow = shadow_root / output_relative_path(relative)
        assert handoff.exists()
        assert handoff.name.endswith(".jsonl.zst")
        assert ".normalized." not in handoff.name
        assert handoff.read_bytes() == shadow.read_bytes()
        assert handoff.stat().st_ino != shadow.stat().st_ino
        assert handoff.stat().st_nlink == shadow.stat().st_nlink == 1

    assert verify_handoff(**arguments) == {
        "verified_files": 2,
        "verified_records": 2,
        "missing_files": 0,
        "orphan_files": 0,
    }


def test_exact_preexisting_copy_is_adopted_after_interruption(
    handoff_environment: dict[str, object],
):
    arguments = handoff_arguments(handoff_environment)
    source_paths = handoff_environment["source_paths"]
    shadow_root = handoff_environment["shadow_root"]
    handoff_root = handoff_environment["handoff_root"]
    assert isinstance(source_paths, list)
    assert isinstance(shadow_root, Path)
    assert isinstance(handoff_root, Path)
    relative = source_paths[1]
    target = handoff_root / relative
    target.parent.mkdir(parents=True)
    shutil.copyfile(shadow_root / output_relative_path(relative), target)
    target.chmod(0o640)

    result = publish_handoff(**arguments, max_files=1)
    assert result["adopted_files"] == 1
    assert result["published_files"] == 0


def test_initialized_plan_and_published_bytes_are_immutable(
    handoff_environment: dict[str, object],
):
    arguments = handoff_arguments(handoff_environment)
    publish_handoff(**arguments, max_files=2)
    source_paths = handoff_environment["source_paths"]
    handoff_root = handoff_environment["handoff_root"]
    plan_path = handoff_environment["plan_path"]
    assert isinstance(source_paths, list)
    assert isinstance(handoff_root, Path)
    assert isinstance(plan_path, Path)

    target = handoff_root / source_paths[1]
    target.write_bytes(b"mutated")
    with pytest.raises(HandoffError, match="handoff file differs"):
        verify_handoff(**arguments)

    write_plan(plan_path, source_paths[2].as_posix())
    changed = dict(arguments)
    changed["plan"] = load_handoff_plan(plan_path, secure=False)
    with pytest.raises(HandoffError, match="plan differs"):
        publish_handoff(**changed, max_files=1)


def test_handoff_ledger_has_exact_schema(
    handoff_environment: dict[str, object],
):
    arguments = handoff_arguments(handoff_environment)
    ledger_path = arguments["handoff_ledger_path"]
    assert isinstance(ledger_path, Path)
    with connect_handoff_ledger(ledger_path, arguments["plan"]) as connection:
        columns = tuple(
            row[1]
            for row in connection.execute("PRAGMA table_info(handoff_files)")
        )
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert columns == HANDOFF_FILE_COLUMNS
    assert names == {"handoff_state", "handoff_files"}
    assert ledger_path.stat().st_mode & 0o777 == 0o640


def test_gx10_identity_rehearsal_prevents_history_replay_and_rollback_duplicates(
    handoff_environment: dict[str, object],
):
    arguments = handoff_arguments(handoff_environment)
    publish_handoff(**arguments, max_files=10)
    source_paths = handoff_environment["source_paths"]
    handoff_root = handoff_environment["handoff_root"]
    assert isinstance(source_paths, list)
    assert isinstance(handoff_root, Path)
    fetcher = load_gx10_fetcher()

    exposed = sorted(
        path.relative_to(handoff_root)
        for path in handoff_root.rglob("*.jsonl.zst")
    )
    assert exposed == source_paths[1:]
    assert all(fetcher.FILE_RE.fullmatch(path.name) for path in exposed)
    assert not fetcher.FILE_RE.fullmatch(
        output_relative_path(source_paths[1]).name
    )

    database = sqlite3.connect(":memory:")
    database.executescript(
        """
        CREATE TABLE source_files (
            remote_path TEXT PRIMARY KEY,
            status TEXT NOT NULL
        );
        CREATE TABLE recent_events (
            source_file TEXT NOT NULL,
            record_number INTEGER NOT NULL,
            UNIQUE(source_file, record_number)
        );
        """
    )
    before_remote = "/spool/" + source_paths[0].as_posix()
    database.execute(
        "INSERT INTO source_files VALUES (?, 'processed')",
        (before_remote,),
    )
    database.execute(
        "INSERT INTO recent_events VALUES (?, 1)",
        (before_remote,),
    )
    for relative in exposed:
        remote = "/spool/" + relative.as_posix()
        database.execute(
            "INSERT OR IGNORE INTO source_files VALUES (?, 'processed')",
            (remote,),
        )
        database.execute(
            "INSERT OR IGNORE INTO recent_events VALUES (?, 1)",
            (remote,),
        )
    assert database.execute("SELECT COUNT(*) FROM recent_events").fetchone() == (
        3,
    )

    for relative in source_paths[1:]:
        raw_rollback_remote = "/spool/" + relative.as_posix()
        database.execute(
            "INSERT OR IGNORE INTO source_files VALUES (?, 'processed')",
            (raw_rollback_remote,),
        )
        database.execute(
            "INSERT OR IGNORE INTO recent_events VALUES (?, 1)",
            (raw_rollback_remote,),
        )
    assert database.execute("SELECT COUNT(*) FROM recent_events").fetchone() == (
        3,
    )
