"""Adversarial observations for the independent mutation oracle, without a host."""
import copy
import json
from pathlib import Path
import unittest

from experiments.interop_d0 import oracle


CASES = {case["id"]: case for case in json.loads(
    (Path(__file__).resolve().parents[1] / "acceptance.json").read_text())["cases"]}


def observed(outcome, operations=(), *, report=None):
    receipt = {"result": {"outcome": outcome}, "trace": [], "cleanup": [],
               "peers": {"mcp": [], "a2a": []}, "proxy": {"mcp": [], "a2a": []},
               "worker": {"retired": True, "returncode": 0, "calls": []}}
    if report is not None:
        receipt["result"]["report"] = copy.deepcopy(report)
    methods = {"readEvidence": ("mcp", "tools/call"), "submit": ("a2a", "SendMessage"),
               "observe": ("a2a", "GetTask")}
    for operation in operations:
        protocol, method = methods[operation]
        receipt["trace"].append({"event": "dispatch", "protocol": protocol,
                                 "method": method, "cleanup": False})
        receipt["proxy"][protocol].append({"event": "forward", "operation": operation})
        if operation == "readEvidence":
            receipt["peers"][protocol].append({"event": "evidence_read", "documentId": "evidence-42"})
        if operation == "submit":
            receipt["peers"][protocol].append({"event": "created", "taskId": "task-1", "contextId": "context-1"})
    receipt["trace"].append({"event": "publication", "success": outcome == "Success", "outcome": outcome})
    return receipt


def source_execution(mutation):
    filename = "domain.ts" if mutation == "accept_wrong_report" else "workflow.ts"
    hashes = {name: "a" * 64 for name in ("bindings.ts", "domain.ts", "main.ts", "workflow.ts")}
    changed = {**hashes, filename: "b" * 64}
    compiler = {"compiler": "TypeScript", "version": "5.9.3", "passed": True, "sourceStrict": True,
                "options": {key: True for key in ("strict", "noImplicitReturns", "noUncheckedIndexedAccess", "exactOptionalPropertyTypes", "noEmitOnError")}}
    return {"kind": "source_mutant", "mutation": mutation, "arm": "typescript", "changedFiles": [filename],
            "sourceSha256": {"control": hashes, "mutant": changed},
            "compiler": {"control": copy.deepcopy(compiler), "mutant": copy.deepcopy(compiler)}}


def host_pair(mutation):
    grant = mutation == "remove_operation_grant"
    operation, denial = ("submit", "AuthorityDenied") if grant else ("readEvidence", "BudgetDenied")
    control = observed(denial)
    control["trace"].insert(0, {"event": "call_rejected", "operation": operation, "code": denial})
    control["probeCalls"] = [{"operation": operation, "result": {"kind": "Error", "code": denial}}]
    control["mutationPolicy"] = {"operation": operation, "grants": ["readEvidence"],
                                 "limits": {"max_requests": 2, "cleanup_requests": 2, "normalRequests": 0}}
    mutant = observed("ProbeComplete", [operation])
    mutant["probeCalls"] = [{"operation": operation, "result": {"kind": "Task" if grant else "Evidence"}}]
    mutant["mutationPolicy"] = copy.deepcopy(control["mutationPolicy"])
    mutant["mutationControl"] = control
    mutant["mutationExecution"] = {"kind": "host_mutant", "mutation": mutation, "arm": "shared"}
    return mutant


def wrong_report_pair():
    control = observed("DomainRejected", ["readEvidence", "submit", "observe"])
    bad = copy.deepcopy(oracle.REPORT)
    bad["selected"][0]["value"] = "invented"
    mutant = observed("Success", ["readEvidence", "submit", "observe"], report=bad)
    for side in (control, mutant):
        side["worker"]["calls"] = [{"operation": "readEvidence", "kind": "Evidence"},
            {"operation": "submit", "kind": "Task", "state": "Working"},
            {"operation": "observe", "kind": "Task", "state": "Completed"}]
        side["proxy"]["a2a"].append({"event": "response_mutated", "mutation": "wrong_value"})
    mutant.update(mutationControl=control, mutationExecution=source_execution("accept_wrong_report"))
    return mutant


def repeat_pair():
    control = observed("TransportFailure", ["readEvidence", "submit"])
    control["result"]["remoteOutcome"] = "Unknown"
    control["worker"]["calls"] = [{"operation": "readEvidence", "kind": "Evidence"},
        {"operation": "submit", "kind": "Error", "code": "TransportFailure", "remoteOutcome": "Unknown"}]
    control["proxy"]["a2a"].append({"event": "response_dropped", "operation": "submit", "afterUpstreamResponse": True})
    control["trace"].insert(-1, {"event": "transport_error", "remoteOutcome": "Unknown"})
    mutant = copy.deepcopy(control)
    mutant["result"] = {"outcome": "BudgetDenied", "remoteOutcome": "NotStarted"}
    mutant["trace"].insert(-1, {"event": "call_rejected", "operation": "submit", "code": "BudgetDenied"})
    mutant["worker"]["calls"].append({"operation": "submit", "kind": "Error", "code": "BudgetDenied"})
    mutant.update(mutationControl=control, mutationExecution=source_execution("repeat_after_unknown_submit"))
    return mutant


def named(value, name):
    return next(check for check in value["checks"] if check["name"] == name)


class MutationOracleTests(unittest.TestCase):
    def test_host_mutants_require_paired_policy_and_independent_effects(self):
        for mutation, case_id in (("remove_operation_grant", "W12-mutant-remove-grant"),
                                  ("remove_request_quota", "W12-mutant-remove-quota")):
            with self.subTest(mutation=mutation):
                receipt = host_pair(mutation)
                value = oracle.evaluate_case(CASES[case_id], receipt)
                self.assertEqual(value["normalized"]["categories"], ["mutation_detected"])
                self.assertEqual(value["mutationOracle"]["ordinaryPolicy"], {"control": True, "mutant": False})
                self.assertEqual(receipt["result"]["outcome"], "ProbeComplete")
                self.assertEqual(value["status"], "unverified")

    def test_missing_or_truncated_peer_evidence_cannot_be_replaced_by_flags(self):
        for defect in ("missing", "empty", "truncated"):
            receipt = host_pair("remove_operation_grant")
            if defect == "missing":
                del receipt["peers"]["a2a"]
            elif defect == "empty":
                receipt["peers"]["a2a"] = []
            else:
                receipt["peers"]["a2a"].append({"event": "witness_limit"})
            receipt["mutationDetected"] = True
            receipt["result"]["outcome"] = "mutation_detected"
            value = oracle.evaluate_case(CASES["W12-mutant-remove-grant"], receipt)
            self.assertNotEqual(value["mutationOracle"]["detected"], True)
            self.assertNotEqual(value["normalized"]["categories"], ["mutation_detected"])

    def test_changed_policy_or_already_broken_control_is_not_a_successful_mutation(self):
        receipt = host_pair("remove_request_quota")
        receipt["mutationPolicy"]["limits"]["normalRequests"] = 2
        value = oracle.evaluate_case(CASES["W12-mutant-remove-quota"], receipt)
        self.assertIsNone(value["mutationOracle"]["detected"])
        receipt = host_pair("remove_operation_grant")
        receipt["mutationControl"]["peers"]["a2a"].append({"event": "created", "taskId": "task-0"})
        value = oracle.evaluate_case(CASES["W12-mutant-remove-grant"], receipt)
        self.assertFalse(value["mutationOracle"]["detected"])
        self.assertEqual(named(value, "mutation.control")["status"], "failed")

    def test_wrong_report_remains_an_ordinary_acceptance_failure(self):
        receipt = wrong_report_pair()
        value = oracle.evaluate_case(CASES["W12-wrong-domain-validator"], receipt)
        self.assertTrue(value["mutationOracle"]["detected"])
        self.assertFalse(value["mutationOracle"]["ordinaryPolicy"]["mutant"])
        ordinary = copy.deepcopy(receipt)
        ordinary.pop("mutationExecution")
        ordinary.pop("mutationControl")
        self.assertIn("exact_report", oracle.evaluate_case(CASES["W01-evidence-json"], ordinary)["invariants"]["failed"])
        self.assertEqual(named(value, "typescript_source_execution")["status"], "passed")
        self.assertEqual(named(value, "meda_source_execution")["status"], "unverified")

    def test_valid_report_or_absent_fault_cannot_kill_validator_mutant(self):
        receipt = wrong_report_pair()
        receipt["result"]["report"] = copy.deepcopy(oracle.REPORT)
        self.assertFalse(oracle.evaluate_case(CASES["W12-wrong-domain-validator"], receipt)["mutationOracle"]["detected"])
        receipt = wrong_report_pair()
        receipt["mutationControl"]["proxy"]["a2a"].pop()
        self.assertIsNone(oracle.evaluate_case(CASES["W12-wrong-domain-validator"], receipt)["mutationOracle"]["detected"])

    def test_mutant_cannot_claim_compilation_for_a_changed_binding_or_weaker_options(self):
        for defect in ("extra_source", "weaker_options", "missing_compiler", "false_arm"):
            receipt = wrong_report_pair()
            metadata = receipt["mutationExecution"]
            if defect == "extra_source": metadata["sourceSha256"]["mutant"]["bindings.ts"] = "c" * 64
            if defect == "weaker_options": metadata["compiler"]["mutant"]["options"]["strict"] = False
            if defect == "missing_compiler": metadata["compiler"].pop("mutant")
            if defect == "false_arm": metadata["arm"] = "meda"
            value = oracle.evaluate_case(CASES["W12-wrong-domain-validator"], receipt)
            self.assertFalse(value["mutationOracle"]["sourceChecked"])
            self.assertIsNone(value["mutationOracle"]["detected"])

    def test_repeated_unknown_submit_is_contained_but_frozen_attribution_mismatch_remains(self):
        value = oracle.evaluate_case(CASES["W12-client-repeat-submit"], repeat_pair())
        self.assertTrue(value["mutationOracle"]["repeatContained"])
        self.assertIn("unknown_not_refunded", value["invariants"]["checked"])
        self.assertEqual(value["normalized"]["layer"], "shared_host")
        self.assertEqual(value["status"], "failed")
        self.assertEqual([row["name"] for row in value["checks"] if row["status"] == "failed"],
                         ["invariant.attribution_recorded"])

    def test_repeat_proof_requires_second_source_attempt_and_one_committed_task(self):
        for defect in ("no_retry", "two_tasks", "no_drop"):
            receipt = repeat_pair()
            if defect == "no_retry": receipt["worker"]["calls"].pop()
            if defect == "two_tasks": receipt["peers"]["a2a"].append({"event": "created", "taskId": "task-2"})
            if defect == "no_drop": receipt["proxy"]["a2a"].pop()
            value = oracle.evaluate_case(CASES["W12-client-repeat-submit"], receipt)
            self.assertFalse(value["mutationOracle"]["repeatContained"])

    def test_receipt_metadata_alone_never_supplies_mutant_observations(self):
        receipt = {"mutationExecution": source_execution("accept_wrong_report"), "mutationControl": {},
                   "result": {"outcome": "mutation_detected"}, "mutationDetected": True}
        value = oracle.evaluate_case(CASES["W12-wrong-domain-validator"], receipt)
        self.assertIsNone(value["mutationOracle"]["detected"])
        self.assertNotIn("mutation_oracle_result", value["witnesses"]["available"])

    def test_case_identity_and_observation_immutability(self):
        receipt = host_pair("remove_operation_grant")
        original = copy.deepcopy(receipt)
        case = copy.deepcopy(CASES["W12-mutant-remove-quota"])
        value = oracle.evaluate_case(case, receipt)
        self.assertEqual(named(value, "mutation.identity")["status"], "failed")
        self.assertEqual(receipt, original)
        self.assertEqual(case, CASES["W12-mutant-remove-quota"])


if __name__ == "__main__":
    unittest.main()
