"""Adversarial checks for the independent receipt oracle, not host behavior."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("d0_independent_oracle", HERE / "oracle.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
INVENTORY = json.loads((HERE / "acceptance.json").read_text())
CASES = {case["id"]: case for case in INVENTORY["cases"]}


def receipt():
    trace = [{"event": "root_open", "sequence": 0}]
    for number, (protocol, method) in enumerate([
            ("mcp", "tools/list"), ("mcp", "tools/call"),
            ("a2a", "__card"), ("a2a", "SendMessage"),
            ("a2a", "__card"), ("a2a", "GetTask")], 1):
        for event in ("admitted", "dispatch", "received"):
            trace.append({"event": event, "protocol": protocol, "method": method,
                          "cleanup": False, "request": number, "sequence": len(trace)})
    trace.extend([{"event": "root_close", "sequence": len(trace)},
                  {"event": "publication", "outcome": "Success", "success": True, "sequence": len(trace) + 1}])
    return {"result": {"outcome": "Success", "report": copy.deepcopy(oracle.REPORT)},
            "cleanup": [], "trace": trace,
            "worker": {"retired": True, "returncode": 0, "supervisorJoined": True,
                       "responsesAfterFatal": 0, "calls": [
                           {"operation": "readEvidence", "kind": "Evidence"},
                           {"operation": "submit", "kind": "Task", "state": "Working"},
                           {"operation": "observe", "kind": "Task", "state": "Completed"}]},
            "peers": {"mcp": [{"event": "evidence_read", "documentId": "evidence-42"}],
                      "a2a": [{"event": "created", "taskId": "task-1", "contextId": "context-1"},
                              {"event": "observed", "taskId": "task-1"}]},
            "proxy": {"mcp": [{"event": "forward", "operation": "readEvidence"}],
                      "a2a": [{"event": "forward", "operation": "submit"},
                              {"event": "forward", "operation": "observe"}]},
            "credentialLeakDetected": False}


def check_named(result, name):
    return next(item for item in result["checks"] if item["name"] == name)


class IndependentOracleTests(unittest.TestCase):
    def test_current_complete_workflow_receipt_is_partial_not_full_pass(self):
        value = oracle.evaluate_case(CASES["W01-evidence-json"], receipt())
        self.assertEqual(value["status"], "unverified")
        self.assertFalse(value["passed"])
        self.assertEqual(value["counts"]["businessDispatches"], {
            "readEvidence": 1, "submit": 1, "observe": 1, "provideInput": 0, "cancel": 0, "cleanupCancel": 0})
        self.assertIn("exact_report", value["invariants"]["checked"])
        self.assertIn("no_secret_exposure", value["invariants"]["unverified"])
        self.assertIn("discovery_metered", value["invariants"]["unverified"])

    def test_mutated_report_is_detected_independently(self):
        for mutation in ("wrong_value", "extra", "order", "boolean_revision"):
            with self.subTest(mutation=mutation):
                observed = receipt()
                report = observed["result"]["report"]
                if mutation == "wrong_value": report["selected"][0]["value"] = "invented"
                if mutation == "extra": report["unexpected"] = True
                if mutation == "order": report["selected"].reverse()
                if mutation == "boolean_revision": report["revision"] = True
                value = oracle.evaluate_case(CASES["W01-evidence-json"], observed)
                self.assertEqual(value["status"], "failed")
                self.assertIn("exact_report", value["invariants"]["failed"])

    def test_duplicate_publication_and_task_are_rejected(self):
        observed = receipt()
        observed["trace"].append(copy.deepcopy(observed["trace"][-1]))
        observed["peers"]["a2a"].append({"event": "created", "taskId": "task-2"})
        value = oracle.evaluate_case(CASES["W01-evidence-json"], observed)
        self.assertEqual(value["status"], "failed")
        self.assertIn("one_terminal", value["invariants"]["failed"])
        self.assertEqual(check_named(value, "count.peerTaskCreations")["status"], "failed")

    def test_missing_witness_cannot_be_replaced_by_pass_flag(self):
        observed = receipt()
        del observed["peers"]
        observed["invariantPassed"] = {name: True for name in INVENTORY["invariantDefinitions"]}
        observed["witnesses"] = {name: True for name in INVENTORY["witnessKinds"]}
        value = oracle.evaluate_case(CASES["W01-evidence-json"], observed)
        self.assertFalse(value["passed"])
        self.assertIn("peer_task_ledger", value["witnesses"]["missing"])
        self.assertIsNone(value["counts"]["peerTaskCreations"])

    def test_empty_peer_ledger_is_zero_missing_ledger_is_unknown(self):
        observed = receipt()
        observed["peers"]["a2a"] = []
        value = oracle.evaluate_case(CASES["W01-evidence-json"], observed)
        self.assertEqual(value["counts"]["peerTaskCreations"], 0)
        self.assertEqual(check_named(value, "count.peerTaskCreations")["status"], "failed")
        del observed["peers"]["a2a"]
        value = oracle.evaluate_case(CASES["W01-evidence-json"], observed)
        self.assertIsNone(value["counts"]["peerTaskCreations"])
        self.assertEqual(check_named(value, "count.peerTaskCreations")["status"], "unverified")

    def test_send_count_requires_proxy_classification(self):
        observed = receipt()
        observed["proxy"]["a2a"] = []
        value = oracle.evaluate_case(CASES["W01-evidence-json"], observed)
        self.assertIsNone(value["counts"]["businessDispatches"]["submit"])
        self.assertFalse(value["passed"])

    def test_protocol_error_does_not_become_expected_category(self):
        observed = receipt()
        observed["result"] = {"outcome": "ProtocolRejected", "remoteOutcome": "Unknown", "fatal": False}
        before = oracle.normalize_outcome(observed)
        self.assertFalse(before["conclusive"])
        for case_id in ("W05-wrong-rpc-id", "W08-evidence-wrong_document"):
            value = oracle.evaluate_case(CASES[case_id], observed)
            self.assertEqual(value["normalized"], before)
            self.assertEqual(check_named(value, "outcomeCategory")["status"], "unverified")

    def test_proxy_witness_disambiguates_evidence_and_wire_rejection(self):
        observed = receipt()
        observed["result"] = {"outcome": "ProtocolRejected", "remoteOutcome": "Completed", "fatal": False}
        observed["worker"]["calls"] = [{"operation": "readEvidence", "kind": "Error", "code": "ProtocolRejected"}]
        observed["proxy"]["mcp"].append({"event": "response_mutated", "mutation": "wrong_document"})
        self.assertEqual(oracle.normalize_outcome(observed)["categories"], ["evidence_rejected"])
        observed["proxy"]["mcp"][-1]["mutation"] = "evidence_response_id"
        self.assertEqual(oracle.normalize_outcome(observed)["categories"], ["protocol_rejected"])

    def test_unknown_is_not_inferred_from_protocol_error(self):
        observed = receipt()
        observed["result"] = {"outcome": "ProtocolRejected", "remoteOutcome": "Unknown"}
        observed["trace"].append({"event": "transport_error", "remoteOutcome": "Unknown"})
        self.assertNotEqual(oracle.normalize_outcome(observed)["categories"], ["delivery_unknown"])
        observed["result"]["outcome"] = "TransportFailure"
        self.assertEqual(oracle.normalize_outcome(observed)["categories"], ["delivery_unknown"])

    def test_late_success_and_credential_leak_fail(self):
        observed = receipt()
        observed["trace"].insert(-1, {"event": "root_abort", "code": "RootTerminated"})
        observed["credentialLeakDetected"] = True
        value = oracle.evaluate_case(CASES["W01-evidence-json"], observed)
        self.assertIn("no_late_application", value["invariants"]["failed"])
        self.assertIn("no_secret_exposure", value["invariants"]["failed"])

    def test_evaluation_does_not_mutate_inventory_or_observations(self):
        case, observed = copy.deepcopy(CASES["W01-evidence-json"]), receipt()
        before = copy.deepcopy((case, observed))
        oracle.evaluate_case(case, observed)
        self.assertEqual((case, observed), before)

    def test_each_required_obligation_gets_an_explicit_check(self):
        value = oracle.evaluate_case(CASES["W01-evidence-json"], {})
        names = {item["name"] for item in value["checks"]}
        for invariant in CASES["W01-evidence-json"]["expected"]["invariants"]:
            self.assertIn("invariant." + invariant, names)
        for witness in CASES["W01-evidence-json"]["expected"]["witnesses"]:
            self.assertIn("witness." + witness, names)
        self.assertFalse(value["passed"])

    def test_setup_offsets_are_applied_before_counting(self):
        observed = receipt()
        observed["probeCalls"] = [{"operation": "observe", "result": {"kind": "Error", "code": "InvalidReference"}}]
        observed["measuredWindow"] = {"trace": {"start": len(observed["trace"]), "end": len(observed["trace"])}}
        for name in ("peers", "proxy"):
            observed["measuredWindow"][name] = {p: {"start": len(v), "end": len(v)} for p, v in observed[name].items()}
        value = oracle.evaluate_case(CASES["W10-host-forged_token"], observed)
        self.assertEqual(value["counts"]["peerTaskCreations"], 0)
        self.assertEqual(value["counts"]["businessDispatches"]["submit"], 0)
        self.assertEqual(value["normalized"]["categories"], ["admission_denied"])
        self.assertIn("counts_exclude_setup", value["invariants"]["checked"])

    def test_invalid_offsets_never_claim_setup_exclusion(self):
        observed = receipt()
        observed["measuredWindow"] = {"trace": {"start": -1, "end": 1000}, "peers": {}, "proxy": {}}
        value = oracle.evaluate_case(CASES["W10-host-forged_token"], observed)
        self.assertEqual(check_named(value, "measurement_window")["status"], "unverified")
        self.assertIsNone(value["counts"]["peerTaskCreations"])

    def test_codec_decoder_and_state_enum_are_observed_independently(self):
        observed = {"probe": {"kind": "header_codec", "input": "évidence", "encoded": "=?test?=", "decoded": "wrong"},
                    "trace": [], "peers": {"mcp": [], "a2a": []}, "proxy": {"mcp": [], "a2a": []}}
        value = oracle.evaluate_case(CASES["W05-header-unicode"], observed)
        self.assertIn("header_roundtrip", value["invariants"]["failed"])
        observed["probe"] = {"kind": "task_state_decode", "wireState": "TASK_STATE_WORKING", "normalizedState": "Working", "sdkEnumName": "TASK_STATE_WORKING"}
        self.assertEqual(oracle.normalize_outcome(observed)["categories"], ["working"])

    def test_private_token_roundtrip_is_not_an_application_wrapper_test(self):
        observed = {"probe": {"kind": "reference_serialization", "operation": "deserialize_roundtrip",
                    "serializedWrapper": '"private-broker-token"', "bridgeCallsBefore": 0, "bridgeCallsAfter": 1,
                    "roundtripResult": {"kind": "Task", "state": "Working"}},
                    "trace": [], "peers": {"mcp": [], "a2a": []}, "proxy": {"mcp": [], "a2a": []}}
        value = oracle.evaluate_case(CASES["W10-host-deserialize_roundtrip"], observed)
        self.assertIn("no_authority_roundtrip", value["invariants"]["failed"])

    def test_peer_request_status_and_business_dispatch_are_independent(self):
        observed = {"probe": {"kind": "peer_request"}, "requests": [{"protocol": "mcp", "method": "tools/call", "operation": "readEvidence", "dispatched": True, "status": 401, "body": {"error": "Unauthorized"}}],
                    "trace": [], "peers": {"mcp": [{"event": "denied", "reason": "credential"}], "a2a": []}, "proxy": {"mcp": [], "a2a": []}}
        value = oracle.evaluate_case(CASES["W06-credential-missing"], observed)
        self.assertEqual(value["normalized"]["categories"], ["authentication_denied"])
        self.assertEqual(value["counts"]["businessDispatches"]["readEvidence"], 1)
        self.assertEqual(check_named(value, "outcomeCategory")["status"], "passed")


if __name__ == "__main__":
    unittest.main()
