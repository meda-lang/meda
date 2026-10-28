"""Public process supervision and CLI boundary, without SDK or peer fixtures."""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import shutil
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from meda_runtime import HostConfig, Limits, run_application
from meda_runtime.__main__ import load_config, main


def config(**changes):
    values = dict(mcp_url="https://mcp.test/mcp", a2a_url="https://agent.test/a2a",
                  mcp_token="MCP-PRIVATE-SENTINEL", a2a_token="A2A-PRIVATE-SENTINEL",
                  ca_file=ssl.get_default_verify_paths().cafile,
                  tool_descriptor={"name": "evidence.read"}, agent_card={"name": "report"},
                  principal="user-1", tenant="org-1", allowed_documents=frozenset({"doc-1"}),
                  limits=Limits(root_seconds=1, cleanup_seconds=.2))
    values.update(changes)
    return HostConfig(**values)


FINISH = "process.stdout.write(JSON.stringify({kind:'finish',result:{outcome:'Success'}})+'\\n');"


class PublicSupervisorTests(unittest.TestCase):
    def execute(self, source, settings=None, input_value=None):
        with tempfile.TemporaryDirectory() as directory:
            worker = Path(directory) / "worker.js"
            worker.write_text(source)
            receipt = run_application(settings or config(), [shutil.which("node"), str(worker)],
                                      {} if input_value is None else input_value, cwd=directory)
        self.assertTrue(receipt["worker"]["retired"])
        self.assertTrue(receipt["worker"]["supervisorJoined"])
        return receipt

    def test_success_waits_for_worker_exit_and_finishes_host_once(self):
        receipt = self.execute(FINISH + "setTimeout(()=>{},80);")
        self.assertEqual(receipt["result"]["outcome"], "Success")
        self.assertEqual(receipt["worker"]["returncode"], 0)
        self.assertEqual(receipt["worker"]["termination"], "normal")
        self.assertGreater(receipt["worker"]["retirementObservedAfterStartSeconds"], .07)
        self.assertEqual(sum(row["event"] == "publication" for row in receipt["trace"]), 1)
        self.assertEqual(receipt["profile"], "meda-evidence-runtime/1")
        self.assertEqual({row["name"] for row in receipt["observedChannelScan"]["channels"]},
                         {"applicationFinish", "stderr", "unexpectedStdout", "ordinaryHostTrace"})

    def test_nonzero_exit_and_live_worker_invalidate_success_proposal(self):
        for suffix, reason in (("process.exitCode=2;", "worker_failure"),
                               ("setInterval(()=>{},1000);", "worker_retirement_limit")):
            with self.subTest(reason=reason):
                receipt = self.execute(FINISH + suffix)
                self.assertNotEqual(receipt["result"]["outcome"], "Success")
                self.assertEqual(receipt["worker"]["termination"], reason)

    def test_deadline_retires_busy_worker(self):
        receipt = self.execute("while(true){}", config(limits=Limits(root_seconds=.15, cleanup_seconds=.2)))
        self.assertEqual(receipt["result"]["outcome"], "Timeout")
        self.assertEqual(receipt["worker"]["termination"], "deadline")

    def test_inherited_credentials_and_runtime_hooks_are_absent(self):
        source = "process.stdout.write(JSON.stringify({kind:'finish',result:{outcome:'Success',keys:Object.keys(process.env).sort()}})+'\\n');"
        with patch.dict(os.environ, {"MCP_TOKEN": "MCP-PRIVATE-SENTINEL", "A2A_TOKEN": "A2A-PRIVATE-SENTINEL",
                                     "PYTHONPATH": "/private/imports", "NODE_OPTIONS": "--trace-warnings"}):
            receipt = self.execute(source)
        self.assertEqual(receipt["result"]["keys"], ["LANG", "PATH"])
        self.assertFalse(receipt["credentialLeakDetected"])

    def test_malformed_frames_fail_before_publication(self):
        malformed = [
            '{"kind":"finish","kind":"finish","result":{"outcome":"Success"}}',
            '{"kind":"finish","result":{"outcome":"Success","data":NaN}}',
            '{"kind":"finish","result":{"outcome":"Success","data":1e999}}',
            '{"kind":"finish","result":{"outcome":"Success","data":"\\ud800"}}',
            '{"kind":"finish","result":{"outcome":"Success","\\ud800":1}}',
            '[' * 1000 + '0' + ']' * 1000,
        ]
        for raw in malformed:
            with self.subTest(raw=raw[:65]):
                receipt = self.execute("process.stdout.write(" + json.dumps(raw + "\n") + ");")
                self.assertEqual(receipt["worker"]["termination"], "invalid_frame")
                self.assertNotEqual(receipt["result"]["outcome"], "Success")

    def test_escaped_credentials_are_scanned_and_redacted_before_return(self):
        secret = 'PRIVATE"QUOTE\\BACKSLASH'
        source = ("process.stderr.write(JSON.stringify(" + json.dumps(secret) + "));"
                  "process.stdout.write(JSON.stringify({kind:'finish',result:{outcome:'Probe',leak:"
                  + json.dumps(secret) + "}})+'\\n');")
        receipt = self.execute(source, config(mcp_token=secret))
        self.assertTrue(receipt["credentialLeakDetected"])
        self.assertEqual(receipt["result"]["outcome"], "ProtocolRejected")
        channels = {row["name"]: row for row in receipt["observedChannelScan"]["channels"]}
        self.assertEqual(channels["applicationFinish"]["credentialMatches"], 1)
        self.assertEqual(channels["stderr"]["credentialMatches"], 1)
        self.assertEqual(receipt["worker"]["applicationFinish"]["leak"], "[REDACTED_CREDENTIAL]")
        self.assertNotIn(secret, json.dumps(receipt))
        self.assertNotIn(json.dumps(secret)[1:-1], json.dumps(receipt))

    def test_credentials_in_arguments_or_nested_input_are_rejected_before_host_creation(self):
        secret = 'PRIVATE"QUOTE\\BACKSLASH'
        settings = config(mcp_token=secret)
        cases = [([sys.executable, secret], {}), ([sys.executable], {"nested": ["prefix" + secret]}),
                 ([sys.executable], {"nested": [{secret: "value"}]})]
        with patch("meda_runtime.api.Host") as host:
            for command, value in cases:
                with self.subTest(value=value), self.assertRaises(ValueError) as caught:
                    run_application(settings, command, value)
                self.assertNotIn(secret, str(caught.exception))
            host.assert_not_called()

    def test_control_word_credentials_cannot_rewrite_owned_receipt_fields(self):
        for secret in ("trace", "credentialMatches", "normal"):
            with self.subTest(secret=secret):
                receipt = self.execute(FINISH, config(mcp_token=secret))
                self.assertEqual(receipt["result"]["outcome"], "Success")
                self.assertEqual(receipt["worker"]["termination"], "normal")
                self.assertFalse(receipt["credentialLeakDetected"])
                self.assertIn("trace", receipt)
                self.assertTrue(all("credentialMatches" in row for row in receipt["observedChannelScan"]["channels"]))

    def test_any_application_outcome_or_key_matching_a_secret_is_rejected_coherently(self):
        cases = [("Success", {"outcome": "Success"}),
                 ("DomainRejected", {"outcome": "DomainRejected"}),
                 ("CUSTOM-APPLICATION-OUTCOME-" + "x" * 80,
                  {"outcome": "CUSTOM-APPLICATION-OUTCOME-" + "x" * 80}),
                 ("PRIVATE-PAYLOAD-KEY", {"outcome": "Success", "nested": [{"PRIVATE-PAYLOAD-KEY": 1}]})]
        for secret, proposed in cases:
            source = "process.stdout.write(" + json.dumps(json.dumps({"kind": "finish", "result": proposed}) + "\n") + ");"
            with self.subTest(secret=secret):
                receipt = self.execute(source, config(mcp_token=secret))
                self.assertEqual(receipt["result"]["outcome"], "ProtocolRejected")
                self.assertTrue(receipt["result"]["fatal"])
                self.assertTrue(receipt["credentialLeakDetected"])
                self.assertEqual(receipt["trace"][-1]["outcome"], "ProtocolRejected")
                self.assertNotIn(secret, json.dumps(receipt))

    def test_reference_in_application_payload_is_rejected_before_publication(self):
        reference = "PRIVATE-REFERENCE-SENTINEL"
        source = ("process.stdin.once('data',()=>{process.stdout.write(JSON.stringify({kind:'call',id:1,"
                  "operation:'submit',arguments:{}})+'\\n');process.stdin.once('data',raw=>{"
                  "process.stdout.write(JSON.stringify({kind:'finish',result:{outcome:'Success',"
                  "leak:JSON.parse(raw).value.ref}})+'\\n');});});")
        with patch("meda_runtime.host.Host.call", return_value={"kind": "Task", "state": "Working", "ref": reference}):
            receipt = self.execute(source)
        self.assertEqual(receipt["result"]["outcome"], "ProtocolRejected")
        self.assertTrue(receipt["referenceLeakDetected"])
        self.assertNotIn(reference, json.dumps(receipt))

    def test_invalid_public_inputs_are_rejected_before_host_creation(self):
        deep = None
        for _ in range(18):
            deep = [deep]
        cases = [(config(), "python", {}), (config(), [sys.executable], float("nan")),
                 (config(), [sys.executable], {"bad": "\ud800"}),
                 (config(), [sys.executable], {"\ud800": "bad"}),
                 (config(), [sys.executable], deep), (config(), [sys.executable], "x" * 65536),
                 (replace(config(), expected_revision=2), [sys.executable], {})]
        with patch("meda_runtime.api.Host") as host:
            for settings, command, value in cases:
                with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                    run_application(settings, command, value)
            host.assert_not_called()

    def test_bad_ca_is_normalized_as_a_prelaunch_error(self):
        with self.assertRaises(ValueError) as caught:
            run_application(config(ca_file="/PRIVATE-CA-PATH/missing.pem"), [sys.executable], {})
        self.assertEqual(str(caught.exception), "Runtime configuration could not be initialized")

    def test_process_launch_failure_is_a_fixed_exception_without_receipt(self):
        with patch("meda_runtime.supervisor.subprocess.Popen", side_effect=OSError("PRIVATE-ERROR")):
            with self.assertRaises(RuntimeError) as caught:
                run_application(config(), [sys.executable], {})
        self.assertNotIn("PRIVATE-ERROR", str(caught.exception))


class CommandLineTests(unittest.TestCase):
    def write_config(self, directory, **changes):
        settings = config()
        value = {name: getattr(settings, name) for name in
                 ("mcp_url", "a2a_url", "ca_file", "tool_descriptor", "agent_card", "principal", "tenant")}
        value.update(mcp_token_env="TEST_MCP_TOKEN", a2a_token_env="TEST_A2A_TOKEN", allowed_documents=["doc-1"])
        value.update(changes)
        path = Path(directory) / "config.json"
        path.write_text(json.dumps(value))
        return path

    def test_environment_references_resolve_only_in_trusted_config(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                "TEST_MCP_TOKEN": "MCP-PRIVATE-SENTINEL", "TEST_A2A_TOKEN": "A2A-PRIVATE-SENTINEL"}):
            path = self.write_config(directory)
            settings = load_config(path)
            self.assertEqual(settings.mcp_token, "MCP-PRIVATE-SENTINEL")
            self.assertNotIn(settings.mcp_token, repr(settings))
            worker = Path(directory) / "worker.js"
            worker.write_text(FINISH)
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(["--config", str(path), "--", shutil.which("node"), str(worker)])
            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(json.loads(stdout.getvalue())["result"]["outcome"], "Success")

    def test_config_requires_explicit_authority_and_rejects_literal_tokens(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                "TEST_MCP_TOKEN": "MCP-PRIVATE-SENTINEL", "TEST_A2A_TOKEN": "A2A-PRIVATE-SENTINEL"}):
            path = self.write_config(directory)
            original = json.loads(path.read_text())
            for key in ("principal", "tenant", "allowed_documents", "mcp_token_env", "a2a_token_env"):
                value = dict(original)
                del value[key]
                path.write_text(json.dumps(value))
                with self.subTest(missing=key), self.assertRaises(ValueError):
                    load_config(path)
            path.write_text(json.dumps(dict(original, mcp_token="PRIVATE-LITERAL")))
            with self.assertRaises(ValueError):
                load_config(path)

    def test_cli_errors_never_echo_paths_arguments_or_exceptions(self):
        for argv in (["--config", "/PRIVATE-CONFIG/missing.json", "--", "PRIVATE-COMMAND"],
                     ["--UNKNOWN-PRIVATE-ARGUMENT"]):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(argv)
            self.assertEqual(code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(json.loads(stderr.getvalue()), {"error": "ConfigurationInvalid"})


if __name__ == "__main__":
    unittest.main()
