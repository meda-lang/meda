import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clients import (ARMS, ClientError, checker_probes, compile_client,
                     invoke_client, validate_decision, validate_snapshot)


def snapshot(**changes):
    return dict({"stage": "active", "observation": "pending", "taskId": "t1",
                 "remaining": 4, "evidence": "evidence:42", "input": ""}, **changes)


class ClientsTest(unittest.TestCase):
    def test_same_actual_clients_and_frozen_source_digests(self):
        for arm in ARMS:
            checked = compile_client(arm)
            self.assertEqual(arm, checked["arm"])
            self.assertEqual(64, len(checked["sha256"]))
        cases = [
            (snapshot(stage="start", observation="", taskId="", evidence=""),
             {"action": "read", "taskId": "", "payload": ""}),
            (snapshot(observation="evidence", taskId=""),
             {"action": "submit", "taskId": "", "payload": "evidence:42"}),
            (snapshot(), {"action": "poll", "taskId": "t1", "payload": ""}),
            (snapshot(observation="input_required"),
             {"action": "stop", "taskId": "t1", "payload": "input_required"}),
            (snapshot(observation="input_required", input="answer"),
             {"action": "continue", "taskId": "t1", "payload": "answer"}),
            (snapshot(observation="completed", evidence="report:evidence:42", remaining=0),
             {"action": "stop", "taskId": "t1", "payload": "report:evidence:42"}),
            (snapshot(remaining=0),
             {"action": "stop", "taskId": "t1", "payload": "budget"}),
            (snapshot(observation="future_state"),
             {"action": "stop", "taskId": "t1", "payload": "unsupported"}),
        ]
        for kind in ("cancelled", "denied", "invalid", "unknown", "budget"):
            cases.append((snapshot(observation=kind, remaining=0),
                          {"action": "stop", "taskId": "t1", "payload": kind}))
        for value, expected in cases:
            for arm in ARMS:
                with self.subTest(arm=arm, observation=value["observation"]):
                    self.assertEqual(expected, invoke_client(arm, value))

    def test_common_boundary_rejects_inexact_or_malformed_values(self):
        for remaining in (True, 2.5, -1, 100_001, 2 ** 53, "2"):
            with self.subTest(remaining=remaining), self.assertRaises(ClientError):
                validate_snapshot(snapshot(remaining=remaining))
        for extra in ({"unexpected": "x"}, {"input": "\ud800"}, {"input": "x" * 16385}):
            with self.subTest(extra=list(extra)), self.assertRaises(ClientError):
                validate_snapshot(snapshot(**extra))
        with self.assertRaises(ClientError):
            validate_decision({"action": "execute_arbitrary", "taskId": "", "payload": ""})
        with self.assertRaises(ClientError):
            validate_decision({"action": "read", "taskId": "", "payload": "", "tenant": "other"})

    def test_typecheck_probes_are_matched_and_include_positive_control(self):
        probes = checker_probes()
        self.assertEqual(5, len(probes))
        for probe in probes:
            for arm in ARMS:
                with self.subTest(probe=probe["id"], arm=arm):
                    self.assertEqual(probe["expectedAccepted"], probe["arms"][arm]["accepted"])

    def test_source_change_invalidates_cached_compile(self):
        for arm, filename, old, replacement in (
            ("meda", "policy.meda", 'payload: "unsupported"', 'payload: "changed"'),
            ("typescript", "policy.ts", 'payload: "unsupported"', 'payload: "changed"'),
        ):
            with self.subTest(arm=arm), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / filename
                path.write_text((ROOT / "clients" / filename).read_text())
                first = compile_client(arm, path)
                path.write_text(path.read_text().replace(old, replacement))
                second = compile_client(arm, path)
                self.assertNotEqual(first["sha256"], second["sha256"])
                self.assertEqual("changed", invoke_client(arm, snapshot(observation="future_state"), path)["payload"])

    def test_bridge_cli_is_usable_from_outside(self):
        value = snapshot(observation="completed", remaining=0)
        for arm in ARMS:
            with self.subTest(arm=arm):
                result = subprocess.run([sys.executable, str(ROOT / "clients.py"), arm],
                                        input=json.dumps(value), text=True, capture_output=True, timeout=20)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual({"action": "stop", "taskId": "t1", "payload": "evidence:42"}, json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
