"""Actual process supervisor probes, independent of protocol interoperability."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host import Limits
from runner import MAX_LINE, _channel_scan, run_client


class RecordingHost:
    def __init__(self, response=None, seconds=.5):
        self.limits = Limits(root_seconds=seconds, cleanup_seconds=.2)
        self.deadline = time.monotonic() + seconds
        self.closed = False
        self.fatal = None
        self.calls = []
        self.finishes = 0
        self.response = response or {"kind": "Error", "code": "AuthorityDenied", "fatal": False,
                                     "remoteOutcome": "NotStarted"}

    def call(self, operation, arguments):
        self.calls.append((operation, arguments))
        if self.response.get("fatal"):
            self.fatal = {"outcome": self.response["code"], "fatal": True}
        return self.response

    def abort(self, code="RootTerminated"):
        self.closed = True
        self.fatal = {"outcome": code, "fatal": True}

    def finish(self, proposed):
        self.finishes += 1
        self.closed = True
        return {"result": self.fatal or proposed, "cleanup": [], "trace": []}


CALL = "process.stdout.write(JSON.stringify({kind:'call',id:1,operation:'readEvidence',arguments:{documentId:'evidence-42'}})+'\\n');"


class RunnerSupervisorTests(unittest.TestCase):
    def execute(self, source, host=None, **kwargs):
        host = host or RecordingHost()
        with tempfile.TemporaryDirectory() as directory:
            worker = Path(directory) / "worker.js"
            worker.write_text(source)
            receipt = run_client(host, {}, worker_path=worker, **kwargs)
        self.assertTrue(receipt["worker"]["retired"])
        self.assertTrue(receipt["worker"]["supervisorJoined"])
        self.assertEqual(host.finishes, 1)
        return receipt, host

    def test_worker_environment_is_scrubbed(self):
        source = "process.stdout.write(JSON.stringify({kind:'finish',result:{outcome:'Probe',keys:Object.keys(process.env).sort()}})+'\\n');"
        with patch.dict(os.environ, {"D0_TEST_SECRET": "never-in-worker", "NODE_OPTIONS": "--trace-warnings"}):
            receipt, _ = self.execute(source)
        self.assertEqual(receipt["worker"]["applicationFinish"]["keys"], ["LANG", "PATH"])
        self.assertEqual(receipt["worker"]["termination"], "normal")

    def test_deadline_retires_busy_worker(self):
        receipt, _ = self.execute("while(true){}", RecordingHost(seconds=.2))
        self.assertEqual(receipt["result"]["outcome"], "Timeout")
        self.assertEqual(receipt["worker"]["termination"], "deadline")
        self.assertLess(receipt["worker"]["elapsedSeconds"], 1.5)

    def test_rss_measures_actual_node_process_in_this_pid_namespace(self):
        receipt, _ = self.execute("global.buf=Buffer.alloc(40*1024*1024,1);setInterval(()=>{},1000);",
                                  RecordingHost(seconds=.25))
        self.assertGreater(receipt["worker"]["peakRssBytesObserved"], 40 * 1024 * 1024)

    def test_sampled_rss_limit_retires_native_buffer_allocation(self):
        receipt, _ = self.execute("global.buf=Buffer.alloc(300*1024*1024,1);setInterval(()=>{},1000);",
                                  RecordingHost(seconds=2))
        self.assertEqual(receipt["worker"]["termination"], "memory_limit")
        self.assertGreater(receipt["worker"]["peakRssBytesObserved"], 256 * 1024 * 1024)
        self.assertEqual(receipt["result"]["outcome"], "RootTerminated")

    def test_fatal_host_return_never_resumes_source(self):
        source = "process.stdin.once('data',()=>{" + CALL + "process.stdin.once('data',()=>{process.stdout.write(JSON.stringify({kind:'finish',result:{outcome:'ForbiddenResume'}})+'\\n');});});"
        host = RecordingHost({"kind": "Error", "code": "Timeout", "fatal": True, "remoteOutcome": "Unknown"})
        receipt, _ = self.execute(source, host)
        self.assertEqual(receipt["result"]["outcome"], "Timeout")
        self.assertEqual(receipt["worker"]["termination"], "fatal_host_outcome")
        self.assertEqual(receipt["worker"]["finishFrames"], 0)
        self.assertEqual(receipt["worker"]["responsesAfterFatal"], 0)

    def test_blocked_stdin_does_not_block_deadline(self):
        source = CALL + "while(true){}"
        host = RecordingHost({"kind": "Evidence", "value": "x" * 60_000}, seconds=.2)
        receipt, _ = self.execute(source, host)
        self.assertEqual(receipt["worker"]["termination"], "deadline")
        self.assertLess(receipt["worker"]["elapsedSeconds"], 1.5)

    def test_non_string_operation_has_controlled_outcome(self):
        for operation in ([], {}):
            with self.subTest(operation=operation):
                frame = {"kind": "call", "id": 1, "operation": operation, "arguments": {}}
                source = "process.stdout.write(" + json.dumps(json.dumps(frame) + "\n") + ");setInterval(()=>{},1000);"
                receipt, host = self.execute(source)
                self.assertEqual(receipt["worker"]["termination"], "invalid_call")
                self.assertEqual(host.calls, [])

    def test_duplicate_finish_is_not_published_as_success(self):
        frame = json.dumps({"kind": "finish", "result": {"outcome": "Success"}}) + "\n"
        receipt, _ = self.execute("process.stdout.write(" + json.dumps(frame + frame) + ");")
        self.assertEqual(receipt["worker"]["termination"], "output_after_finish")
        self.assertEqual(receipt["worker"]["finishFrames"], 2)
        self.assertNotEqual(receipt["result"]["outcome"], "Success")

    def test_oversize_stdout_is_retired_and_capture_is_bounded(self):
        receipt, _ = self.execute("process.stdout.write('x'.repeat(100000));setInterval(()=>{},1000);")
        self.assertEqual(receipt["worker"]["termination"], "frame_limit")
        self.assertTrue(receipt["worker"]["outputTruncated"])
        self.assertLessEqual(len(''.join(receipt["worker"]["unexpectedStdout"])), MAX_LINE)

    def test_observable_channels_are_scanned_before_redaction(self):
        ref, credential = "private-reference-sentinel", "private-credential-sentinel"
        source = "process.stdin.once('data',()=>{" + CALL + "process.stdin.once('data',()=>{process.stderr.write(" + json.dumps(credential) + ");process.stdout.write(JSON.stringify({kind:'finish',result:{outcome:'Probe',leak:" + json.dumps(ref) + "}})+'\\n');});});"
        private = {}
        host = RecordingHost({"kind": "Task", "ref": ref, "state": "Working"})
        receipt, _ = self.execute(source, host, credential_sentinels=[credential], private_receipts=private)
        scan = _channel_scan(private["channels"], [credential], private["references"], private["complete"])
        by_name = {row["name"]: row for row in scan["channels"]}
        self.assertEqual(by_name["applicationFinish"]["referenceMatches"], 1)
        self.assertEqual(by_name["stderr"]["credentialMatches"], 1)
        self.assertEqual(scan["referenceSentinelCount"], 1)
        self.assertTrue(scan["complete"])
        self.assertNotIn(ref, json.dumps(receipt))
        self.assertNotIn(credential, json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
