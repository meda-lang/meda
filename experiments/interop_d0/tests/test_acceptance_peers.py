"""The nine direct peer stimuli execute through actual SDK processes and TLS."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from acceptance_peers import probe_in_environment
from runner import environment


class AcceptancePeerTests(unittest.TestCase):
    def test_actual_denials_discovery_and_setup_window(self):
        inventory = json.loads((HERE / "acceptance.json").read_text())
        cases = [case for case in inventory["cases"] if case["surface"] == "peer_probe"]
        self.assertEqual(len(cases), 9)
        with environment({}) as env:
            for case in cases:
                with self.subTest(stimulus=case["scenario"]):
                    receipt = probe_in_environment(case["scenario"], env)
                    window = receipt["measuredWindow"]["requests"]
                    measured = receipt["requests"][window["start"]:window["end"]]
                    self.assertEqual(len(measured), 1)
                    request = measured[0]
                    self.assertTrue(request["dispatched"])
                    self.assertFalse(receipt["credentialLeakDetected"])
                    self.assertTrue(receipt["witnessesCapturedBeforePeerShutdown"])
                    self.assertFalse(request["responseTruncated"])
                    scenario = case["scenario"]
                    if request["method"] == "tools/call":
                        peer_window = receipt["measuredWindow"]["peers"]["mcp"]
                        peer_rows = receipt["peers"]["mcp"][peer_window["start"]:peer_window["end"]]
                        self.assertFalse(any(row["event"] == "evidence_read" for row in peer_rows))
                    if "credentialVariant" in scenario:
                        self.assertEqual(request["status"], 401)
                        self.assertEqual(request["body"], {"error": "Unauthorized"})
                    elif "wireMutation" in scenario:
                        self.assertEqual(request["status"], 400)
                        self.assertIn("error", request["body"])
                        self.assertTrue(request["schemaValidation"]["accepted"])
                    elif scenario["operation"] == "server/discover":
                        self.assertEqual(request["status"], 200)
                        self.assertIn("2026-07-28", request["body"]["result"]["supportedVersions"])
                        self.assertEqual(request["schemaValidation"],
                                         {"schemaName": "mcp.types.DiscoverResult", "accepted": True})
                    else:
                        self.assertEqual(request["body"]["error"]["code"], -32001)
                        self.assertEqual(window, {"start": 1, "end": 2})
                        peer_window = receipt["measuredWindow"]["peers"]["a2a"]
                        measured_peers = receipt["peers"]["a2a"][peer_window["start"]:peer_window["end"]]
                        self.assertTrue(any(row["event"] == "task_access_denied" for row in measured_peers))
                        self.assertFalse(any(row["event"] == "created" for row in measured_peers))
                    serialized = json.dumps(receipt)
                    self.assertTrue(all(secret not in serialized for secret in env["secrets"]))


if __name__ == "__main__":
    unittest.main()
