from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "components/collector/clickhouse/build-ai-device-backfill.py"


def load_module():
    specification = importlib.util.spec_from_file_location(
        "ai_device_backfill", SCRIPT
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


BACKFILL = load_module()


class AiDeviceBackfillTests(unittest.TestCase):
    def mapping(self, rows):
        temporary = tempfile.NamedTemporaryFile(delete=False)
        temporary.close()
        path = Path(temporary.name)
        path.write_text(
            "".join(
                json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                for row in rows
            ),
            encoding="utf-8",
        )
        path.chmod(0o600)
        self.addCleanup(path.unlink)
        return path

    def test_rendered_query_is_bounded_synchronous_and_aggregate_only(self):
        rows = BACKFILL.load_mapping(
            self.mapping(
                [
                    {"run_id": "run-v1-b", "device": "router-b.example.invalid"},
                    {"run_id": "run-v1-a", "device": "router-a.example.invalid"},
                ]
            )
        )
        sql = BACKFILL.render_sql(rows)
        self.assertIn("UPDATE device = multiIf(", sql)
        self.assertIn("SETTINGS mutations_sync = 2", sql)
        self.assertIn("countIf(device = '') AS missing_devices", sql)
        self.assertLess(sql.index("run-v1-a"), sql.index("run-v1-b"))

    def test_divergent_duplicate_is_refused(self):
        path = self.mapping(
            [
                {"run_id": "run-v1-a", "device": "router-a.example.invalid"},
                {"run_id": "run-v1-a", "device": "router-b.example.invalid"},
            ]
        )
        with self.assertRaisesRegex(
            BACKFILL.BackfillError, "divergent run identity"
        ):
            BACKFILL.load_mapping(path)

    def test_unsafe_or_overpermissive_identity_is_refused(self):
        path = self.mapping(
            [{"run_id": "run-v1-a", "device": "router'a"}]
        )
        with self.assertRaisesRegex(BACKFILL.BackfillError, "line 1 differs"):
            BACKFILL.load_mapping(path)


if __name__ == "__main__":
    unittest.main()
