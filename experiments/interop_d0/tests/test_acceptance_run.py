"""Safe failure receipts for the acceptance runner."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from experiments.interop_d0 import acceptance_run, runner


class AcceptanceRunTests(unittest.TestCase):
    def case(self, surface="workflow"):
        return {"id": "W01-test", "surface": surface, "scenario": {"probe": "safe"}}

    def test_execution_error_records_closed_stage_without_exception_text(self):
        with mock.patch.object(acceptance_run, "execute",
                               side_effect=RuntimeError("credential=do-not-copy")):
            row = acceptance_run.execute_case(self.case())
        self.assertEqual(row["executionStatus"], "execution_error")
        self.assertEqual(row["errorType"], "RuntimeError")
        self.assertEqual(row["errorStage"], "workflow_execution")
        self.assertNotIn("do-not-copy", json.dumps(row))

    def test_oracle_error_is_distinguished_from_execution_error(self):
        with (mock.patch.object(acceptance_run, "execute", return_value={"result": {}}),
              mock.patch.object(acceptance_run.oracle, "evaluate_case",
                                side_effect=KeyError("private-reference"))):
            row = acceptance_run.execute_case(self.case("host_probe"))
        self.assertEqual(row["executionStatus"], "execution_error")
        self.assertEqual(row["errorType"], "KeyError")
        self.assertEqual(row["errorStage"], "oracle_assessment")
        self.assertNotIn("private-reference", json.dumps(row))

    def test_unknown_surface_cannot_become_a_receipt_stage(self):
        with mock.patch.object(acceptance_run, "execute", side_effect=ValueError("peer-data")):
            row = acceptance_run.execute_case(self.case("peer supplied stage"))
        self.assertEqual(row["errorStage"], "case_dispatch")
        self.assertNotIn("peer supplied stage", row["errorStage"])

    def test_unsupported_case_remains_not_run(self):
        with mock.patch.object(acceptance_run, "execute",
                               side_effect=runner.UnsupportedScenario("fixture unavailable")):
            row = acceptance_run.execute_case(self.case("adapter_probe"))
        self.assertEqual(row["executionStatus"], "not_run")
        self.assertNotIn("errorStage", row)


if __name__ == "__main__":
    unittest.main()
