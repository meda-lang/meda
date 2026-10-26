"""Actual compiler/Node worker checks; fake controller cases are not wire conformance."""
from __future__ import annotations

import json
from pathlib import Path
import selectors
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / "node_modules/typescript/bin/tsc"
EVIDENCE = {"documentId": "evidence-42", "revision": 1,
            "facts": [{"id": "f1", "value": "blue"}, {"id": "f2", "value": "square"}]}
REPORT = {"documentId": "evidence-42", "revision": 1,
          "selected": [{"id": "f1", "value": "blue"}, {"id": "f2", "value": "square"}]}


class TypeScriptClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not COMPILER.is_file():
            raise RuntimeError("Pinned TypeScript compiler is required; run npm ci --ignore-scripts")
        version = subprocess.run(["node", str(COMPILER), "--version"], check=True,
                                 text=True, capture_output=True, timeout=10)
        if version.stdout.strip() != "Version 5.9.3":
            raise RuntimeError("Unexpected compiler version")
        subprocess.run(["node", str(COMPILER), "-p", "tsconfig.json"], cwd=ROOT,
                       text=True, capture_output=True, check=True, timeout=30)

    def node(self, source: str):
        result = subprocess.run(["node", "-e", source], cwd=ROOT, text=True,
                                capture_output=True, check=True, timeout=10)
        return json.loads(result.stdout)

    def worker(self, replies, input_value=None, corrupt_id=False):
        process = subprocess.Popen(["node", "dist/main.js"], cwd=ROOT, text=True,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, bufsize=1)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        calls = []
        final = None
        deadline = time.monotonic() + 8
        try:
            process.stdin.write(json.dumps({"kind": "start", "input": input_value or {}}) + "\n")
            process.stdin.flush()
            while time.monotonic() < deadline:
                if not selector.select(max(0, deadline - time.monotonic())):
                    self.fail("Worker stalled")
                line = process.stdout.readline()
                if not line:
                    self.fail("Worker exited before finish")
                frame = json.loads(line)
                if frame["kind"] == "finish":
                    final = frame["result"]
                    break
                self.assertEqual(frame["kind"], "call")
                calls.append(frame)
                self.assertLessEqual(len(calls), len(replies), "Unexpected additional host call")
                value = replies[len(calls) - 1]
                process.stdin.write(json.dumps({"kind": "response", "id": frame["id"] + int(corrupt_id),
                                                "value": value}) + "\n")
                process.stdin.flush()
            self.assertIsNotNone(final)
            process.stdin.close()
            process.wait(timeout=3)
            self.assertEqual(process.stdout.read(), "", "Duplicate finish or other stdout")
            self.assertEqual(process.stderr.read(), "")
            return final, calls, process.returncode
        finally:
            selector.close()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream and not stream.closed:
                    stream.close()

    def test_domain_validation_rejects_wrong_values_order_duplicates_and_extras(self):
        cases = [REPORT,
                 {**REPORT, "revision": 2},
                 {**REPORT, "selected": list(reversed(REPORT["selected"]))},
                 {**REPORT, "selected": [{"id": "f1", "value": "green"}, REPORT["selected"][1]]},
                 {**REPORT, "selected": [REPORT["selected"][0], REPORT["selected"][0]]},
                 {**REPORT, "unrequested": True},
                 {**REPORT, "selected": [{**REPORT["selected"][0], "extra": 1}, REPORT["selected"][1]]},
                 {**REPORT, "selected": REPORT["selected"][:1]},
                 None]
        got = self.node("const d=require('./dist/domain'); const e=d.decodeEvidence(" + json.dumps(EVIDENCE) +
                        ", 'evidence-42'); console.log(JSON.stringify(" + json.dumps(cases) +
                        ".map(r=>d.validateReport(r,e,['f1','f2'])!==null)));")
        self.assertEqual(got, [True] + [False] * (len(cases) - 1))

    def test_private_references_do_not_serialize_or_restore_authority(self):
        got = self.node("""
          const {createBindings}=require('./dist/bindings');
          (async()=>{
            const calls=[];
            const b=createBindings(async(op,args)=>{calls.push([op,args]);
              return {kind:'Task', ref:'private-token', state:'Working'};});
            const t=await b.host.submit({documentId:'x',revision:1,facts:[]});
            const serialized=JSON.stringify(t.ref);
            const restored=await b.host.observe(JSON.parse(serialized));
            const valid=await b.host.observe(t.ref);
            const other=createBindings(async()=>{throw Error('must not call');});
            const foreign=await other.host.observe(t.ref);
            b.close();
            const closed=await b.host.observe(t.ref);
            console.log(JSON.stringify({serialized,keys:Object.keys(t.ref),restored,valid:valid.kind,
              foreign,closed,calls}));
          })().catch(()=>{process.exitCode=1;});
        """)
        self.assertEqual(got["serialized"], "{}")
        self.assertEqual(got["keys"], [])
        self.assertEqual(got["valid"], "Task")
        for key in ("restored", "foreign", "closed"):
            self.assertEqual(got[key]["code"], "InvalidReference")
        self.assertEqual([item[0] for item in got["calls"]], ["submit", "observe"])
        self.assertEqual(got["calls"][1][1], {"ref": "private-token"})

    def test_real_worker_success_and_domain_rejection(self):
        for artifact, expected in [(REPORT, "Success"), ({**REPORT, "revision": 9}, "DomainRejected")]:
            with self.subTest(expected=expected):
                final, calls, code = self.worker([
                    {"kind": "Evidence", "value": EVIDENCE},
                    {"kind": "Task", "ref": "t", "state": "Completed", "artifact": artifact}])
                self.assertEqual(final["outcome"], expected)
                self.assertEqual([c["operation"] for c in calls], ["readEvidence", "submit"])
                self.assertEqual(code, 0)
                if expected == "Success":
                    self.assertEqual(final["report"], REPORT)
                else:
                    self.assertNotIn("report", final)

    def test_worker_continues_same_reference_once_or_returns_needs_input(self):
        initial = [{"kind": "Evidence", "value": EVIDENCE},
                   {"kind": "Task", "ref": "same-task", "state": "InputRequired"}]
        final, calls, _ = self.worker(initial, {"requestClarification": True})
        self.assertEqual(final["outcome"], "NeedsInput")
        self.assertNotIn("includeIds", calls[1]["arguments"])
        final, calls, _ = self.worker(initial + [
            {"kind": "Task", "ref": "same-task", "state": "InputRequired"}],
            {"requestClarification": True, "suppliedInput": ["f1", "f2"]})
        self.assertEqual(final["outcome"], "NeedsInput")
        self.assertEqual(calls[2]["arguments"], {"ref": "same-task", "includeIds": ["f1", "f2"]})
        self.assertEqual([c["operation"] for c in calls], ["readEvidence", "submit", "provideInput"])

    def test_uncertain_submission_stops_without_resubmission(self):
        final, calls, _ = self.worker([
            {"kind": "Evidence", "value": EVIDENCE},
            {"kind": "Error", "code": "TransportFailure", "remoteOutcome": "Unknown", "fatal": False}])
        self.assertEqual(final, {"outcome": "TransportFailure", "remoteOutcome": "Unknown", "fatal": False})
        self.assertEqual([c["operation"] for c in calls], ["readEvidence", "submit"])

    def test_polls_are_bounded_and_terminal_states_remain_distinct(self):
        working = {"kind": "Task", "ref": "t", "state": "Working"}
        final, calls, _ = self.worker([{"kind": "Evidence", "value": EVIDENCE}, working,
                                      working, working, working])
        self.assertEqual(final["outcome"], "PollLimit")
        self.assertEqual(sum(c["operation"] == "observe" for c in calls), 3)
        for state, outcome in [("AuthRequired", "AuthorizationRequired"), ("Failed", "RemoteFailed"),
                               ("Canceled", "RemoteCanceled"), ("Rejected", "RemoteRejected")]:
            with self.subTest(state=state):
                final, calls, _ = self.worker([{"kind": "Evidence", "value": EVIDENCE},
                                               {"kind": "Task", "ref": "t", "state": state}])
                self.assertEqual(final["outcome"], outcome)
                self.assertEqual(len(calls), 2)

    def test_explicit_cancel_keeps_normal_host_call_semantics(self):
        final, calls, _ = self.worker([{"kind": "Evidence", "value": EVIDENCE},
            {"kind": "Task", "ref": "t", "state": "Working"},
            {"kind": "Task", "ref": "t", "state": "Canceled"}], {"cancelAfterSubmit": True})
        self.assertEqual(final["outcome"], "RemoteCanceled")
        self.assertEqual([c["operation"] for c in calls], ["readEvidence", "submit", "cancel"])

    def test_cancel_refusal_retains_remote_completed_delivery(self):
        final, calls, _ = self.worker([{"kind": "Evidence", "value": EVIDENCE},
            {"kind": "Task", "ref": "t", "state": "Working"},
            {"kind": "Error", "code": "TaskNotCancelable", "remoteOutcome": "Completed", "fatal": False}],
            {"cancelAfterSubmit": True})
        self.assertEqual(final, {"outcome": "TaskNotCancelable", "remoteOutcome": "Completed", "fatal": False})
        self.assertEqual([c["operation"] for c in calls], ["readEvidence", "submit", "cancel"])

    def test_wrong_controller_correlation_terminates_without_leaking_raw_error(self):
        final, calls, code = self.worker([{"kind": "Evidence", "value": EVIDENCE}], corrupt_id=True)
        self.assertEqual(final, {"outcome": "ProtocolRejected", "remoteOutcome": "Unknown", "fatal": True})
        self.assertEqual(len(calls), 1)
        self.assertEqual(code, 1)

    def test_actual_checker_rejects_forged_reference_and_invalid_operation(self):
        probes = [("const x: TaskRef = {};", False),
                  ("const x: Operation = 'retry';", False),
                  ("const x: Operation = 'observe';", True)]
        with tempfile.TemporaryDirectory(prefix="ts-probe-", dir=ROOT) as tmp:
            path = Path(tmp) / "probe.ts"
            for source, accepted in probes:
                path.write_text("import type {TaskRef, Operation} from '../client/bindings';\n" + source)
                checked = subprocess.run(["node", str(COMPILER), "--strict", "--noEmit",
                    "--target", "ES2022", "--module", "commonjs", "--moduleResolution", "node",
                    "--lib", "ES2022", "--skipLibCheck", "--types", "node", str(path)],
                    cwd=ROOT, capture_output=True, text=True, timeout=20)
                self.assertEqual(checked.returncode == 0, accepted, checked.stdout + checked.stderr)


if __name__ == "__main__":
    unittest.main()
