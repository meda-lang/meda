"""Canonical denials versus instance-local defects over independent SDK peers."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest import mock

from experiments.interop_d0 import acceptance_mutations_host as mutations
from experiments.interop_d0 import host, oracle, runner


HERE = Path(__file__).resolve().parents[1]
CASES = {case["id"]: case for case in json.loads((HERE / "acceptance.json").read_text())["cases"]}


def measured(receipt):
    result, errors = oracle._measured(receipt)
    if errors:
        raise AssertionError(errors)
    return result


class HostMutationTests(unittest.TestCase):
    def assert_common(self, receipt, code):
        control = receipt["mutationControl"]
        self.assertEqual(control["probeCalls"][0]["result"]["code"], code)
        self.assertEqual(control["mutationPolicy"], receipt["mutationPolicy"])
        self.assertFalse(control["credentialLeakDetected"])
        self.assertFalse(receipt["credentialLeakDetected"])
        for item in (control, receipt):
            self.assertTrue(item["peerProcessesRetired"])
            self.assertTrue(item["witnessesCapturedBeforePeerShutdown"])
            publications = [row for row in item["trace"] if row["event"] == "publication"]
            self.assertEqual(len(publications), 1)
            self.assertFalse(publications[0]["success"])
        metadata = receipt["mutationExecution"]
        self.assertEqual(metadata["scope"], "fixture_instance")
        self.assertNotEqual(metadata["canonicalMethodSha256"], metadata["mutatedMethodSha256"])
        self.assertNotEqual(receipt["result"]["outcome"], "mutation_detected")

    def test_removed_grant_dispatches_only_in_mutant_with_real_peer_creation(self):
        canonical = host.Host.call
        receipt = mutations.execute_host_mutant(CASES["W12-mutant-remove-grant"]["scenario"])
        self.assertIs(host.Host.call, canonical)
        self.assert_common(receipt, "AuthorityDenied")
        self.assertNotIn("submit", receipt["mutationPolicy"]["grants"])
        baseline, mutated = measured(receipt["mutationControl"]), measured(receipt)
        self.assertEqual(baseline["peers"]["a2a"], [])
        self.assertFalse(any(row["event"] == "dispatch" for row in baseline["trace"]))
        self.assertEqual(sum(row["event"] == "created" for row in mutated["peers"]["a2a"]), 1)
        self.assertEqual(sum(row["event"] == "forward" and row.get("operation") == "submit"
                             for row in mutated["proxy"]["a2a"]), 1)
        self.assertEqual(receipt["probeCalls"][0]["result"]["state"], "Completed")
        # Setup evidence remains visible, while the measured business window
        # contains only the forbidden submit and no cleanup cancellation.
        self.assertTrue(any(row["event"] == "evidence_read" for row in receipt["peers"]["mcp"]))
        self.assertEqual(mutated["peers"]["mcp"], [])
        self.assertEqual(oracle._counts(mutated)["businessDispatches"], {
            "readEvidence": 0, "submit": 1, "observe": 0,
            "provideInput": 0, "cancel": 0, "cleanupCancel": 0})

    def test_removed_quota_dispatches_only_in_mutant_without_increasing_limit(self):
        canonical = host.Host._reserve
        receipt = mutations.execute_host_mutant(CASES["W12-mutant-remove-quota"]["scenario"])
        self.assertIs(host.Host._reserve, canonical)
        self.assert_common(receipt, "BudgetDenied")
        self.assertEqual(receipt["mutationPolicy"]["limits"]["normalRequests"], 0)
        baseline, mutated = measured(receipt["mutationControl"]), measured(receipt)
        self.assertEqual(baseline["peers"]["mcp"], [])
        self.assertEqual(baseline["proxy"]["mcp"], [])
        self.assertEqual(sum(row["event"] == "evidence_read" for row in mutated["peers"]["mcp"]), 1)
        self.assertEqual([row["method"] for row in mutated["trace"] if row["event"] == "dispatch"],
                         ["tools/list", "tools/call"])
        self.assertEqual(receipt["probeCalls"][0]["result"]["kind"], "Evidence")
        self.assertEqual(oracle._counts(mutated)["businessDispatches"], {
            "readEvidence": 1, "submit": 0, "observe": 0,
            "provideInput": 0, "cancel": 0, "cleanupCancel": 0})

    def test_unknown_or_no_longer_applicable_mutation_is_not_silently_counted(self):
        scenario = copy.deepcopy(CASES["W12-mutant-remove-quota"]["scenario"])
        scenario["normalRequests"] = True
        with self.assertRaises(runner.UnsupportedScenario):
            mutations.execute_host_mutant(scenario)
        with mock.patch.object(mutations.inspect, "getsource", return_value="def call(self):\n    pass\n"):
            with self.assertRaises(runner.UnsupportedScenario):
                mutations._method_mutation(object(), "remove_operation_grant")


if __name__ == "__main__":
    unittest.main()
