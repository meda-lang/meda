"""Outside-in TLS tests against real upstream SDK servers, not in-process mocks."""
from __future__ import annotations

import copy
import http.client
import importlib.metadata
import json
import ssl
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from sdk_peers import EVIDENCE, build_agent_card, build_tool_descriptor
from support import certificates, credentials, free_port, peer, read_witness


class UpstreamPeerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="meda-sdk-peers-")
        self.directory = Path(self.temporary.name)
        self.certs = certificates(self.directory)

    def tearDown(self):
        self.temporary.cleanup()

    def config(self, protocol, **changes):
        config = {"protocol": protocol, "port": free_port(), **self.certs,
                  "credentials": credentials(protocol),
                  "witness_path": str(self.directory / (protocol + ".jsonl"))}
        return {**config, **changes}

    def request(self, config, method, params=None, label="valid", overrides=None):
        token = next(r["token"] for r in config["credentials"] if r["label"] == label)
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if method == "card":
            path, verb, body = "/.well-known/agent-card.json", "GET", None
        else:
            params = copy.deepcopy(params or {})
            path = "/mcp" if config["protocol"] == "mcp" else "/a2a"
            verb = "POST"
            if config["protocol"] == "mcp":
                params["_meta"] = {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientInfo": {"name": "external-test", "version": "1"},
                    "io.modelcontextprotocol/clientCapabilities": {},
                    "progressToken": "test-progress",
                }
                headers.update({"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": method})
                if method == "tools/call":
                    headers.update({"Mcp-Name": params["name"],
                                    "Mcp-Param-DocumentId": params["arguments"]["documentId"]})
            else:
                headers["A2A-Version"] = "1.0"
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        headers.update(overrides or {})
        context = ssl.create_default_context(cafile=config["ca_file"])
        connection = http.client.HTTPSConnection("127.0.0.1", config["port"], context=context, timeout=4)
        try:
            connection.request(verb, path, body, headers)
            response = connection.getresponse()
            raw = response.read().decode()
            if "text/event-stream" in response.getheader("Content-Type", ""):
                data = [json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith("data:")]
                result = next(row for row in data if row.get("id") == 1)
            else:
                try:
                    result = json.loads(raw)
                except ValueError:
                    result = {"raw": raw}
            return response.status, result, response.getheader("Content-Type", "")
        finally:
            connection.close()

    def send(self, **data):
        return {"message": {"messageId": "test-message", "role": "ROLE_USER",
                            "parts": [{"data": data}]}, "configuration": {"returnImmediately": True}}

    def test_mcp_sdk_json_discovery_headers_and_authentication(self):
        self.assertEqual(importlib.metadata.version("mcp"), "2.3.0")
        config = self.config("mcp")
        with peer(config, self.directory):
            status, result, _ = self.request(config, "server/discover")
            self.assertEqual(status, 200)
            self.assertEqual(result["result"]["resultType"], "complete")
            status, result, _ = self.request(config, "tools/list")
            self.assertEqual(result["result"]["tools"], [build_tool_descriptor()])
            params = {"name": "evidence.read", "arguments": {"documentId": "evidence-42"}}
            status, result, _ = self.request(config, "tools/call", params)
            self.assertEqual(status, 200)
            self.assertEqual(result["result"]["structuredContent"], EVIDENCE)
            for label in ["expired", "wrong_audience"]:
                status, _, _ = self.request(config, "tools/call", params, label=label)
                self.assertEqual(status, 401)
            status, result, _ = self.request(config, "tools/call", params,
                overrides={"Mcp-Param-DocumentId": "other-document"})
            self.assertEqual(status, 400)
            self.assertIn("error", result)
            status, _, _ = self.request(config, "tools/call", params,
                overrides={"Origin": "https://untrusted.example"})
            self.assertEqual(status, 403)
        rows = read_witness(config["witness_path"])
        self.assertEqual(sum(row["event"] == "evidence_read" for row in rows), 1)
        text = Path(config["witness_path"]).read_text()
        self.assertTrue(all(row["token"] not in text for row in config["credentials"]))

    def test_mcp_sdk_request_scoped_sse(self):
        config = self.config("mcp", json_response=False)
        with peer(config, self.directory):
            status, result, media = self.request(config, "tools/call",
                {"name": "evidence.read", "arguments": {"documentId": "evidence-42"}})
            self.assertEqual(status, 200)
            self.assertIn("text/event-stream", media)
            self.assertEqual(result["result"]["structuredContent"], EVIDENCE)

    def test_mcp_sdk_live_stream_disconnect_cancels_handler(self):
        config = self.config("mcp", json_response=False, scenario="live_progress")
        with peer(config, self.directory):
            token = next(row["token"] for row in config["credentials"] if row["label"] == "valid")
            headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json",
                       "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28",
                       "Mcp-Method": "tools/call", "Mcp-Name": "evidence.read",
                       "Mcp-Param-DocumentId": "evidence-42"}
            params = {"name": "evidence.read", "arguments": {"documentId": "evidence-42"},
                      "_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
                                "io.modelcontextprotocol/clientInfo": {"name": "disconnect-test", "version": "1"},
                                "io.modelcontextprotocol/clientCapabilities": {}, "progressToken": "live-test"}}
            connection = http.client.HTTPSConnection("127.0.0.1", config["port"], timeout=3,
                context=ssl.create_default_context(cafile=config["ca_file"]))
            response = None
            try:
                connection.request("POST", "/mcp", json.dumps({"jsonrpc": "2.0", "id": 1,
                                   "method": "tools/call", "params": params}), headers)
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn("text/event-stream", response.getheader("Content-Type", ""))
                # Read one real SDK progress event, then close before the result.
                for _ in range(8):
                    line = response.readline()
                    if line.startswith(b"data:"):
                        event = json.loads(line[5:])
                        break
                else:
                    self.fail("No SDK progress notification")
                self.assertEqual(event["method"], "notifications/progress")
                self.assertEqual(event["params"]["progressToken"], "live-test")
            finally:
                if response is not None:
                    response.close()
                connection.close()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                rows = read_witness(config["witness_path"])
                if any(row["event"] == "stream_terminated" for row in rows):
                    break
                time.sleep(.02)
            # This assertion executes while the peer process is still alive.
            # Its later shutdown therefore cannot supply the cancellation proof.
            self.assertEqual(sum(row["event"] == "stream_cancelled" for row in rows), 1)
            self.assertEqual([row["completed"] for row in rows if row["event"] == "stream_terminated"], [False])

    def test_a2a_sdk_lifecycle_and_cross_principal_ownership(self):
        self.assertEqual(importlib.metadata.version("a2a-sdk"), "1.2.3")
        config = self.config("a2a")
        with peer(config, self.directory):
            status, card, _ = self.request(config, "card")
            self.assertEqual(card, build_agent_card(f"https://127.0.0.1:{config['port']}/a2a"))
            status, value, _ = self.request(config, "SendMessage",
                self.send(kind="evidence-report", evidence=EVIDENCE, includeIds=["f1", "f2"]))
            self.assertEqual(status, 200)
            task = value["result"]["task"]
            self.assertEqual(task["status"]["state"], "TASK_STATE_WORKING")
            status, foreign, _ = self.request(config, "GetTask", {"id": task["id"]}, label="foreign")
            self.assertEqual(foreign["error"]["code"], -32001)
            status, observed, _ = self.request(config, "GetTask", {"id": task["id"]})
            completed = observed["result"]
            self.assertEqual(completed["status"]["state"], "TASK_STATE_COMPLETED")
            self.assertEqual(completed["artifacts"][0]["parts"][0]["data"]["selected"], EVIDENCE["facts"])
            status, canceled, _ = self.request(config, "CancelTask", {"id": task["id"]})
            self.assertEqual(canceled["error"]["code"], -32002)
            _, wrong_version, _ = self.request(config, "GetTask", {"id": task["id"]},
                                               overrides={"A2A-Version": "0.3"})
            self.assertEqual(wrong_version["error"]["code"], -32009)
        rows = read_witness(config["witness_path"])
        self.assertEqual(sum(r["event"] == "created" for r in rows), 1)
        self.assertEqual(sum(r["event"] == "task_access_denied" for r in rows), 1)

    def test_a2a_sdk_clarification_and_explicit_cancel(self):
        config = self.config("a2a")
        with peer(config, self.directory):
            _, value, _ = self.request(config, "SendMessage", self.send(kind="evidence-report", evidence=EVIDENCE))
            task = value["result"]["task"]
            self.assertEqual(task["status"]["state"], "TASK_STATE_INPUT_REQUIRED")
            followup = self.send(includeIds=["f1", "f2"])
            followup["message"].update({"taskId": task["id"], "contextId": task["contextId"], "messageId": "reply"})
            _, resumed, _ = self.request(config, "SendMessage", followup)
            self.assertEqual(resumed["result"]["task"]["id"], task["id"])
            self.assertEqual(resumed["result"]["task"]["status"]["state"], "TASK_STATE_COMPLETED")
            _, pending, _ = self.request(config, "SendMessage", self.send(kind="evidence-report", evidence=EVIDENCE))
            _, canceled, _ = self.request(config, "CancelTask", {"id": pending["result"]["task"]["id"]})
            self.assertEqual(canceled["result"]["status"]["state"], "TASK_STATE_CANCELED")
        rows = read_witness(config["witness_path"])
        self.assertEqual(sum(r["event"] == "created" for r in rows), 2)
        self.assertEqual([r["includeIds"] for r in rows if r["event"] == "continued"], [["f1", "f2"]])
        self.assertEqual(sum(r["event"] == "canceled" for r in rows), 1)

    def test_a2a_sdk_completion_before_cancel_refuses_cancel(self):
        config = self.config("a2a", scenario="completion_before_cancel")
        with peer(config, self.directory):
            _, initial, _ = self.request(config, "SendMessage",
                self.send(kind="evidence-report", evidence=EVIDENCE, includeIds=["f1", "f2"]))
            task = initial["result"]["task"]
            self.assertEqual(task["status"]["state"], "TASK_STATE_WORKING")
            _, refused, _ = self.request(config, "CancelTask", {"id": task["id"]})
            self.assertEqual(refused["error"]["code"], -32002)
            _, observed, _ = self.request(config, "GetTask", {"id": task["id"]})
            self.assertEqual(observed["result"]["status"]["state"], "TASK_STATE_COMPLETED")
        rows = read_witness(config["witness_path"])
        self.assertEqual(sum(row["event"] == "completed_before_cancel" for row in rows), 1)
        self.assertEqual(sum(row["event"] == "cancel_refused" for row in rows), 1)
        self.assertFalse(any(row["event"] == "canceled" for row in rows))


if __name__ == "__main__":
    unittest.main()
