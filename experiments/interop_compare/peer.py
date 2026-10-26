"""Independent process fixture for the shared-adapter experiment.

These JSON-RPC envelopes resemble a tiny MCP/A2A interaction but are NOT a
protocol implementation or conformance oracle. Identity headers are synthetic
test identities, not authentication. Bind only to loopback; use no real data.
"""
from __future__ import annotations

import argparse
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


MODES = ("normal", "needs_input", "pending", "lost_submit", "malformed",
         "oversized", "wrong_type", "wrong_id")


class State:
    def __init__(self, mode: str):
        self.mode = mode
        self.lock = threading.Lock()
        self.calls: dict[str, int] = {}
        self.tasks: dict[str, dict] = {}


def serve(mode: str) -> None:
    state = State(mode)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def send_bytes(self, raw: bytes, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def send_json(self, value, status: int = 200):
            self.send_bytes(json.dumps(value, separators=(",", ":")).encode(), status)

        def do_GET(self):
            if self.path != "/__stats":
                self.send_json({"error": "not-found"}, 404)
                return
            with state.lock:
                self.send_json({"calls": state.calls, "created": len(state.tasks),
                                "tasks": state.tasks})

        def do_POST(self):
            if self.path != "/rpc":
                self.send_json({"error": "not-found"}, 404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("size")
                request = json.loads(self.rfile.read(length))
                request_id = request["id"]
                method = request["method"]
                params = request["params"]
                if not isinstance(method, str) or not isinstance(params, dict):
                    raise ValueError("shape")
            except (ValueError, KeyError, TypeError):
                self.send_json({"error": "bad-request"}, 400)
                return
            principal = self.headers.get("X-Fixture-Principal", "")
            tenant = self.headers.get("X-Fixture-Tenant", "")
            with state.lock:
                state.calls[method] = state.calls.get(method, 0) + 1
                envelope = {"jsonrpc": "2.0", "id": request_id}
                if state.mode == "wrong_id":
                    envelope["id"] = request_id + 100
                if method == "tools/call":
                    if state.mode == "malformed":
                        self.send_bytes(b'{"jsonrpc":"2.0","result":')
                        return
                    value = 42 if state.mode == "wrong_type" else "evidence:42"
                    if state.mode == "oversized":
                        value = "x" * 32768
                    envelope["result"] = {"resultType": "complete",
                                          "structuredContent": {"value": value}}
                elif method == "message/send":
                    task_id = "t" + str(len(state.tasks) + 1)
                    state.tasks[task_id] = {
                        "principal": principal, "tenant": tenant,
                        "input": params["input"],
                        "state": "input-required" if state.mode == "needs_input" else "working",
                    }
                    if state.mode == "lost_submit":
                        # The task exists, but no response bytes reach the client.
                        self.close_connection = True
                        self.connection.shutdown(socket.SHUT_RDWR)
                        self.connection.close()
                        return
                    envelope["result"] = task_result(task_id)
                elif method in ("tasks/get", "tasks/continue", "tasks/cancel"):
                    task_id = params.get("taskId", "")
                    task = state.tasks.get(task_id)
                    if (not task or task["principal"] != principal
                            or task["tenant"] != tenant):
                        envelope["error"] = {"code": "Denied", "message": "unavailable"}
                        self.send_json(envelope, 403)
                        return
                    if method == "tasks/cancel" and task["state"] != "completed":
                        task["state"] = "canceled"
                    elif method == "tasks/continue" and task["state"] == "input-required":
                        if not params.get("input"):
                            envelope["error"] = {"code": "InputRequired", "message": "input required"}
                            self.send_json(envelope)
                            return
                        task["continuationInput"] = params["input"]
                        task["state"] = "completed"
                    elif method == "tasks/get" and task["state"] == "working" and state.mode != "pending":
                        task["state"] = "completed"
                    envelope["result"] = task_result(task_id)
                else:
                    envelope["error"] = {"code": "Unsupported", "message": "unsupported"}
                self.send_json(envelope)

    def task_result(task_id: str) -> dict:
        task = state.tasks[task_id]
        return {"id": task_id, "status": {"state": task["state"]},
                "artifacts": ([{"text": "report:" + task["input"]}]
                              if task["state"] == "completed" else [])}

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    print(f"http://127.0.0.1:{server.server_port}/rpc", flush=True)
    server.serve_forever(poll_interval=0.05)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=MODES, default="normal")
    serve(parser.parse_args().mode)
