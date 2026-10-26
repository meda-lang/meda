"""Adapter receipts from actual helpers, SDK setup, and compiled TS bindings."""
import copy
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from acceptance_adapters import execute_adapter_probe, UnsupportedScenario
from oracle import evaluate_case
from runner import compile_client

CASES = {row["id"]: row for row in json.loads((HERE / "acceptance.json").read_text())["cases"]}


class AdapterExecutionTests(unittest.TestCase):
    def test_local_corpus_uses_helpers_without_network(self):
        rows = [row for row in CASES.values() if row["surface"] == "adapter_probe" and "setup" not in row["scenario"]]
        self.assertEqual(len(rows), 19)
        for case in rows:
            with self.subTest(case=case["id"]):
                observed = execute_adapter_probe(case["scenario"])
                self.assertEqual(observed["networkAttempts"], [])
                result = evaluate_case(case, observed)
                self.assertIn(case["expected"]["outcomeCategory"], result["normalized"]["categories"])
                self.assertTrue(all(value == 0 for value in result["counts"]["businessDispatches"].values()))
                self.assertEqual(result["counts"]["peerTaskCreations"], 0)

    def test_independent_oracle_rejects_corrupted_codec_observation(self):
        case = CASES["W05-header-unicode"]
        observed = execute_adapter_probe(case["scenario"])
        observed["probe"]["decoded"] = "changed"
        result = evaluate_case(case, observed)
        self.assertIn("header_roundtrip", result["invariants"]["failed"])

    def test_real_owned_wrapper_roundtrip_has_no_measured_effect(self):
        compile_client()
        for name in ("W10-typescript-inert-serialization", "W10-host-deserialize_roundtrip"):
            with self.subTest(case=name):
                case = CASES[name]
                observed = execute_adapter_probe(case["scenario"], compiled=True)
                probe = observed["probe"]
                self.assertEqual(probe["serializedWrapper"], "{}")
                self.assertEqual(probe["roundtripResult"]["code"], "InvalidReference")
                self.assertEqual(probe["bridgeCallsBefore"], probe["bridgeCallsAfter"])
                self.assertEqual(probe["positiveControlResult"], {"kind": "Task", "state": "Completed"})
                self.assertEqual(sum(row["event"] == "created" for row in observed["peers"]["a2a"]), 1)
                evaluated = evaluate_case(case, observed)
                self.assertEqual(evaluated["counts"]["peerTaskCreations"], 0)
                self.assertEqual(evaluated["counts"]["businessDispatches"]["observe"], 0)
                self.assertIn("no_authority_roundtrip", evaluated["invariants"]["checked"])
                self.assertIn("counts_exclude_setup", evaluated["invariants"]["checked"])
                self.assertTrue(observed["peerProcessesRetired"])
                self.assertFalse(any(row["credentialMatches"] or row["referenceMatches"]
                                     for row in observed["applicationChannelScan"]["channels"]))
                # Erasing the measured window must expose the setup effects,
                # rather than accepting an asserted zero count from the runner.
                unbounded = copy.deepcopy(observed)
                del unbounded["measuredWindow"]
                self.assertEqual(evaluate_case(case, unbounded)["counts"]["peerTaskCreations"], 1)

    def test_unknown_scenario_is_not_an_accepted_probe(self):
        with self.assertRaises(UnsupportedScenario):
            execute_adapter_probe({"futureAdapterProbe": True})


if __name__ == "__main__":
    unittest.main()
