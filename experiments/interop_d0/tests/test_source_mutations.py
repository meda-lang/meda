"""Genuine checked source edits, canonical controls, and independent peer effects."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from experiments.interop_d0 import acceptance_mutations_source as mutations, runner


HERE = Path(__file__).resolve().parents[1]
CASES = {case["id"]: case for case in json.loads((HERE / "acceptance.json").read_text())["cases"]}


class SourceMutationTests(unittest.TestCase):
    def assert_pair(self, receipt, changed_file):
        control = receipt["mutationControl"]
        execution = receipt["mutationExecution"]
        self.assertEqual(execution["arm"], "typescript")
        self.assertEqual(execution["changedFiles"], [changed_file])
        canonical = {str(path.relative_to(HERE / "client")): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in (HERE / "client").rglob("*.ts")}
        self.assertEqual(execution["sourceSha256"]["control"], canonical)
        differences = {name for name, digest in execution["sourceSha256"]["mutant"].items()
                       if digest != canonical[name]}
        self.assertEqual(differences, {changed_file})
        self.assertEqual(execution["compiler"]["control"]["options"],
                         execution["compiler"]["mutant"]["options"])
        for compiler in execution["compiler"].values():
            self.assertTrue(compiler["passed"])
            self.assertTrue(compiler["sourceStrict"])
        self.assertEqual(control["bindingManifest"]["limits"], receipt["bindingManifest"]["limits"])
        for candidate in (control, receipt):
            self.assertTrue(candidate["peerProcessesRetired"])
            self.assertTrue(candidate["worker"]["retired"])
            self.assertTrue(candidate["worker"]["supervisorJoined"])
            self.assertFalse(candidate["credentialLeakDetected"])
        return control

    def test_compiled_repeat_attempt_is_denied_after_unknown_delivery(self):
        receipt = mutations.execute_source_mutant(CASES["W12-client-repeat-submit"]["scenario"])
        control = self.assert_pair(receipt, "workflow.ts")
        self.assertEqual(control["result"]["remoteOutcome"], "Unknown")
        self.assertEqual(receipt["result"]["outcome"], "BudgetDenied")
        control_submits = [row for row in control["worker"]["calls"] if row["operation"] == "submit"]
        submits = [row for row in receipt["worker"]["calls"] if row["operation"] == "submit"]
        self.assertEqual(len(control_submits), 1)
        self.assertEqual(len(submits), 2)
        self.assertEqual(submits[0]["remoteOutcome"], "Unknown")
        self.assertEqual(submits[1]["code"], "BudgetDenied")
        for candidate in (control, receipt):
            created = [row for row in candidate["peers"]["a2a"] if row["event"] == "created"]
            self.assertEqual(len(created), 1)
            self.assertEqual(sum(row["event"] == "dispatch" and row.get("method") == "SendMessage"
                                 for row in candidate["trace"]), 1)

    def test_compiled_validator_publishes_wrong_value_that_control_rejects(self):
        receipt = mutations.execute_source_mutant(CASES["W12-wrong-domain-validator"]["scenario"])
        control = self.assert_pair(receipt, "domain.ts")
        self.assertEqual(control["result"]["outcome"], "DomainRejected")
        self.assertEqual(receipt["result"]["outcome"], "Success")
        self.assertNotEqual(receipt["result"]["report"]["selected"][0]["value"], "blue")
        for candidate, success in ((control, False), (receipt, True)):
            publications = [row for row in candidate["trace"] if row["event"] == "publication"]
            self.assertEqual(len(publications), 1)
            self.assertEqual(publications[0]["success"], success)
            self.assertTrue(any(row["event"] == "response_mutated" and row.get("mutation") == "wrong_value"
                                for row in candidate["proxy"]["a2a"]))

    def test_unknown_mutation_is_not_run(self):
        with self.assertRaises(runner.UnsupportedScenario):
            mutations.execute_source_mutant({"sourceMutation": "unspecified"})


if __name__ == "__main__":
    unittest.main()
