"""The bounded CI screen must retain, rather than launder, acceptance failures."""
import copy
import unittest
from unittest import mock

from experiments.interop_d0 import mutation_screen


def document():
    return {"sourceUnchangedDuringRun": True,
            "runs": [{"caseId": case_id, "executionStatus": "executed", "receipt": {}}
                     for case_id in sorted(mutation_screen.CASE_IDS)]}


def assessment(case, receipt):
    repeat = case["id"] == "W12-client-repeat-submit"
    names = ["outcomeCategory", "phase", "invariant.one_terminal"]
    names += ["count." + key for key in case["expected"]["businessDispatches"]]
    names += ["count.peerTaskCreations", "count.successfulPublications"]
    names += ["invariant.unknown_not_refunded" if repeat else "invariant.independent_mutant_detection"]
    checks = [{"name": name, "status": "passed"} for name in names]
    checks += [{"name": "invariant.attribution_recorded", "status": "failed" if repeat else "passed"},
               {"name": "invariant.no_secret_exposure", "status": "unverified"}]
    return {"status": "failed" if repeat else "unverified", "checks": checks,
            "normalized": {"layer": "shared_host" if repeat else "independent_oracle"}}


class MutationScreenTests(unittest.TestCase):
    def test_behavior_success_preserves_failed_and_unverified_acceptance(self):
        with mock.patch.object(mutation_screen.oracle, "evaluate_case", side_effect=assessment):
            result = mutation_screen.summarize(document())
        self.assertTrue(result["behavioralScreenPassed"])
        self.assertFalse(result["acceptanceClosed"])
        self.assertEqual(result["fullAcceptanceStatusCounts"], {"unverified": 3, "failed": 1})
        mismatch = next(row for row in result["cases"] if row["knownAttributionMismatch"])
        self.assertEqual(mismatch["failedFrozenChecks"], ["invariant.attribution_recorded"])

    def test_other_failures_or_missing_detection_cannot_use_known_mismatch(self):
        for defect in ("additional_failure", "missing_detection", "unknown_detection", "wrong_layer"):
            def broken(case, receipt):
                value = assessment(case, receipt)
                if case["id"] == "W12-client-repeat-submit":
                    if defect == "additional_failure":
                        value["checks"].append({"name": "invariant.no_late_application", "status": "failed"})
                    elif defect == "wrong_layer":
                        value["normalized"]["layer"] = "application"
                    else:
                        for check in value["checks"]:
                            if check["name"] == "invariant.unknown_not_refunded":
                                check["status"] = "unverified"
                        if defect == "missing_detection":
                            value["checks"] = [check for check in value["checks"]
                                               if check["name"] != "invariant.unknown_not_refunded"]
                return value
            with self.subTest(defect=defect), mock.patch.object(
                    mutation_screen.oracle, "evaluate_case", side_effect=broken):
                self.assertFalse(mutation_screen.summarize(document())["behavioralScreenPassed"])

    def test_changed_sources_and_saved_pass_flags_never_override_reassessment(self):
        value = document()
        value["sourceUnchangedDuringRun"] = False
        for row in value["runs"]:
            row["assessment"] = {"passed": True, "status": "passed"}
        with mock.patch.object(mutation_screen.oracle, "evaluate_case", side_effect=assessment) as evaluate:
            result = mutation_screen.summarize(value)
        self.assertEqual(evaluate.call_count, 4)
        self.assertFalse(result["behavioralScreenPassed"])
        self.assertEqual(result["fullAcceptanceStatusCounts"]["failed"], 1)

    def test_missing_duplicate_or_unexecuted_cases_are_rejected(self):
        for defect in ("missing", "duplicate", "not_run"):
            value = copy.deepcopy(document())
            if defect == "missing":
                value["runs"].pop()
            elif defect == "duplicate":
                value["runs"][-1] = value["runs"][0]
            else:
                value["runs"][0]["executionStatus"] = "not_run"
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                mutation_screen.summarize(value)
