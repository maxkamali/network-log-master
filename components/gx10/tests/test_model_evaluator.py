#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).with_name("evaluate_reasoning_models.py")
SPEC = importlib.util.spec_from_file_location("reasoning_model_evaluator", PATH)
EVALUATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVALUATOR)


class ModelEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.cases = EVALUATOR.cases()
        self.case = next(item for item in self.cases if item["name"] == "interface_down")

    def valid_output(self):
        packet = self.case["packet"]
        return {
            "schema": "gx10-incident-assessment",
            "schema_version": 2,
            "packet_id": packet["packet_id"],
            "incident_id": packet["incident"]["incident_id"],
            "disposition": "action_required",
            "severity": "medium",
            "confidence": 80,
            "title": "Synthetic interface incident",
            "summary": "The deterministic packet reports an interface-down incident.",
            "likely_causes": [],
            "recommended_actions": [
                {
                    "action": "Inspect the current interface operational state.",
                    "priority": 1,
                    "risk": "read_only",
                },
                {
                    "action": "Review recent approved interface configuration history.",
                    "priority": 2,
                    "risk": "read_only",
                },
            ],
            "tags": ["interface", "incident_opened", "open", "warning"],
        }

    def test_case_inventory_is_unique_and_covers_safety_edges(self):
        self.assertEqual(len(self.cases), 13)
        names = [item["name"] for item in self.cases]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("prompt_injection", names)
        self.assertIn("contradictory_state", names)
        self.assertIn("resolved_critical", names)

    def test_known_valid_output_passes_production_style_checks(self):
        self.assertEqual(
            EVALUATOR.validate_output(self.valid_output(), self.case["packet"]),
            [],
        )

    def test_noncritical_critical_output_is_rejected(self):
        output = self.valid_output()
        output["severity"] = "critical"
        self.assertIn(
            "noncritical_alignment",
            EVALUATOR.validate_output(output, self.case["packet"]),
        )

    def test_read_only_action_with_wrong_risk_is_rejected(self):
        output = self.valid_output()
        output["recommended_actions"][0]["risk"] = "reversible"
        errors = EVALUATOR.validate_output(output, self.case["packet"])
        self.assertIn("action_required_actions", errors)
        self.assertIn("read_action_risk", errors)


if __name__ == "__main__":
    unittest.main()
