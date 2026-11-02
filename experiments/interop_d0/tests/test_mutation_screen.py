"""Reassess the same retained observations without waiving any failed check."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from experiments.interop_d0 import mutation_screen


RECEIPT = Path(__file__).resolve().parents[3] / "results/acceptance-mutations/frozen-run.json"


def document():
    return json.loads(RECEIPT.read_text())


def repeat_row(value):
    return next(row for row in value["runs"] if row["caseId"] == "W12-client-repeat-submit")


class MutationScreenTests(unittest.TestCase):
    def test_original_failed_assessment_is_no_longer_a_ci_exception(self):
        result = mutation_screen.summarize(document())
        self.assertFalse(result["behavioralScreenPassed"])
        self.assertFalse(result["acceptanceClosed"])
        self.assertEqual(result["acceptanceRevision"]["id"], "original")
        self.assertEqual(result["fullAcceptanceStatusCounts"], {"unverified": 3, "failed": 1})
        repeat = next(row for row in result["cases"] if row["caseId"] == "W12-client-repeat-submit")
        self.assertFalse(repeat["behaviorVerified"])
        self.assertEqual(repeat["failedFrozenChecks"], ["invariant.attribution_recorded"])

    def test_revised_assessment_preserves_original_failure_and_missing_evidence(self):
        value = document()
        before = copy.deepcopy(value)
        file_hash = hashlib.sha256(RECEIPT.read_bytes()).hexdigest()
        result = mutation_screen.summarize(value, revision="attribution-1")
        self.assertTrue(result["behavioralScreenPassed"])
        self.assertFalse(result["acceptanceClosed"])
        self.assertFalse(result["medaSourceArmExecuted"])
        self.assertEqual(result["acceptanceRevision"]["id"], "attribution-1")
        self.assertEqual(result["originalFullAcceptanceStatusCounts"], {"unverified": 3, "failed": 1})
        self.assertEqual(result["fullAcceptanceStatusCounts"], {"unverified": 4})
        for row in result["cases"]:
            self.assertEqual(row["failedFrozenChecks"], [])
            self.assertTrue(row["unverifiedChecks"])
            if row["caseId"] == "W12-client-repeat-submit":
                self.assertEqual(row["originalFullAcceptanceStatus"], "failed")
                self.assertEqual(row["originalFailedFrozenChecks"], ["invariant.attribution_recorded"])
            else:
                self.assertEqual(row["originalFullAcceptanceStatus"], row["fullAcceptanceStatus"])
                self.assertEqual(row["originalFailedFrozenChecks"], [])
        self.assertEqual(value, before)
        self.assertEqual(hashlib.sha256(RECEIPT.read_bytes()).hexdigest(), file_hash)

    def test_correction_does_not_hide_a_second_task_missing_retry_or_leak(self):
        for defect in ("second_task", "missing_retry", "leak"):
            value = document()
            receipt = repeat_row(value)["receipt"]
            if defect == "second_task":
                receipt["peers"]["a2a"].append({"event": "created", "taskId": "unexpected-task"})
            elif defect == "missing_retry":
                receipt["worker"]["calls"].pop()
            else:
                receipt["credentialLeakDetected"] = True
            with self.subTest(defect=defect):
                self.assertFalse(mutation_screen.summarize(
                    value, revision="attribution-1")["behavioralScreenPassed"])

    def test_incorrect_enforcement_layer_is_rejected_under_corrected_revision(self):
        value = document()
        receipt = repeat_row(value)["receipt"]
        receipt["result"] = {"outcome": "DomainRejected"}
        receipt["worker"]["calls"][-1] = {"operation": "observe", "kind": "Task", "state": "Completed"}
        result = mutation_screen.summarize(value, revision="attribution-1")
        repeat = next(row for row in result["cases"] if row["caseId"] == "W12-client-repeat-submit")
        self.assertFalse(result["behavioralScreenPassed"])
        self.assertIn("invariant.attribution_recorded", repeat["failedFrozenChecks"])

    def test_changed_sources_and_saved_pass_flags_never_override_reassessment(self):
        value = document()
        value["sourceUnchangedDuringRun"] = False
        for row in value["runs"]:
            row["assessment"] = {"passed": True, "status": "passed"}
        result = mutation_screen.summarize(value, revision="attribution-1")
        self.assertFalse(result["behavioralScreenPassed"])
        self.assertEqual(result["originalFullAcceptanceStatusCounts"]["failed"], 1)
        self.assertEqual(result["fullAcceptanceStatusCounts"], {"unverified": 4})

    def test_missing_duplicate_or_unexecuted_cases_are_rejected(self):
        for defect in ("missing", "duplicate", "not_run"):
            value = document()
            if defect == "missing":
                value["runs"].pop()
            elif defect == "duplicate":
                value["runs"][-1] = value["runs"][0]
            else:
                value["runs"][0]["executionStatus"] = "not_run"
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                mutation_screen.summarize(value, revision="attribution-1")

    def test_receipt_must_belong_to_the_pinned_profile_and_inventory(self):
        for defect in ("wrong_profile", "wrong_inventory", "missing_inventory"):
            value = document()
            if defect == "wrong_profile":
                value["profile"] = "another-profile"
            elif defect == "wrong_inventory":
                value["sourceSha256"]["acceptance.json"] = "0" * 64
            else:
                del value["sourceSha256"]["acceptance.json"]
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                mutation_screen.summarize(value, revision="attribution-1")
