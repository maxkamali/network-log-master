from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import stat
import textwrap
import time

import pytest

from network_log_normalizer.shadow import (
    ShadowError,
    completed_cursor,
    connect_ledger,
    eligible_source_files,
    ledger_totals,
    load_inventory,
    output_relative_path,
    process_source_file,
    verify_outputs,
)


def write_inventory(path: Path, platforms: dict | None = None) -> None:
    if platforms is None:
        platforms = {
            "192.0.2.10": {
                "vendor_hint": "cisco",
                "os_family_hint": "nxos",
            }
        }
    path.write_text(
        json.dumps(
            {"schema_version": 1, "platforms": platforms},
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)


def make_fake_zstd(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import pathlib
            import sys

            arguments = sys.argv[1:]
            source = pathlib.Path(arguments[-1])
            if "-t" in arguments:
                source.read_bytes()
                raise SystemExit(0)
            if "-dc" in arguments:
                sys.stdout.buffer.write(source.read_bytes())
                raise SystemExit(0)
            if "-c" in arguments:
                sys.stdout.buffer.write(source.read_bytes())
                raise SystemExit(0)
            raise SystemExit(2)
            """
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def write_source(root: Path, records: list[object]) -> Path:
    path = root / "2026/08/23/12/syslog-20260823-1234.jsonl.zst"
    path.parent.mkdir(parents=True)
    path.write_text(
        "".join(
            json.dumps(record, sort_keys=True) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    old = time.time() - 180
    os.utime(path, (old, old))
    return path


@pytest.fixture
def shadow_environment(tmp_path: Path) -> dict[str, object]:
    source_root = tmp_path / "source"
    output_root = tmp_path / "output"
    state_root = tmp_path / "state"
    source_root.mkdir()
    output_root.mkdir()
    state_root.mkdir()
    inventory_path = tmp_path / "inventory.json"
    write_inventory(inventory_path)
    zstd = tmp_path / "zstd"
    make_fake_zstd(zstd)
    return {
        "source_root": source_root,
        "output_root": output_root,
        "ledger_path": state_root / "state.sqlite3",
        "inventory_path": inventory_path,
        "inventory": load_inventory(inventory_path, secure=False),
        "zstd": zstd,
    }


def test_inventory_accepts_canonical_supported_entries(tmp_path: Path):
    path = tmp_path / "inventory.json"
    write_inventory(
        path,
        {
            "192.0.2.20": {
                "vendor_hint": "arista",
                "os_family_hint": "eos",
            },
            "2001:db8::20": {
                "vendor_hint": "cisco",
                "os_family_hint": "iosxr",
            },
        },
    )
    inventory = load_inventory(path, secure=False)
    assert inventory.platforms["192.0.2.20"] == ("arista", "eos")
    assert inventory.platforms["2001:db8::20"] == ("cisco", "iosxr")
    assert len(inventory.sha256) == 64


def test_inventory_rejects_duplicate_keys(tmp_path: Path):
    path = tmp_path / "inventory.json"
    path.write_text(
        '{"schema_version":1,"schema_version":1,"platforms":{}}',
        encoding="utf-8",
    )
    with pytest.raises(ShadowError, match="duplicate JSON key"):
        load_inventory(path, secure=False)


@pytest.mark.parametrize(
    "platforms, message",
    [
        (
            {
                "192.0.2.1": {
                    "vendor_hint": "future",
                    "os_family_hint": "futureos",
                }
            },
            "unsupported vendor/OS pair",
        ),
        (
            {
                "2001:0db8::1": {
                    "vendor_hint": "cisco",
                    "os_family_hint": "nxos",
                }
            },
            "not canonical",
        ),
    ],
)
def test_inventory_rejects_invalid_entries(
    tmp_path: Path,
    platforms: dict,
    message: str,
):
    path = tmp_path / "inventory.json"
    write_inventory(path, platforms)
    with pytest.raises(ShadowError, match=message):
        load_inventory(path, secure=False)


def test_secure_inventory_requires_root_runtime_metadata(tmp_path: Path):
    path = tmp_path / "inventory.json"
    write_inventory(path)
    with pytest.raises(ShadowError, match="owned by root|mode must be 0640"):
        load_inventory(path, secure=True)


def test_source_eligibility_requires_exact_path_and_settle_time(tmp_path: Path):
    root = tmp_path / "source"
    root.mkdir()
    eligible = write_source(root, [{"message": "eligible"}])
    recent = root / "2026/08/23/12/syslog-20260823-1235.jsonl.zst"
    recent.write_text('{}\n', encoding="utf-8")
    invalid = root / "other.jsonl.zst"
    invalid.write_text('{}\n', encoding="utf-8")
    assert eligible_source_files(root) == [eligible]
    with pytest.raises(ShadowError, match="at least 120"):
        eligible_source_files(root, settle_seconds=119)


def test_eligible_path_symlink_fails_instead_of_disappearing(tmp_path: Path):
    root = tmp_path / "source"
    root.mkdir()
    target = tmp_path / "outside"
    target.write_text('{}\n', encoding="utf-8")
    candidate = root / "2026/08/23/12/syslog-20260823-1234.jsonl.zst"
    candidate.parent.mkdir(parents=True)
    candidate.symlink_to(target)
    with pytest.raises(ShadowError, match="nonsymlink"):
        eligible_source_files(root)


def test_output_path_mirrors_partition_and_marks_normalized():
    assert output_relative_path(
        Path("2026/08/23/12/syslog-20260823-1234.jsonl.zst")
    ) == Path(
        "2026/08/23/12/syslog-20260823-1234.normalized.jsonl.zst"
    )


def test_process_is_cardinality_preserving_enriched_and_idempotent(
    shadow_environment: dict[str, object],
):
    source_root = shadow_environment["source_root"]
    assert isinstance(source_root, Path)
    source = write_source(
        source_root,
        [
            {
                "timestamp": "2026-08-23T12:34:00Z",
                "ingest_timestamp": "2026-08-23T12:34:00Z",
                "source_ip": "192.0.2.10",
                "hostname": "switch-example",
                "message": (
                    "%ETHPORT-5-IF_DOWN_LINK_FAILURE: "
                    "Interface Ethernet1/10 is down (Link failure)"
                ),
            },
            {
                "timestamp": "2026-08-23T12:34:01Z",
                "source_ip": "192.0.2.99",
                "message": "%FUTURE-3-EVENT: retained",
            },
        ],
    )
    source_before = source.read_bytes()
    arguments = {
        key: shadow_environment[key]
        for key in (
            "source_root",
            "output_root",
            "ledger_path",
            "inventory",
            "zstd",
        )
    }
    arguments["zstd_path"] = arguments.pop("zstd")
    assert process_source_file(source, **arguments) == "completed"
    assert source.read_bytes() == source_before
    assert process_source_file(source, **arguments) == "skipped"

    output_root = shadow_environment["output_root"]
    assert isinstance(output_root, Path)
    output = output_root / output_relative_path(source.relative_to(source_root))
    records = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2
    assert records[0]["vendor"] == "cisco"
    assert records[0]["os_family"] == "nxos"
    assert records[0]["attributes"]["normalization_path"] == "parser"
    assert records[1]["vendor"] == "unknown"
    assert records[1]["attention_eligible"] is True

    ledger_path = shadow_environment["ledger_path"]
    assert isinstance(ledger_path, Path)
    with sqlite3.connect(ledger_path) as connection:
        row = connection.execute(
            "SELECT status, input_records, output_records, generic_records, "
            "enriched_records, inventory_hits, inventory_misses "
            "FROM shadow_files"
        ).fetchone()
    assert row == ("completed", 2, 2, 1, 1, 1, 1)
    totals = ledger_totals(ledger_path)
    assert totals["ledger_completed_files"] == 1
    assert totals["ledger_processing_files"] == 0
    assert totals["ledger_input_records"] == 2
    assert totals["ledger_output_records"] == 2
    assert totals["ledger_inventory_hits"] == 1
    assert totals["ledger_inventory_misses"] == 1


def test_completed_cursor_advances_bounded_backlog_scan(
    shadow_environment: dict[str, object],
):
    source_root = shadow_environment["source_root"]
    assert isinstance(source_root, Path)
    first = write_source(source_root, [{"message": "first"}])
    process_source_file(
        first,
        source_root=source_root,
        output_root=shadow_environment["output_root"],
        ledger_path=shadow_environment["ledger_path"],
        inventory=shadow_environment["inventory"],
        zstd_path=shadow_environment["zstd"],
    )
    second = first.with_name("syslog-20260823-1235.jsonl.zst")
    second.write_text('{"message":"second"}\n', encoding="utf-8")
    old = time.time() - 180
    os.utime(second, (old, old))
    cursor = completed_cursor(shadow_environment["ledger_path"])
    assert cursor == first.relative_to(source_root).as_posix()
    assert eligible_source_files(source_root, after_path=cursor) == [second]


def test_untrusted_record_hints_are_removed_on_inventory_miss(
    shadow_environment: dict[str, object],
):
    source_root = shadow_environment["source_root"]
    assert isinstance(source_root, Path)
    source = write_source(
        source_root,
        [
            {
                "source_ip": "192.0.2.99",
                "vendor_hint": "cisco",
                "os_family_hint": "nxos",
                "message": "%ETHPORT-5-IF_UP: Interface Ethernet1/1 is up",
            }
        ],
    )
    process_source_file(
        source,
        source_root=source_root,
        output_root=shadow_environment["output_root"],
        ledger_path=shadow_environment["ledger_path"],
        inventory=shadow_environment["inventory"],
        zstd_path=shadow_environment["zstd"],
    )
    output_root = shadow_environment["output_root"]
    assert isinstance(output_root, Path)
    output = output_root / output_relative_path(source.relative_to(source_root))
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["vendor"] == "unknown"
    assert record["attributes"].get("vendor_hint") is None


def test_previously_completed_source_mutation_is_refused(
    shadow_environment: dict[str, object],
):
    source_root = shadow_environment["source_root"]
    assert isinstance(source_root, Path)
    source = write_source(source_root, [{"message": "first"}])
    process_source_file(
        source,
        source_root=source_root,
        output_root=shadow_environment["output_root"],
        ledger_path=shadow_environment["ledger_path"],
        inventory=shadow_environment["inventory"],
        zstd_path=shadow_environment["zstd"],
    )
    source.write_text('{"message":"changed"}\n', encoding="utf-8")
    with pytest.raises(ShadowError, match="source path changed"):
        process_source_file(
            source,
            source_root=source_root,
            output_root=shadow_environment["output_root"],
            ledger_path=shadow_environment["ledger_path"],
            inventory=shadow_environment["inventory"],
            zstd_path=shadow_environment["zstd"],
        )


def test_malformed_json_never_publishes_success(
    shadow_environment: dict[str, object],
):
    source_root = shadow_environment["source_root"]
    assert isinstance(source_root, Path)
    source = write_source(source_root, [])
    source.write_text('{not-json}\n', encoding="utf-8")
    with pytest.raises(ShadowError, match="invalid JSONL"):
        process_source_file(
            source,
            source_root=source_root,
            output_root=shadow_environment["output_root"],
            ledger_path=shadow_environment["ledger_path"],
            inventory=shadow_environment["inventory"],
            zstd_path=shadow_environment["zstd"],
        )
    output_root = shadow_environment["output_root"]
    assert isinstance(output_root, Path)
    output = output_root / output_relative_path(source.relative_to(source_root))
    assert not output.exists()
    ledger_path = shadow_environment["ledger_path"]
    assert isinstance(ledger_path, Path)
    with sqlite3.connect(ledger_path) as connection:
        assert connection.execute(
            "SELECT status FROM shadow_files"
        ).fetchone() == ("processing",)


def test_completed_output_mutation_is_refused(
    shadow_environment: dict[str, object],
):
    source_root = shadow_environment["source_root"]
    output_root = shadow_environment["output_root"]
    assert isinstance(source_root, Path)
    assert isinstance(output_root, Path)
    source = write_source(source_root, [{"message": "retained"}])
    process_source_file(
        source,
        source_root=source_root,
        output_root=output_root,
        ledger_path=shadow_environment["ledger_path"],
        inventory=shadow_environment["inventory"],
        zstd_path=shadow_environment["zstd"],
    )
    output = output_root / output_relative_path(source.relative_to(source_root))
    output.write_bytes(b"changed")
    with pytest.raises(ShadowError, match="differs from ledger"):
        verify_outputs(
            shadow_environment["ledger_path"],
            output_root,
            shadow_environment["zstd"],
        )


def test_ledger_has_exact_versioned_schema(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    ledger = state / "state.sqlite3"
    with connect_ledger(ledger) as connection:
        assert connection.execute("PRAGMA quick_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert names == {"shadow_files"}
    assert stat.S_IMODE(ledger.stat().st_mode) == 0o640
