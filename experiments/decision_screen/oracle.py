"""Independent oracle for the bounded decision screen, not full D0 acceptance.

Only receipt data and frozen expectations are inputs. No host, client, binding,
SDK or application validator is imported. Missing evidence fails a screen check.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
OPERATIONS = ("readEvidence", "submit", "observe", "provideInput", "cancel")
REPORT = {"documentId": "evidence-42", "revision": 1,
          "selected": [{"id": "f1", "value": "blue"}, {"id": "f2", "value": "square"}]}


def load_cases():
    return json.loads((HERE / "cases.json").read_text())["cases"]


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _exact(actual, expected):
    try:
        return _json(actual) == _json(expected)
    except (TypeError, ValueError):
        return False


def _rows(value):
    return [row for row in value if type(row) is dict] if type(value) is list else []


def _dict(value):
    return value if type(value) is dict else {}


def _bounded(value, maximum):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum


def assess(case, receipt):
    """Return independently evaluated checks; matching two clients is insufficient."""
    checks = []

    def check(name, passed, actual=None, expected=None):
        checks.append({"name": name, "passed": bool(passed), "actual": actual, "expected": expected})

    r = _dict(receipt)
    expected = case["expected"]
    result, worker = _dict(r.get("result")), _dict(r.get("worker"))
    trace, calls = _rows(r.get("trace")), _rows(worker.get("calls"))
    peers, proxy = _dict(r.get("peers")), _dict(r.get("proxy"))
    peer_a2a, peer_mcp = _rows(peers.get("a2a")), _rows(peers.get("mcp"))
    proxy_a2a, proxy_mcp = _rows(proxy.get("a2a")), _rows(proxy.get("mcp"))
    check("receipt_shapes", type(receipt) is dict and type(r.get("trace")) is list and
          type(worker.get("calls")) is list and all(type(row) is dict for row in r.get("trace", [])) and
          all(type(row) is dict for row in worker.get("calls", [])) and
          all(type(peers.get(p)) is list and type(proxy.get(p)) is list for p in ("mcp", "a2a")))
    check("outcome", result.get("outcome") == expected["outcome"], result.get("outcome"), expected["outcome"])
    if "remoteOutcome" in expected:
        check("remote_outcome", result.get("remoteOutcome") == expected["remoteOutcome"],
              result.get("remoteOutcome"), expected["remoteOutcome"])
    check("fatal", result.get("fatal", False) is expected.get("fatal", False),
          result.get("fatal", False), expected.get("fatal", False))
    success = expected["outcome"] == "Success"
    check("report", _exact(result.get("report"), REPORT) if success else "report" not in result,
          result.get("report"), REPORT if success else "absent")
    publications = [e for e in trace if e.get("event") == "publication"]
    check("one_publication", len(publications) == 1, len(publications), 1)
    check("publication_result", len(publications) == 1 and
          publications[0].get("outcome") == expected["outcome"] and
          publications[0].get("success") is success)
    actual_calls = dict(Counter(c.get("operation") for c in calls))
    check("application_calls", all(actual_calls.get(op, 0) == count for op, count in expected["calls"].items()) and
          not set(actual_calls) - set(OPERATIONS), actual_calls, expected["calls"])
    check("call_ids", [c.get("id") for c in calls] == list(range(1, len(calls) + 1)))
    cleanup_dispatches = [e for e in trace if e.get("event") == "dispatch" and e.get("cleanup") is True]
    cleanup_cancels = sum(e.get("method") == "CancelTask" for e in cleanup_dispatches)
    check("cleanup_cancels", cleanup_cancels == expected["cleanupCancel"], cleanup_cancels, expected["cleanupCancel"])
    check("cleanup_scope", len(cleanup_dispatches) <= 2 and
          all(e.get("protocol") == "a2a" and e.get("method") in ("__card", "CancelTask") for e in cleanup_dispatches))
    created = [e for e in peer_a2a if e.get("event") == "created"]
    continued = [e for e in peer_a2a if e.get("event") == "continued"]
    check("peer_task_creations", len(created) == expected["peerTasks"], len(created), expected["peerTasks"])
    check("peer_continuations", len(continued) == expected["calls"]["provideInput"], len(continued), expected["calls"]["provideInput"])
    followups = [e for e in peer_a2a if e.get("event") in ("continued", "observed", "canceled", "cancel_refused")]
    check("same_task", (not followups if not created else len(created) == 1 and
          type(created[0].get("taskId")) is str and
          all(e.get("taskId") == created[0]["taskId"] for e in followups)))
    if continued:
        check("continuation_input", all(_exact(e.get("includeIds"), ["f1", "f2"]) for e in continued))
    # Independent proxy forwards corroborate business delivery. Cleanup shares
    # the cancel operation, so add its separately observed allowance here.
    forwarded = Counter(e.get("operation") for e in proxy_mcp + proxy_a2a if e.get("event") == "forward")
    wanted_forwards = {**expected["calls"], "cancel": expected["calls"]["cancel"] + expected["cleanupCancel"]}
    check("proxy_business_forwards", all(forwarded.get(op, 0) == count for op, count in wanted_forwards.items()),
          {op: forwarded.get(op, 0) for op in OPERATIONS}, wanted_forwards)
    check("evidence_peer", sum(e.get("event") == "evidence_read" for e in peer_mcp) == expected["calls"]["readEvidence"])
    for field in ("retired", "supervisorJoined"):
        check("worker_" + field, worker.get(field) is True)
    check("peers_retired", r.get("peerProcessesRetired") is True)
    check("witnesses_before_peer_shutdown", r.get("witnessesCapturedBeforePeerShutdown") is True)
    check("no_output_truncation", worker.get("outputTruncated") is False)
    check("no_unexpected_stdout", worker.get("unexpectedStdout") == [])
    check("no_post_fatal_responses", worker.get("responsesAfterFatal") == 0)
    check("finish_frames", worker.get("finishFrames") == (0 if expected.get("fatal") else 1),
          worker.get("finishFrames"), 0 if expected.get("fatal") else 1)
    check("cleanup_time", _bounded(worker.get("hostFinishElapsedSeconds"), 1.0),
          worker.get("hostFinishElapsedSeconds"), "0..1.0 seconds")
    if expected.get("fatal"):
        retirement = worker.get("retirementAfterRequestSeconds")
        requested = worker.get("retirementRequestedAfterStartSeconds")
        observed = worker.get("retirementObservedAfterStartSeconds")
        check("fatal_retirement_time", _bounded(retirement, 3.0), retirement, "0..3.0 seconds")
        valid_clock = _bounded(requested, 60) and _bounded(observed, 60) and observed >= requested
        check("retirement_clock_consistency", valid_clock and _bounded(retirement, 3) and
              abs((observed - requested) - retirement) < 0.000001)
    scan = _dict(r.get("applicationChannelScan"))
    channels = _rows(scan.get("channels"))
    required_channels = {"applicationFinish", "stderr", "unexpectedStdout", "ordinaryHostTrace", "peerWitnesses", "proxyWitnesses"}
    check("complete_channel_scan", scan.get("complete") is True and
          {e.get("name") for e in channels} == required_channels and
          type(scan.get("credentialSentinelCount")) is int and scan["credentialSentinelCount"] > 0)
    check("no_channel_secrets", bool(channels) and r.get("credentialLeakDetected") is False and
          all(e.get("credentialMatches") == 0 and e.get("referenceMatches") == 0 for e in channels))
    check("ordered_trace", [e.get("sequence") for e in trace] == list(range(len(trace))) and bool(trace))
    closures = [i for i, e in enumerate(trace) if e.get("event") in ("root_abort", "root_close")]
    check("no_late_application_dispatch", bool(closures) and not any(
          e.get("event") in ("admitted", "dispatch") and e.get("cleanup") is not True
          for e in trace[min(closures, default=len(trace)) + 1:]))
    if case["scenario"].get("probeAfterClose"):
        post = _dict(r.get("postCloseAdmission"))
        check("post_close_admission", post.get("kind") == "Error" and post.get("fatal") is True and
              post.get("code") == (expected["outcome"] if expected.get("fatal") else "RootTerminated"), post)
        check("post_close_no_dispatch", r.get("postCloseDispatches") == 0, r.get("postCloseDispatches"), 0)

    witness = expected.get("witness")
    if witness == "lost_submit":
        drops = [e for e in proxy_a2a if e.get("event") == "response_dropped" and
                 e.get("operation") == "submit" and e.get("afterUpstreamResponse") is True]
        check("committed_then_dropped", len(drops) == 1 and len(created) == 1 and any(
              e.get("event") == "upstream_response" and e.get("operation") == "submit" and
              e.get("request") == drops[0].get("request") and e.get("complete") is True and
              e.get("status") == 200 and e.get("rpcResult") is True for e in proxy_a2a))
        check("no_reference_from_unknown_submit", not any(c.get("kind") == "Task" for c in calls) and
              scan.get("referenceSentinelCount") == 0)
    elif witness == "wrong_rpc_id":
        check("wrong_id_mutated", any(e.get("event") == "response_mutated" and
              e.get("mutation") == "evidence_response_id" and e.get("operation") == "readEvidence" for e in proxy_mcp))
        check("wrong_id_received", any(e.get("event") == "transport_error" and
              e.get("code") == "ProtocolRejected" and type(e.get("bytes")) is int and e["bytes"] > 0 for e in trace) or
              any(e.get("event") == "received" and e.get("method") == "tools/call" and
                  type(e.get("bytes")) is int and e["bytes"] > 0 for e in trace))
    elif witness == "wrong_value":
        # Protobuf Struct's raw wire JSON decodes revision as 1.0 in Python.
        # This witness hashes that raw host artifact before either binding
        # normalizes it to an application integer.
        wrong_report = {**REPORT, "revision": 1.0,
                        "selected": [{"id": "f1", "value": "invented"}, {"id": "f2", "value": "square"}]}
        wrong_hash = hashlib.sha256(_json(wrong_report).encode()).hexdigest()
        check("wrong_value_mutated", any(e.get("event") == "response_mutated" and
              e.get("mutation") == "wrong_value" and e.get("operation") == "observe" for e in proxy_a2a))
        check("wrong_value_reached_application", any(c.get("operation") == "observe" and
              c.get("kind") == "Task" and c.get("state") == "Completed" and c.get("artifactSha256") == wrong_hash for c in calls))
    elif witness == "cancel_refusal":
        refused = [e for e in trace if e.get("event") == "explicit_cancel_refused"]
        skipped = [e for e in trace if e.get("event") == "cleanup_skipped"]
        check("refusal_peer", sum(e.get("event") == "cancel_refused" for e in peer_a2a) == 1)
        check("refusal_skip_provenance", len(refused) == 1 and len(skipped) == 1 and
              skipped[0].get("reason") == "PriorExplicitRefusal" and skipped[0].get("remoteOutcome") == "Unknown" and
              skipped[0].get("refusalSequence") == refused[0].get("sequence") and
              refused[0].get("state") == skipped[0].get("lastObservedState") == "Working")
        check("refusal_not_terminal_proof", not any(e.get("event") == "task_observed" and
              e.get("state") in ("Completed", "Failed", "Canceled", "Rejected") for e in trace))
    elif witness in ("abort_after_submit", "abort_before_response", "publish_before_abort"):
        wanted = {"abort_after_submit": "root_closed_after_submit_before_source_response",
                  "abort_before_response": "root_closed_before_observation_release",
                  "publish_before_abort": "publication_committed_before_late_abort"}[witness]
        barriers = worker.get("barriers")
        check("ordering_barrier", type(barriers) is list and wanted in barriers, barriers, wanted)
        if witness == "abort_before_response":
            check("response_barrier", any(e.get("event") == "response_barrier" and e.get("operation") == "observe" for e in proxy_a2a))
        if witness != "publish_before_abort":
            aborts = [e["sequence"] for e in trace if e.get("event") == "root_abort"]
            check("abort_precedes_publication", bool(aborts) and len(publications) == 1 and min(aborts) < publications[0].get("sequence", -1))
    elif witness == "deadline_progress":
        check("live_stream_reached_peer", any(e.get("event") == "stream_started" for e in peer_mcp))
        check("live_stream_interrupted", any(e.get("event") == "stream_terminated" and
              e.get("completed") is False for e in peer_mcp))
        check("live_stream_reached_proxy", any(e.get("event") == "stream_begin" and
              e.get("injected") is False for e in proxy_mcp))
        limits = _dict(_dict(r.get("bindingManifest")).get("limits"))
        check("root_deadline_precedes_request", limits.get("root_seconds") == 0.5 and limits.get("request_seconds") == 2)

    return {"caseId": case["id"], "passed": all(c["passed"] for c in checks), "checks": checks,
            "failedChecks": [c["name"] for c in checks if not c["passed"]],
            "scope": "bounded_screen_not_full_D0_acceptance", "actualCalls": actual_calls}
