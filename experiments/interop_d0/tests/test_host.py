import base64
import copy
import json
import sys
import unittest
import threading
import socket
import ssl
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host import Host, HostConfig, HostError, Limits, encode_header_value, validate_tool_descriptor
from transport import HTTPSTransport, Response, TransportError, decode_json


EVIDENCE = {"documentId": "evidence-42", "revision": 1,
            "facts": [{"id": "f1", "value": "blue"}, {"id": "f2", "value": "square"}]}
TOOL = {"name": "evidence.read", "inputSchema": {"type": "object", "properties": {
    "documentId": {"type": "string", "x-mcp-header": "DocumentId"}}}, "outputSchema": {"type": "object"}}
CARD = {"name": "report", "supportedInterfaces": [{"url": "https://agent.test/rpc",
    "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}], "capabilities": {}}


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


class PeerDouble:
    """Unit fake with recorded wire requests; integration uses real upstream peers."""
    def __init__(self):
        self.requests = []
        self.tool, self.card = copy.deepcopy(TOOL), copy.deepcopy(CARD)
        self.state = "TASK_STATE_WORKING"
        self.drop = None
        self.wrong_id = False
        self.no_result_type = False
        self.cancel_refusal = False
        self.status = 200
        self.task_count = 0

    def request(self, verb, url, headers, body, **options):
        if options.get("on_dispatch"):
            options["on_dispatch"]()
        request = json.loads(body) if body else None
        method = request["method"] if request else "card"
        self.requests.append((method, request, dict(headers), options))
        if self.status != 200:
            return Response(self.status, None, 0)
        if method == "card":
            return Response(200, copy.deepcopy(self.card), 100)
        if method == "tools/list":
            result = {"resultType": "complete", "tools": [copy.deepcopy(self.tool)]}
        elif method == "tools/call":
            result = {"resultType": "complete", "content": [], "structuredContent": copy.deepcopy(EVIDENCE)}
        else:
            if method == "SendMessage" and "taskId" not in request["params"]["message"]:
                self.task_count += 1
            if self.drop == method:
                raise TransportError("TransportFailure", dispatched=True)
            if method == "CancelTask" and self.cancel_refusal:
                return Response(200, {"jsonrpc": "2.0", "id": request["id"],
                    "error": {"code": -32002, "message": "private upstream detail"}}, 100)
            state = "TASK_STATE_CANCELED" if method == "CancelTask" else self.state
            task = {"id": "task-1", "contextId": "context-1", "status": {"state": state}}
            result = {"task": task} if method == "SendMessage" else task
        if self.no_result_type:
            result.pop("resultType", None)
        return Response(200, {"jsonrpc": "2.0", "id": "wrong" if self.wrong_id else request["id"], "result": result}, 100)


def make_host(peer=None, **kwargs):
    clock = Clock()
    config = HostConfig("https://mcp.test/mcp", "https://agent.test/rpc", "MCP-SECRET",
                        "A2A-SECRET", "/unused", TOOL, CARD, **kwargs)
    peer = peer or PeerDouble()
    return Host(config, transport=peer, clock=clock, sleep=clock.sleep), peer, clock


def submit(host):
    evidence = host.call("readEvidence", {"documentId": "evidence-42"})
    assert evidence["kind"] == "Evidence", evidence
    return host.call("submit", {"evidence": evidence["value"], "includeIds": ["f1", "f2"]})


class HostBoundaryTests(unittest.TestCase):
    def test_authority_denied_before_discovery(self):
        host, peer, _ = make_host(grants=frozenset())
        self.assertEqual(host.call("readEvidence", {"documentId": "evidence-42"})["code"], "AuthorityDenied")
        self.assertEqual(peer.requests, [])

    def test_explicit_duplicate_after_unknown_does_not_dispatch(self):
        peer = PeerDouble(); peer.drop = "SendMessage"
        host, _, _ = make_host(peer)
        result = submit(host)
        self.assertEqual((result["code"], result["remoteOutcome"]), ("TransportFailure", "Unknown"))
        before = len(peer.requests)
        result = host.call("submit", {"evidence": EVIDENCE, "includeIds": ["f1"]})
        self.assertEqual(result["code"], "BudgetDenied")
        self.assertEqual((len(peer.requests), peer.task_count), (before, 1))

    def test_deadline_after_peer_creation_without_response_stays_unknown(self):
        host, peer, clock = make_host()
        original = peer.request
        def expire_after_submission(verb, url, headers, body, **options):
            request = json.loads(body) if body else {}
            if request.get("method") == "SendMessage":
                options["on_dispatch"]()
                peer.task_count += 1
                clock.now = 16
                options["check_live"]()
                self.fail("expired root resumed after dispatch")
            return original(verb, url, headers, body, **options)
        peer.request = expire_after_submission
        result = submit(host)
        self.assertEqual(peer.task_count, 1)
        self.assertEqual((result["code"], result["remoteOutcome"], result["fatal"]), ("Timeout", "Unknown", True))
        terminal = host.finish({"outcome": "Success"})
        self.assertEqual((terminal["result"]["outcome"], terminal["result"]["remoteOutcome"]), ("Timeout", "Unknown"))

    def test_malformed_state_after_peer_creation_stays_unknown(self):
        host, peer, _ = make_host()
        original = peer.request
        def malformed_state(verb, url, headers, body, **options):
            response = original(verb, url, headers, body, **options)
            if body and json.loads(body)["method"] == "SendMessage":
                response.value["result"]["task"]["status"]["state"] = []
            return response
        peer.request = malformed_state
        result = submit(host)
        self.assertEqual(peer.task_count, 1)
        self.assertEqual((result["code"], result["remoteOutcome"]), ("ProtocolRejected", "Unknown"))

    def test_malformed_a2a_content_cannot_publish_an_artifact_or_reference(self):
        report = {"documentId": "evidence-42", "revision": 1, "selected": []}
        variants = [
            {"artifactId": "a1", "parts": [{"data": report, "text": "conflict"}]},
            {"parts": [{"data": report}]},
            {"artifactId": "a1", "parts": [{"data": report, "metadata": []}]},
        ]
        for artifact in variants:
            host, peer, _ = make_host()
            original = peer.request
            def corrupt(verb, url, headers, body, **options):
                response = original(verb, url, headers, body, **options)
                if body and json.loads(body)["method"] == "SendMessage":
                    task = response.value["result"]["task"]
                    task["status"]["state"] = "TASK_STATE_COMPLETED"
                    task["artifacts"] = [artifact]
                return response
            peer.request = corrupt
            result = submit(host)
            self.assertEqual(peer.task_count, 1)
            self.assertEqual((result["code"], result["remoteOutcome"]), ("ProtocolRejected", "Unknown"))
            self.assertEqual(host.refs, {})

    def test_direct_reply_parts_and_mcp_content_are_protocol_checked(self):
        for protocol in ("mcp", "a2a"):
            host, peer, _ = make_host()
            original = peer.request
            def corrupt(verb, url, headers, body, **options):
                response = original(verb, url, headers, body, **options)
                method = json.loads(body)["method"] if body else "card"
                if protocol == "mcp" and method == "tools/call":
                    response.value["result"]["content"] = [{}]
                if protocol == "a2a" and method == "SendMessage":
                    response.value["result"] = {"message": {"messageId": "m1", "role": "ROLE_AGENT", "parts": [{"text": "x", "data": {}}]}}
                return response
            peer.request = corrupt
            result = host.call("readEvidence", {"documentId": "evidence-42"}) if protocol == "mcp" else submit(host)
            self.assertEqual((result["code"], result["remoteOutcome"]), ("ProtocolRejected", "Unknown"))
            self.assertEqual(host.refs, {})

    def test_valid_a2a_metadata_survives_protocol_validation(self):
        host, peer, _ = make_host()
        original = peer.request
        def metadata(verb, url, headers, body, **options):
            response = original(verb, url, headers, body, **options)
            if body and json.loads(body)["method"] == "SendMessage":
                task = response.value["result"]["task"]
                task["metadata"] = {"future": {"number": 1}}
                task["artifacts"] = [{"artifactId": "a1", "metadata": {}, "parts": [{"data": {"selected": []}, "metadata": {"hint": "untrusted"}}]}]
            return response
        peer.request = metadata
        self.assertEqual(submit(host)["artifact"], {"selected": []})

    def test_two_finishers_publish_only_once_and_abort_wins_before_publish(self):
        for should_abort in (False, True):
            host, _, _ = make_host()
            closed, release = threading.Event(), threading.Event()
            paused = False
            def paused_clock():
                nonlocal paused
                if host.closed and not paused:
                    paused = True
                    closed.set()
                    if not release.wait(2):
                        raise RuntimeError("test release missing")
                return 0
            host.clock = paused_clock
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(host.finish, {"outcome": "Success"})
                self.assertTrue(closed.wait(2))
                second = pool.submit(host.finish, {"outcome": "Success"})
                if should_abort:
                    host.abort()
                release.set()
                result, other = first.result(timeout=2), second.result(timeout=2)
            self.assertEqual(result, other)
            self.assertEqual(sum(e["event"] == "publication" for e in host.trace), 1)
            self.assertEqual(result["result"]["outcome"], "RootTerminated" if should_abort else "Success")

    def test_descriptor_drift_and_invalid_header_block_business_call(self):
        for mutate in (lambda d: d.update(description="changed"),
                       lambda d: d["inputSchema"]["properties"]["documentId"].update({"x-mcp-header": "Bad\rName"})):
            host, peer, _ = make_host()
            mutate(peer.tool)
            self.assertEqual(host.call("readEvidence", {"documentId": "evidence-42"})["code"], "BindingChanged")
            self.assertEqual([r[0] for r in peer.requests], ["tools/list"])

    def test_card_endpoint_drift_blocks_task_creation(self):
        host, peer, _ = make_host()
        peer.card["supportedInterfaces"][0]["url"] = "https://wrong.test/rpc"
        self.assertEqual(submit(host)["code"], "BindingChanged")
        self.assertEqual(peer.task_count, 0)

    def test_real_metadata_and_header_mirroring(self):
        host, peer, _ = make_host()
        host.call("readEvidence", {"documentId": "evidence-42"})
        _, request, headers, _ = peer.requests[-1]
        self.assertEqual(headers["MCP-Protocol-Version"], "2026-07-28")
        self.assertEqual(request["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"], "2026-07-28")
        self.assertEqual(headers["Mcp-Name"], "evidence.read")
        self.assertEqual(headers["Mcp-Param-DocumentId"], "evidence-42")

    def test_missing_mcp_result_type_is_compatible_wrong_rpc_id_is_not(self):
        host, peer, _ = make_host(); peer.no_result_type = True
        self.assertEqual(host.call("readEvidence", {"documentId": "evidence-42"})["kind"], "Evidence")
        host, peer, _ = make_host(); peer.wrong_id = True
        self.assertEqual(host.call("readEvidence", {"documentId": "evidence-42"})["code"], "ProtocolRejected")

    def test_forged_foreign_and_closed_root_references(self):
        host, _, _ = make_host()
        ref = submit(host)["ref"]
        other, _, _ = make_host()
        self.assertEqual(other.call("observe", {"ref": ref})["code"], "InvalidReference")
        self.assertEqual(host.call("observe", {"ref": "forged"})["code"], "InvalidReference")
        host.finish({"outcome": "NeedsInput"})
        self.assertEqual(host.call("observe", {"ref": ref})["code"], "RootTerminated")

    def test_reference_cannot_follow_a_changed_peer_endpoint(self):
        host, peer, _ = make_host()
        ref = submit(host)["ref"]
        before = len(peer.requests)
        host.config = replace(host.config, a2a_url="https://agent.test/other")
        self.assertEqual(host.call("observe", {"ref": ref})["code"], "InvalidReference")
        self.assertEqual(len(peer.requests), before)

    def test_cleanup_uses_reserve_and_publication_is_idempotent(self):
        host, peer, _ = make_host(limits=Limits(max_requests=6, cleanup_requests=2))
        submit(host)
        self.assertEqual(host.normal_requests, 4)
        result = host.finish({"outcome": "NeedsInput"})
        self.assertEqual(result["cleanup"][0]["outcome"], "Canceled")
        self.assertEqual(host.requests, 6)
        self.assertEqual(result, host.finish({"outcome": "Success"}))
        self.assertEqual(sum(x["event"] == "publication" for x in host.trace), 1)
        serialized = json.dumps(result)
        self.assertNotIn("MCP-SECRET", serialized)
        self.assertNotIn("A2A-SECRET", serialized)

    def test_explicit_cancel_keeps_root_live_and_preserves_refusal(self):
        host, peer, _ = make_host()
        ref = submit(host)["ref"]
        peer.cancel_refusal = True
        result = host.call("cancel", {"ref": ref})
        self.assertEqual((result["code"], result["remoteOutcome"]), ("TaskNotCancelable", "Completed"))
        self.assertFalse(host.closed)
        self.assertNotIn("private upstream detail", json.dumps(result))

    def test_root_deadline_overrides_success_without_call_budget_requirement(self):
        host, _, clock = make_host(limits=Limits(max_requests=2, cleanup_requests=2))
        self.assertEqual(host.finish({"outcome": "Success"})["result"]["outcome"], "Success")
        host, _, clock = make_host()
        clock.now = 16
        self.assertEqual(host.finish({"outcome": "Success"})["result"]["outcome"], "Timeout")

    def test_poll_spacing_and_limit(self):
        host, _, clock = make_host()
        ref = submit(host)["ref"]
        for _ in range(3):
            self.assertEqual(host.call("observe", {"ref": ref})["kind"], "Task")
        self.assertGreaterEqual(clock.now, .2)
        self.assertEqual(host.call("observe", {"ref": ref})["code"], "BudgetDenied")

    def test_header_constraints_and_encoding(self):
        for value in (" snow ", "é", "=?base64?abc?=", ""):
            self.assertEqual(encode_header_value(value), "=?base64?" + base64.b64encode(value.encode()).decode() + "?=")
        self.assertEqual(encode_header_value("plain"), "plain")
        descriptor = copy.deepcopy(TOOL)
        descriptor["inputSchema"]["properties"]["documentId"]["type"] = "number"
        with self.assertRaises(HostError): validate_tool_descriptor(descriptor)
        descriptor = copy.deepcopy(TOOL)
        descriptor["inputSchema"]["items"] = {"type": "string", "x-mcp-header": "Array"}
        with self.assertRaises(HostError): validate_tool_descriptor(descriptor)

    def test_malformed_call_arguments_are_rejected(self):
        host, _, _ = make_host()
        for operation, arguments in (({}, {}), ("readEvidence", []), ("submit", {}), ("readEvidence", {"documentId": []})):
            self.assertEqual(host.call(operation, arguments)["kind"], "Error")


class TransportTests(unittest.TestCase):
    def test_duplicate_json_keys_nonfinite_and_depth(self):
        for raw in (b'{"a":1,"a":2}', b'{"x":NaN}', b'"\xff"'):
            with self.assertRaises(TransportError): decode_json(raw)
        with self.assertRaises(TransportError): decode_json(b'[[[[1]]]]', 2)

    def test_sse_notifications_and_final_response(self):
        payload = (b': keepalive\n\n'
            b'data: {"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":"p","progress":1}}\n\n'
            b'data: {"jsonrpc":"2.0","id":"1","result":{"resultType":"complete"}}\n\n')
        response = FakeHTTPResponse(payload, "text/event-stream")
        with patch("transport.ssl.create_default_context"), patch("transport._OwnedHTTPSConnection", return_value=FakeConnection(response)):
            transport = HTTPSTransport("/unused")
            result = transport.request("POST", "https://peer.test/mcp", {}, b"{}", deadline=__import__('time').monotonic()+1,
                max_bytes=1024, max_depth=16, max_events=4, max_event_bytes=512, request_id="1", progress_token="p")
        self.assertEqual(result.notifications, 1)
        self.assertEqual(result.value["id"], "1")

    def test_stream_bytes_are_bounded_before_decode(self):
        response = FakeHTTPResponse(b"x" * 300, "application/json")
        with patch("transport.ssl.create_default_context"), patch("transport._OwnedHTTPSConnection", return_value=FakeConnection(response)):
            transport = HTTPSTransport("/unused")
            with self.assertRaises(TransportError) as caught:
                transport.request("GET", "https://peer.test/card", {}, None, deadline=__import__('time').monotonic()+1,
                    max_bytes=100, max_depth=16, max_events=4, max_event_bytes=512)
        self.assertEqual(caught.exception.code, "ResponseLimit")
        self.assertLessEqual(caught.exception.received, 101)

    def test_sse_bom_cr_and_split_crlf(self):
        for terminator in (b"\r", b"\r\n"):
            payload = b'\xef\xbb\xbfdata: {"jsonrpc":"2.0","id":"1","result":{}}' + terminator * 2
            response = FakeHTTPResponse(payload, "text/event-stream")
            original_read = response.read1
            response.read1 = lambda n: original_read(min(n, 1))
            with patch("transport.ssl.create_default_context"), patch("transport._OwnedHTTPSConnection", return_value=FakeConnection(response)):
                result = HTTPSTransport("/unused").request("POST", "https://peer.test/mcp", {}, b"{}",
                    deadline=__import__('time').monotonic()+1, max_bytes=1024,
                    max_depth=16, max_events=4, max_event_bytes=512, request_id="1")
            self.assertEqual(result.value["id"], "1")


class FakeHTTPResponse:
    status = 200
    def __init__(self, body, content_type): self.body, self.content_type = body, content_type
    def getheader(self, name, default=None): return self.content_type if name == "Content-Type" else default
    def read1(self, n):
        data, self.body = self.body[:n], self.body[n:]
        return data


class FakeConnection:
    sock = None
    def __init__(self, response): self.response = response
    def connect(self): pass
    def request(self, *args, **kwargs): pass
    def getresponse(self): return self.response
    def close(self): pass


class RealTLSBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="d0-host-tls-")
        cls.cert, cls.key = str(Path(cls.tmp.name) / "cert.pem"), str(Path(cls.tmp.name) / "key.pem")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
                        "-keyout", cls.key, "-out", cls.cert], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @contextmanager
    def peer(self, handler):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(2)
        stopped, errors = threading.Event(), []
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert, self.key)
        def serve():
            try:
                raw, _ = listener.accept()
                with context.wrap_socket(raw, server_side=True) as stream:
                    stream.settimeout(2)
                    request = b""
                    while b"\r\n\r\n" not in request:
                        request += stream.recv(4096)
                    handler(stream, stopped)
            except (OSError, ssl.SSLError):
                pass  # Client shutdown is the expected adverse boundary.
            except Exception as exc:
                errors.append(exc)
        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        try:
            yield f"https://127.0.0.1:{listener.getsockname()[1]}/rpc"
        finally:
            stopped.set()
            listener.close()
            worker.join(2)
            self.assertFalse(worker.is_alive(), "test peer did not join")
            self.assertEqual(errors, [])

    def request(self, url, seconds=1):
        return HTTPSTransport(self.cert).request("GET", url, {}, None,
            deadline=time.monotonic() + seconds, max_bytes=4096, max_depth=16,
            max_events=4, max_event_bytes=512)

    def test_absolute_deadline_interrupts_dripped_http_headers(self):
        def drip(stream, stopped):
            stream.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n")
            for _ in range(30):
                if stopped.wait(.04): return
                stream.sendall(b"X-Drip: 1\r\n")
            stream.sendall(b"Content-Length: 2\r\n\r\n{}")
        with self.peer(drip) as url:
            start = time.monotonic()
            with self.assertRaises(TransportError) as caught:
                self.request(url, .15)
            elapsed = time.monotonic() - start
        self.assertEqual(caught.exception.code, "Timeout")
        self.assertTrue(caught.exception.dispatched)
        self.assertLess(elapsed, .6)

    def test_truncated_content_length_cannot_be_a_valid_json_response(self):
        def truncated(stream, stopped):
            stream.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 102\r\n\r\n{}")
        with self.peer(truncated) as url:
            with self.assertRaises(TransportError) as caught:
                self.request(url)
        self.assertEqual((caught.exception.code, caught.exception.received, caught.exception.dispatched), ("TransportFailure", 2, True))

    def test_root_close_interrupts_owned_response_before_publication(self):
        for abort in (False, True):
            waiting = threading.Event()
            def silent(stream, stopped):
                stream.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 100\r\nConnection: close\r\n\r\n")
                waiting.set()
                stopped.wait(2)
            with self.peer(silent) as url:
                host = Host(HostConfig(url, url, "test", "test", self.cert, TOOL, CARD))
                with ThreadPoolExecutor(max_workers=1) as pool:
                    call = pool.submit(host.call, "readEvidence", {"documentId": "evidence-42"})
                    self.assertTrue(waiting.wait(1))
                    start = time.monotonic()
                    if abort: host.abort()
                    result = host.finish({"outcome": "Success"})
                    outcome = call.result(timeout=1)
                    elapsed = time.monotonic() - start
                self.assertLess(elapsed, .6)
                self.assertEqual((outcome["code"], outcome["remoteOutcome"]), ("RootTerminated", "Unknown"))
                self.assertEqual(result["result"]["outcome"], "RootTerminated")
                events = [e["event"] for e in result["trace"]]
                self.assertLess(events.index("call_rejected"), events.index("publication"))

    def test_cancel_interrupts_silent_tls_handshake(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        hello, stopped = threading.Event(), threading.Event()
        def raw_peer():
            stream, _ = listener.accept()
            with stream:
                stream.recv(4096)  # Observe actual ClientHello, then withhold TLS reply.
                hello.set()
                stopped.wait(2)
        worker = threading.Thread(target=raw_peer, daemon=True)
        worker.start()
        transport = HTTPSTransport(self.cert)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                call = pool.submit(transport.request, "GET", f"https://127.0.0.1:{listener.getsockname()[1]}/", {}, None,
                    deadline=time.monotonic()+2, max_bytes=4096, max_depth=16, max_events=4, max_event_bytes=512)
                self.assertTrue(hello.wait(1))
                start = time.monotonic()
                transport.cancel_active()
                with self.assertRaises(TransportError) as caught:
                    call.result(timeout=1)
                self.assertLess(time.monotonic()-start, .6)
                self.assertEqual((caught.exception.code, caught.exception.dispatched), ("RootTerminated", False))
        finally:
            stopped.set()
            listener.close()
            worker.join(2)


if __name__ == "__main__": unittest.main()
