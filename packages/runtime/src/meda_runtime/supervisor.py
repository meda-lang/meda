"""Bounded process controller for Meda's evidence/report protocol profile.

No SDK peers, language compiler, scenario fixtures or repository paths are needed.
This is process supervision, not a security sandbox for hostile application code.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import threading
import time
from .host import OPERATIONS

MAX_LINE = 65_536
MAX_RSS = 256 * 1024 * 1024
_PROCESS_STATUS_PATHS = {}


def _decode_frame(raw):
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise ValueError("duplicate frame field")
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite frame")))
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if depth > 16:
                raise ValueError("frame depth limit")
            if isinstance(item, str) and any(0xD800 <= ord(char) <= 0xDFFF for char in item):
                raise ValueError("invalid Unicode frame")
            children = (*item.keys(), *item.values()) if isinstance(item, dict) else item if isinstance(item, list) else ()
            pending.extend((child, depth + 1) for child in children)
        json.dumps(value, allow_nan=False)
    except RecursionError:
        raise ValueError("frame depth limit") from None
    return value


def _safe_environment():
    # Deliberately excludes credentials, NODE_OPTIONS and other inherited hooks.
    return {"PATH": os.defpath, "LANG": "C.UTF-8"}


def _rss(pid):
    # Some executors expose an outer /proc inside an inner PID namespace.
    # Popen.pid then does not name that process in /proc. Resolve only among
    # this controller's direct children and match its namespace-visible PID.
    own = Path("/proc/self/status").read_text().splitlines()
    outer_pid = next(line.split()[1] for line in own if line.startswith("Tgid:"))
    key = (outer_pid, pid)
    cached = _PROCESS_STATUS_PATHS.get(key)
    paths = [cached] if cached is not None else []
    # The children pseudo-file is unavailable on some kernel builds. Enumerate
    # status metadata only, requiring both parent and namespace PID to match.
    paths.extend(path / "status" for path in Path("/proc").iterdir() if path.name.isdigit())
    for path in paths:
        try:
            fields = {line.split(":", 1)[0]: line.split(":", 1)[1].split()
                      for line in path.read_text().splitlines()}
            namespace_pids = fields.get("NSpid", fields["Pid"])
            if fields["PPid"] == [outer_pid] and int(namespace_pids[-1]) == pid:
                _PROCESS_STATUS_PATHS[key] = path
                return int(fields.get("VmRSS", ["0"])[0]) * 1024
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return 0


def _kill(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=2)


def _run_process(host, input_value, command, *, cwd=None,
                 credential_sentinels=(), private_receipts=None, _hooks=None,
                 _reject_output_secrets=False):
    """Trusted process controller shared by public API and research adapters.

    The private hooks are supplied by a trusted controller for lifecycle probes;
    application code cannot install them. They contain no protocol or policy.
    """
    if not Path("/proc/self/status").is_file():
        raise RuntimeError("This profile requires Linux RSS supervision")
    process = subprocess.Popen(command, cwd=cwd,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=_safe_environment(), start_new_session=True, bufsize=0)
    os.set_blocking(process.stdin.fileno(), False)
    start = time.monotonic()
    stop = threading.Event()
    guard = threading.Lock()
    state = {"termination": None, "peakRssBytesObserved": 0, "barriers": [],
             "retirementRequestedAt": None}
    rpc_calls, finish_frames, post_fatal_responses = [], 0, 0
    stderr = bytearray()
    unexpected_stdout = bytearray()
    internal_refs = set()
    truncated = False

    def terminate(reason):
        with guard:
            if state["termination"] is not None:
                return
            state["retirementRequestedAt"] = time.monotonic()
            state["termination"] = reason
            host.abort("Timeout" if reason == "deadline" else "RootTerminated")
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def monitor():
        try:
            monitor_loop()
        except Exception:
            terminate("supervisor_failure")

    def monitor_loop():
        while not stop.wait(.01):
            if process.poll() is not None:
                return
            rss = _rss(process.pid)
            state["peakRssBytesObserved"] = max(state["peakRssBytesObserved"], rss)
            if rss > MAX_RSS:
                terminate("memory_limit")
            if time.monotonic() >= host.deadline:
                terminate("deadline")
            if _hooks is not None and _hooks.monitor(terminate, state["barriers"]):
                return

    def write_frame(frame):
        # A hostile or wedged worker cannot hold the closure lock by failing to
        # drain stdin. Each write is nonblocking; closure may interrupt a frame.
        view = memoryview(frame)
        while view:
            with guard:
                if host.closed or state["termination"] is not None:
                    return False
                try:
                    written = os.write(process.stdin.fileno(), view[:4096])
                except BlockingIOError:
                    written = 0
            if written:
                view = view[written:]
            else:
                stop.wait(.005)
        return True

    watcher = threading.Thread(target=monitor, name="meda-worker-supervisor", daemon=True)
    watcher.start()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffer = bytearray()
    proposed = None
    expected_id = 1
    try:
        initial = json.dumps({"kind": "start", "input": input_value}, separators=(",", ":")).encode() + b"\n"
        if len(initial) > MAX_LINE:
            terminate("input_limit")
        else:
            write_frame(initial)
        while proposed is None and state["termination"] is None:
            ready = selector.select(.05)
            if not ready and process.poll() is not None:
                terminate("exit_without_finish")
                break
            for key, _ in ready:
                data = os.read(key.fileobj.fileno(), 4096)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                if key.data == "stderr":
                    stderr.extend(data)
                    if len(stderr) > MAX_LINE:
                        truncated = True
                        del stderr[MAX_LINE:]
                        terminate("stderr_limit")
                    continue
                buffer.extend(data)
                if len(buffer) > MAX_LINE:
                    unexpected_stdout.extend(buffer[:MAX_LINE])
                    truncated = True
                    terminate("frame_limit")
                    break
                while b"\n" in buffer and state["termination"] is None:
                    line, _, rest = buffer.partition(b"\n")
                    buffer = bytearray(rest)
                    try:
                        frame = _decode_frame(line)
                    except (UnicodeDecodeError, ValueError):
                        unexpected_stdout.extend(line)
                        terminate("invalid_frame")
                        break
                    if not isinstance(frame, dict):
                        unexpected_stdout.extend(line)
                        terminate("invalid_frame")
                        break
                    if frame.get("kind") == "finish":
                        finish_frames += 1
                        if finish_frames != 1 or not isinstance(frame.get("result"), dict):
                            unexpected_stdout.extend(line)
                            terminate("invalid_finish")
                            break
                        proposed = frame["result"]
                        if buffer:
                            unexpected_stdout.extend(buffer)
                            finish_frames += _finish_count(buffer)
                            terminate("output_after_finish")
                        break
                    operation = frame.get("operation")
                    if (frame.get("kind") != "call" or type(frame.get("id")) is not int or frame.get("id") != expected_id or
                            not isinstance(operation, str) or operation not in OPERATIONS or not isinstance(frame.get("arguments"), dict)):
                        terminate("invalid_call")
                        break
                    expected_id += 1
                    value = host.call(operation, frame["arguments"])
                    if value.get("kind") == "Task" and isinstance(value.get("ref"), str):
                        internal_refs.add(value["ref"])
                    rpc_calls.append({"id": frame["id"], "operation": operation, "kind": value.get("kind"),
                                      **{name: value[name] for name in ("state", "code", "fatal", "remoteOutcome") if name in value},
                                      **({"artifactSha256": hashlib.sha256(json.dumps(value["artifact"], sort_keys=True,
                                          separators=(",", ":")).encode()).hexdigest()} if "artifact" in value else {})})
                    if _hooks is not None:
                        _hooks.after_call(operation, value, terminate, state["barriers"])
                    if value.get("fatal") or host.closed or state["termination"] is not None:
                        with guard:
                            if state["termination"] is None:
                                # Retire without replacing the host's specific fatal cause.
                                state["termination"] = "fatal_host_outcome"
                                state["retirementRequestedAt"] = time.monotonic()
                                try:
                                    os.killpg(process.pid, signal.SIGKILL)
                                except ProcessLookupError:
                                    pass
                        break
                    response = json.dumps({"kind": "response", "id": frame["id"], "value": value},
                                          separators=(",", ":")).encode() + b"\n"
                    if len(response) > MAX_LINE:
                        terminate("response_frame_limit")
                        break
                    if not write_frame(response):
                        break
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        try:
            process.wait(timeout=min(1, host.limits.cleanup_seconds))
        except subprocess.TimeoutExpired:
            terminate("worker_retirement_limit")
            _kill(process)
        # After one finish, any further stdout is a duplicate/output violation.
        os.set_blocking(process.stdout.fileno(), False)
        trailing = process.stdout.read(MAX_LINE + 1)
        if trailing:
            unexpected_stdout.extend(trailing[:MAX_LINE])
            truncated = truncated or len(trailing) > MAX_LINE
            finish_frames += _finish_count(trailing)
            terminate("output_after_finish")
        os.set_blocking(process.stderr.fileno(), False)
        trailing_stderr = process.stderr.read(MAX_LINE - len(stderr) + 1)
        if trailing_stderr:
            stderr.extend(trailing_stderr)
        if len(stderr) > MAX_LINE or len(unexpected_stdout) > MAX_LINE:
            truncated = True
            del stderr[MAX_LINE:]
            del unexpected_stdout[MAX_LINE:]
        if process.returncode not in (0, None) and state["termination"] is None:
            terminate("worker_failure")
    except (BrokenPipeError, OSError):
        terminate("controller_io_failure")
    finally:
        stop.set()
        _kill(process)
        worker_retired_at = time.monotonic()
        watcher.join(timeout=1)
        selector.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream and not stream.closed:
                stream.close()
    if _reject_output_secrets and _contains_secret(proposed, [*credential_sentinels, *internal_refs]):
        host.abort("ProtocolRejected")
    cleanup_started_at = time.monotonic()
    publication = host.finish(proposed or {"outcome": "RootTerminated", "fatal": True})
    cleanup_elapsed = time.monotonic() - cleanup_started_at
    if _hooks is not None:
        _hooks.after_publication(host, state["barriers"])
    application_channels = {
        "applicationFinish": [] if proposed is None else [json.dumps(proposed, ensure_ascii=False)],
        "stderr": [] if not stderr else [stderr.decode(errors="replace")],
        "unexpectedStdout": [] if not unexpected_stdout else [unexpected_stdout.decode(errors="replace")],
    }
    if private_receipts is not None:
        private_receipts.update(references=internal_refs, channels=application_channels, complete=not truncated)
    worker = {"retired": process.poll() is not None, "returncode": process.returncode,
              "termination": state["termination"] or "normal", "finishFrames": finish_frames,
              "responsesAfterFatal": post_fatal_responses, "calls": rpc_calls,
              "peakRssBytesObserved": state["peakRssBytesObserved"],
              "elapsedSeconds": time.monotonic() - start, "barriers": state["barriers"],
              "retirementRequestedAfterStartSeconds": (None if state["retirementRequestedAt"] is None
                  else state["retirementRequestedAt"] - start),
              "retirementObservedAfterStartSeconds": worker_retired_at - start,
              "retirementAfterRequestSeconds": (None if state["retirementRequestedAt"] is None
                  else worker_retired_at - state["retirementRequestedAt"]),
              "hostFinishElapsedSeconds": cleanup_elapsed,
              "supervisorJoined": not watcher.is_alive(), "stderrBytes": len(stderr),
              "applicationFinish": proposed, "stderr": application_channels["stderr"],
              "unexpectedStdout": application_channels["unexpectedStdout"], "outputTruncated": truncated,
              "containment": "sampled_rss_and_wall_supervision_not_os_sandbox"}
    receipt = {**publication, "worker": worker}
    if private_receipts is not None:
        private_receipts["receipt"] = receipt
    return _scrub(receipt, [*credential_sentinels, *internal_refs])


def _finish_count(raw):
    count = 0
    for line in raw.splitlines():
        try:
            value = json.loads(line)
            count += isinstance(value, dict) and value.get("kind") == "finish"
        except (ValueError, UnicodeError):
            pass
    return count


def _channel_scan(channels, credentials, references, complete):
    rows = []
    for name, records in channels.items():
        rows.append({"name": name, "entries": len(records),
            "bytes": sum(len(item.encode("utf-8")) for item in records),
            "credentialMatches": sum(_match_count(item, token) for item in records for token in credentials),
            "referenceMatches": sum(_match_count(item, token) for item in records for token in references)})
    return {"channels": rows, "credentialSentinelCount": len(credentials),
            "referenceSentinelCount": len(references), "complete": complete}


def _secret_forms(secret):
    # Captured channels may contain raw text or serialized JSON. Scan/redact
    # both forms, including JSON's quote/backslash escapes and Unicode escapes.
    if not secret:
        return []
    return sorted({secret, json.dumps(secret, ensure_ascii=False)[1:-1],
                   json.dumps(secret, ensure_ascii=True)[1:-1]}, key=len, reverse=True)


def _match_count(item, token):
    forms = _secret_forms(token)
    return len(re.findall("|".join(re.escape(form) for form in forms), item)) if forms else 0


def _contains_secret(value, secrets):
    if isinstance(value, str):
        return any(_match_count(value, secret) for secret in secrets)
    if isinstance(value, list):
        return any(_contains_secret(item, secrets) for item in value)
    if isinstance(value, dict):
        return any(_contains_secret(key, secrets) or _contains_secret(item, secrets)
                   for key, item in value.items())
    return False


def _scrub(value, secrets):
    if isinstance(value, str):
        for secret in secrets:
            for form in _secret_forms(secret):
                value = value.replace(form, "[REDACTED_CREDENTIAL]")
        return value
    if isinstance(value, list):
        return [_scrub(item, secrets) for item in value]
    if isinstance(value, dict):
        return {_scrub(key, secrets): _scrub(item, secrets) for key, item in value.items()}
    return value


