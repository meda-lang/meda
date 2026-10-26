"""Independent, conservative D0 receipt checks (standard library only).

This module does not import the host, client, transport, or runner. A receipt is
evidence, not an assertion that the case passed. Missing observations remain
unverified; in particular neither scenario labels nor an ``invariantPassed``
boolean can stand in for a witness. Inventory validation and these receipt
checks never mutate the planned inventory.

The current workflow receipt observes a subset of the frozen requirements. A
fully passing case requires *all* required checks and witnesses. This prevents
useful partial execution from being reported as complete acceptance coverage.
"""

from __future__ import annotations

from collections import Counter


REPORT = {"documentId": "evidence-42", "revision": 1,
          "selected": [{"id": "f1", "value": "blue"},
                       {"id": "f2", "value": "square"}]}
BUSINESS = ("readEvidence", "submit", "observe", "provideInput", "cancel", "cleanupCancel")
DISCOVERY = frozenset({"tools/list", "__card"})


def _exact(value, expected):
    """JSON structural equality with bool/int distinction and exact key sets."""
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return value.keys() == expected.keys() and all(_exact(value[key], item) for key, item in expected.items())
    if isinstance(expected, list):
        return len(value) == len(expected) and all(_exact(a, b) for a, b in zip(value, expected))
    return value == expected


def _events(value):
    """None means missing/malformed; [] is an observed empty ledger."""
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    return None


def _protocol_events(observed, name, protocol):
    value = observed.get(name)
    return _events(value.get(protocol)) if isinstance(value, dict) else None


def _all_protocol_events(observed, name):
    ledgers = [_protocol_events(observed, name, protocol) for protocol in ("mcp", "a2a")]
    return None if any(value is None for value in ledgers) else sum(ledgers, [])


def _has(events, event, **fields):
    return events is not None and any(item.get("event") == event and
        all(item.get(key) == value for key, value in fields.items()) for item in events)


def _measured(observed):
    """Apply explicit half-open observation offsets without deleting raw setup."""
    window = observed.get("measuredWindow")
    if window is None:
        return observed, []
    if not isinstance(window, dict):
        return observed, ["measuredWindow must be an object"]
    result, errors = dict(observed), []

    def portion(values, bounds, label):
        if not isinstance(bounds, dict) or _events(values) is None:
            errors.append(label + " lacks a ledger or bounds")
            return None
        start, end = bounds.get("start"), bounds.get("end")
        if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(values):
            errors.append(label + " has invalid offsets")
            return None
        return values[start:end]

    for key in ("trace", "requests"):
        if key in window:
            result[key] = portion(observed.get(key), window[key], key)
    for key in ("peers", "proxy"):
        if key in window:
            original, bounds = observed.get(key), window[key]
            result[key] = {}
            for protocol in ("mcp", "a2a"):
                result[key][protocol] = portion(original.get(protocol) if isinstance(original, dict) else None,
                    bounds.get(protocol) if isinstance(bounds, dict) else None, key + "." + protocol)
    return result, errors


def _probe_normalization(observed):
    probe = observed.get("probe")
    probe = probe if isinstance(probe, dict) else {}
    kind = probe.get("kind")
    error = probe.get("error")
    error = error if isinstance(error, dict) else {}
    categories, phases, layer = [], [], "shared_adapter"
    code = error.get("code")
    if kind == "header_codec":
        if not error and isinstance(probe.get("encoded"), str) and isinstance(probe.get("decoded"), str):
            categories, phases = ["probe_accepted"], ["codec"]
    elif kind == "descriptor_validation":
        if code in {"BindingChanged", "ProtocolRejected"}:
            categories, phases = ["descriptor_rejected"], ["binding_validation"]
    elif kind == "task_state_decode":
        state_categories = {"Submitted": "pending", "Working": "working", "InputRequired": "input_required",
            "AuthRequired": "auth_required", "Completed": "remote_completed", "Failed": "remote_failed",
            "Canceled": "remote_canceled", "Rejected": "remote_rejected"}
        if probe.get("normalizedState") in state_categories:
            categories, phases = [state_categories[probe["normalizedState"]]], ["decode"]
        elif code == "UnsupportedRemoteState":
            categories, phases = ["unsupported_remote_state"], ["decode"]
    elif kind == "reference_serialization":
        raw = probe.get("roundtripResult")
        if probe.get("operation") == "deserialize_roundtrip" and isinstance(raw, dict) and raw.get("kind") == "Error" and raw.get("code") == "InvalidReference":
            categories, phases = ["admission_denied"], ["pre_dispatch"]
        elif probe.get("operation") == "serialize_wrapper" and isinstance(probe.get("serializedWrapper"), str):
            categories, phases = ["probe_accepted"], ["codec"]
    elif kind == "peer_request":
        requests = _events(observed.get("requests"))
        last = requests[-1] if requests else {}
        status, body = last.get("status"), last.get("body")
        rpc_error = body.get("error") if isinstance(body, dict) else None
        rpc_code = rpc_error.get("code") if isinstance(rpc_error, dict) else None
        layer, phases = "remote_peer", ["peer_receive"]
        if status == 401:
            categories = ["authentication_denied"]
        elif status == 403 or rpc_code == -32001 and _has(_all_protocol_events(observed, "peers"), "task_access_denied"):
            categories = ["authorization_denied"]
        elif type(status) is int and 400 <= status < 500 or rpc_code in {-32600, -32601, -32602}:
            categories = ["protocol_rejected"]
        elif status == 200 and isinstance(body, dict) and "result" in body and last.get("method") == "server/discover":
            categories = ["probe_accepted"]
    elif isinstance(observed.get("probeCalls"), list) and observed["probeCalls"]:
        last = observed["probeCalls"][-1]
        raw = last.get("result") if isinstance(last, dict) else None
        raw = raw if isinstance(raw, dict) else {}
        code = raw.get("code")
        trace = _events(observed.get("trace"))
        if raw.get("kind") == "Error" and code in {"AuthorityDenied", "InvalidReference", "BudgetDenied", "RootTerminated"}:
            categories, phases, layer = ["admission_denied"], ["pre_dispatch"], "shared_host"
        elif raw.get("kind") in {"Evidence", "Task"}:
            categories, phases, layer = ["probe_accepted"], ["receive"], "shared_host"
        elif code == "BindingChanged":
            categories, phases, layer = ["binding_changed"], ["pre_dispatch"], "shared_adapter"
        else:
            layer = None
    else:
        return None
    return {"code": code, "remoteOutcome": error.get("remoteOutcome"),
            "categories": categories, "phases": phases, "layer": layer,
            "conclusive": len(categories) == 1 and len(phases) == 1}


def normalize_outcome(observed):
    """Normalize receipt observations without consulting the expected case.

    A wire/validation error code is intentionally not enough to infer a unique
    semantic phase. Observed proxy mutations narrow it only where the receipt
    actually identifies the mutation that reached the adapter.
    """
    probe_result = _probe_normalization(observed)
    if probe_result is not None:
        return probe_result
    result = observed.get("result")
    result = result if isinstance(result, dict) else {}
    trace = _events(observed.get("trace"))
    worker = observed.get("worker")
    calls = _events(worker.get("calls")) if isinstance(worker, dict) else None
    last_call = calls[-1] if calls else {}
    proxy = _all_protocol_events(observed, "proxy")
    mutations = {item.get("mutation") for item in proxy or []
                 if item.get("event") == "response_mutated"}
    code = result.get("outcome", result.get("code"))
    categories, phases, layer = [], [], None
    if code == "Success" and _has(trace, "publication", success=True):
        categories, phases, layer = ["success"], ["publication"], "application"
    elif code == "NeedsInput" and last_call.get("state") == "InputRequired":
        categories, phases, layer = ["needs_input"], ["root_terminal"], "application"
    elif code == "DomainRejected" and last_call.get("state") == "Completed":
        categories, phases, layer = ["domain_rejected"], ["domain_validation"], "application"
    elif code == "AuthorizationRequired" and last_call.get("state") == "AuthRequired":
        categories, phases, layer = ["auth_required"], ["receive"], "remote_peer"
    elif code in {"RemoteFailed", "RemoteCanceled", "RemoteRejected"}:
        state = {"RemoteFailed": "Failed", "RemoteCanceled": "Canceled", "RemoteRejected": "Rejected"}[code]
        if last_call.get("state") == state:
            categories = [{"Failed": "remote_failed", "Canceled": "remote_canceled", "Rejected": "remote_rejected"}[state]]
            phases, layer = ["receive"], "remote_peer"
    elif code == "UnsupportedReply" and last_call.get("kind") == "DirectReply":
        categories, phases, layer = ["direct_reply"], ["receive"], "application"
    elif code == "PollLimit":
        categories, phases, layer = ["poll_limit"], ["pre_dispatch"], "application"
    elif code == "RootTerminated" and result.get("fatal") is True and _has(trace, "root_abort"):
        categories, phases, layer = ["root_cancelled"], ["root_terminal"], "shared_host"
    elif code == "Timeout" and result.get("fatal") is True:
        categories, phases, layer = ["root_deadline"], ["root_terminal"], "shared_host"
    elif code in {"TransportFailure", "Timeout"} and result.get("remoteOutcome") == "Unknown":
        if _has(trace, "transport_error", remoteOutcome="Unknown"):
            categories, phases, layer = ["delivery_unknown"], ["receive"], "shared_adapter"
    elif code == "CleanupFailure":
        categories, phases, layer = ["cleanup_failure"], ["cleanup"], "shared_host"
    elif code == "TaskNotCancelable" and last_call.get("operation") == "cancel":
        categories, phases, layer = ["cancel_refused"], ["receive"], "remote_peer"
    elif code == "UnsupportedRemoteState":
        categories, phases, layer = ["unsupported_remote_state"], ["receive"], "shared_adapter"
    elif code == "BudgetDenied":
        categories, phases, layer = ["admission_denied"], ["pre_dispatch"], "shared_host"
    elif code in {"AuthorityDenied", "InvalidReference"}:
        dispatches = [item for item in trace or [] if item.get("event") == "dispatch"]
        if not dispatches and trace is not None:
            categories, phases, layer = ["admission_denied"], ["pre_dispatch"], "shared_host"
        # A 401 and a 403 are currently collapsed by the host. No invented
        # distinction between authentication, authorization, and local denial.
    elif code == "BindingChanged":
        categories, phases, layer = ["binding_changed"], ["pre_dispatch"], "shared_adapter"
        if "required_extension" in mutations:
            categories = ["binding_changed", "unsupported_capability"]
    elif code == "TransportFailure" and "discovery_redirect" in mutations:
        categories, phases, layer = ["binding_rejected"], ["pre_dispatch"], "shared_adapter"
    elif code in {"ProtocolRejected", "ResponseLimit"}:
        evidence_schema = {"wrong_field_type", "tool_error", "missing_structured_content"}
        evidence_domain = {"wrong_document", "duplicate_fact_id", "wrong_revision"}
        response = {"malformed_json", "oversized_response", "over_depth"} | evidence_schema
        wire = {"evidence_response_id", "observe_taskId", "observe_contextId", "a2a_pre_1_envelope"}
        if mutations & response:
            categories, phases = ["response_rejected"], ["validation"]
        elif mutations & evidence_domain and last_call.get("operation") == "readEvidence":
            categories, phases = ["evidence_rejected"], ["validation"]
        elif mutations & wire:
            categories, phases = ["protocol_rejected"], ["receive"]
        elif "mcp_result_type" in mutations:
            categories, phases = ["protocol_rejected", "unsupported_capability"], ["receive"]
        elif code == "ResponseLimit":
            categories, phases = ["resource_denied"], ["receive"]
        else:
            categories = ["protocol_rejected", "response_rejected", "evidence_rejected"]
            phases = ["pre_dispatch", "receive", "decode", "validation"]
        layer = "shared_adapter"
    return {"code": code, "remoteOutcome": result.get("remoteOutcome"),
            "categories": categories, "phases": phases, "layer": layer,
            "conclusive": len(categories) == 1 and len(phases) == 1}


def _counts(observed):
    trace = _events(observed.get("trace"))
    counts = {key: None for key in BUSINESS}
    publications = None
    if trace is not None:
        dispatches = [item for item in trace if item.get("event") == "dispatch"]
        counts.update(readEvidence=sum(item.get("method") == "tools/call" for item in dispatches),
                      observe=sum(item.get("method") == "GetTask" and item.get("cleanup") is False for item in dispatches),
                      cancel=sum(item.get("method") == "CancelTask" and item.get("cleanup") is False for item in dispatches),
                      cleanupCancel=sum(item.get("method") == "CancelTask" and item.get("cleanup") is True for item in dispatches))
        sends = [item for item in dispatches if item.get("method") == "SendMessage"]
        a2a_proxy = _protocol_events(observed, "proxy", "a2a")
        forwarded = [item for item in a2a_proxy or [] if item.get("event") == "forward"
                     and item.get("operation") in {"submit", "provideInput"}]
        if not sends:
            counts.update(submit=0, provideInput=0)
        elif a2a_proxy is not None and len(forwarded) == len(sends):
            counts.update(submit=sum(item["operation"] == "submit" for item in forwarded),
                          provideInput=sum(item["operation"] == "provideInput" for item in forwarded))
        publications = sum(item.get("event") == "publication" and item.get("success") is True for item in trace)
    probe = observed.get("probe")
    if isinstance(probe, dict) and probe.get("kind") == "peer_request":
        requests = _events(observed.get("requests"))
        if requests is not None and all(isinstance(item.get("operation"), str) and isinstance(item.get("dispatched"), bool) for item in requests):
            counts = {key: sum(item["operation"] == key and item["dispatched"] for item in requests) for key in BUSINESS}
        else:
            counts = {key: None for key in BUSINESS}
    peers = _protocol_events(observed, "peers", "a2a")
    creations = None if peers is None else sum(item.get("event") == "created" for item in peers)
    return {"businessDispatches": counts, "peerTaskCreations": creations,
            "successfulPublications": publications}


def evaluate_case(case, observed):
    """Return checked, failed, and unverified obligations for one immutable case.

    ``observed`` is the runner's result/cleanup/trace/worker/peers/proxy receipt.
    No import or invocation of the system under test occurs here.
    """
    raw_observed = observed
    observed, window_errors = _measured(observed)
    expected = case["expected"]
    normalized = normalize_outcome(observed)
    counts = _counts(observed)
    checks = []

    def check(name, status, reason, **details):
        checks.append({"name": name, "status": status, "reason": reason, **details})

    def condition(name, verified, reason, **details):
        check(name, "unverified" if verified is None else "passed" if verified else "failed", reason, **details)

    if window_errors:
        check("measurement_window", "unverified", "; ".join(window_errors))

    channel_scan = observed.get("applicationChannelScan")
    if isinstance(channel_scan, dict):
        channels = _events(channel_scan.get("channels"))
        expected_channels = {"applicationFinish", "stderr", "unexpectedStdout", "ordinaryHostTrace", "peerWitnesses", "proxyWitnesses"}
        complete = channels is not None and {item.get("name") for item in channels} == expected_channels and channel_scan.get("complete") is True
        metrics_valid = channels is not None and all(type(item.get(key)) is int and item[key] >= 0
            for item in channels for key in ("entries", "bytes", "credentialMatches", "referenceMatches"))
        leaked = channels is not None and any(item.get("credentialMatches", 0) > 0 or item.get("referenceMatches", 0) > 0 for item in channels)
        condition("observation.application_channel_scan", False if leaked else True if complete and metrics_valid else None,
                  "Scan covers named emitted channels; trusted RPC transport is excluded and source-internal visibility is a separate obligation.")

    for field, candidates in (("outcomeCategory", normalized["categories"]), ("phase", normalized["phases"])):
        wanted = expected[field]
        condition(field, None if not candidates or len(candidates) > 1 and wanted in candidates
                  else wanted in candidates, "Derived from result, call observations, and trace; ambiguity is retained.",
                  expected=wanted, actual=candidates)
    for operation in BUSINESS:
        value, bounds = counts["businessDispatches"][operation], expected["businessDispatches"][operation]
        condition("count." + operation, None if value is None else bounds["min"] <= value <= bounds["max"],
                  "Committed host dispatches; SendMessage classification requires matching independent proxy forwards.",
                  actual=value, expected=bounds)
    for field in ("peerTaskCreations", "successfulPublications"):
        value, bounds = counts[field], expected[field]
        condition("count." + field, None if value is None else bounds["min"] <= value <= bounds["max"],
                  "Peer creation ledger or host publication events, excluding no unrecorded setup.", actual=value, expected=bounds)

    trace = _events(observed.get("trace"))
    worker = observed.get("worker")
    worker = worker if isinstance(worker, dict) else {}
    calls = _events(worker.get("calls"))
    peers = _all_protocol_events(observed, "peers")
    proxy = _all_protocol_events(observed, "proxy")
    tasks = _protocol_events(observed, "peers", "a2a")
    result = observed.get("result")
    result = result if isinstance(result, dict) else {}
    publications = [item for item in trace or [] if item.get("event") == "publication"]
    dispatches = [item for item in trace or [] if item.get("event") == "dispatch"]
    mutations = {item.get("mutation") for item in proxy or [] if item.get("event") == "response_mutated"}
    probe = observed.get("probe")
    probe = probe if isinstance(probe, dict) else {}

    # Presence is separate from satisfying an invariant. A coarse ledger is
    # usable as a witness but cannot prove information it never recorded.
    available = set()
    if normalized["categories"]:
        available.add("normalized_outcome")
    if trace is not None:
        available.update({"host_trace", "host_admission_log"})
    if peers is not None:
        available.add("peer_wire_log")
    if tasks is not None:
        available.add("peer_task_ledger")
    if proxy is not None:
        available.add("fault_proxy_log")
    if calls is not None and any(item.get("kind") == "Task" for item in calls):
        available.add("normalized_task_observation")
    if tasks is not None and any(item.get("event") == "continued" and isinstance(item.get("includeIds"), list) for item in tasks):
        available.add("peer_continuation_input")
    if isinstance(result.get("report"), dict):
        available.add("report")
    if _events(observed.get("cleanup")) is not None and isinstance(worker.get("retired"), bool):
        available.add("cleanup_witness")
    if isinstance(worker.get("retired"), bool) and isinstance(worker.get("returncode"), int):
        available.add("worker_exit_witness")
    if isinstance(worker.get("barriers"), list) and worker["barriers"]:
        available.add("clock_barrier_log")
    if _has(peers, "stream_cancelled"):
        available.add("peer_stream_disconnect")
    if probe.get("kind") == "header_codec" and isinstance(probe.get("encoded"), str):
        available.add("codec_output")
        if isinstance(probe.get("decoded"), str):
            available.add("independent_header_decoder")
    if probe.get("kind") == "descriptor_validation" and isinstance(probe.get("descriptor"), dict):
        available.add("validated_tool_catalog")
    if probe.get("kind") == "task_state_decode":
        available.add("normalized_task_observation")
        if isinstance(probe.get("sdkEnumName"), str) or type(probe.get("sdkEnumNumber")) is int:
            available.add("independent_protocol_schema")
    if probe.get("kind") == "reference_serialization" and isinstance(probe.get("serializedWrapper"), str):
        available.add("codec_output")
    schema = observed.get("schemaValidation")
    requests = _events(observed.get("requests"))
    if not isinstance(schema, dict) and requests:
        schema = requests[-1].get("schemaValidation")
    if isinstance(schema, dict) and isinstance(schema.get("schemaName"), str) and isinstance(schema.get("accepted"), bool):
        available.add("independent_protocol_schema")
    if _has(peers, "denied") or _has(peers, "task_access_denied"):
        available.add("peer_rejection_log")
    if probe.get("kind") == "peer_request" and _events(observed.get("requests")) is not None:
        available.add("peer_wire_log")
        if any(type(item.get("status")) is int and item["status"] >= 400 or
               isinstance(item.get("body"), dict) and "error" in item["body"] for item in observed["requests"]):
            available.add("peer_rejection_log")
    for witness in expected["witnesses"]:
        condition("witness." + witness, True if witness in available else None,
                  "Required observation is present." if witness in available else "Required independent observation is absent.")

    invariant_results = {}
    for invariant in expected["invariants"]:
        value, reason = None, "The current receipt does not observe enough evidence to prove this invariant."
        if invariant == "one_terminal":
            value = None if trace is None else len(publications) <= 1
            reason = "Count every terminal publication event, including unsuccessful terminals."
        elif invariant == "exact_report":
            # Independent literal fixture, never import the application's domain validator.
            value = None if "report" not in result else _exact(result["report"], REPORT) and result.get("outcome") == "Success"
            reason = "Compare the entire report, including field set and selected ID order, to the independent fixture."
        elif invariant == "attribution_recorded":
            value = None if not normalized["conclusive"] or normalized["layer"] is None else normalized["layer"] in case["attribution"]
            reason = "Attribution is inferred from the observed result and call phase, not the source language label."
        elif invariant == "no_automatic_resend":
            submit, continuation = counts["businessDispatches"]["submit"], counts["businessDispatches"]["provideInput"]
            value = None if submit is None or continuation is None else submit <= 1 and continuation <= 1
            reason = "Observe at most one dispatched submit and one dispatched continuation."
        elif invariant == "same_task":
            if tasks is not None:
                created = [item for item in tasks if item.get("event") == "created"]
                followups = [item for item in tasks if item.get("event") in {"continued", "observed", "canceled", "cancel_refused"}]
                value = len(created) == 1 and all(item.get("taskId") == created[0].get("taskId") for item in followups)
                if value:
                    # The task ID is observable here; continuation context is
                    # not in today's peer ledger and must not be invented.
                    value = None
                reason = "Peer task IDs are checked; continuation context correlation is not yet recorded."
        elif invariant == "no_task_ref_on_unknown_submit":
            if calls is not None and counts["businessDispatches"]["observe"] is not None:
                bad = any(item.get("kind") == "Task" for item in calls) or counts["businessDispatches"]["observe"] > 0
                value = False if bad else None
                reason = "Task observations and blind polls can be disproved; complete source-visible response/reference scanning is still required."
        elif invariant == "no_secret_exposure":
            if observed.get("credentialLeakDetected") is True:
                value = False
            if isinstance(channel_scan, dict) and _events(channel_scan.get("channels")) is not None:
                if any(item.get("credentialMatches", 0) > 0 or item.get("referenceMatches", 0) > 0 for item in channel_scan["channels"]):
                    value = False
            reason = "Credential leakage is checked when reported; a clean receipt scan alone does not cover reference tokens or all source-visible values."
        elif invariant == "no_late_application":
            if trace is not None:
                aborts = [i for i, item in enumerate(trace) if item.get("event") == "root_abort"]
                closes = [i for i, item in enumerate(trace) if item.get("event") in {"root_close", "root_abort"}]
                late_dispatch = closes and any(item.get("event") == "dispatch" and not item.get("cleanup") for item in trace[closes[0] + 1:])
                late_success = aborts and any(item.get("event") == "publication" and item.get("success") for item in trace[aborts[0] + 1:])
                if late_dispatch or late_success or worker.get("responsesAfterFatal", 0) > 0:
                    value = False
                reason = "Reject observed late dispatch/success/response; full source-continuation ordering is not recorded."
        elif invariant == "discovery_metered":
            if trace is not None:
                admitted = Counter((item.get("protocol"), item.get("method"), item.get("request")) for item in trace if item.get("event") == "admitted")
                traced = Counter((item.get("protocol"), item.get("method"), item.get("request")) for item in dispatches if item.get("method") in DISCOVERY)
                if any(count > admitted[key] for key, count in traced.items()):
                    value = False
                reason = "Discovery admission is cross-checked; remaining request/byte/time ledger observations are needed for full metering proof."
        elif invariant == "bounded_cleanup":
            if worker.get("retired") is False or worker.get("supervisorJoined") is False:
                value = False
            reason = "Worker retirement is observed; a separately measured root-close/retirement duration is required to establish the cleanup deadline."
        elif invariant == "compatible_missing_result_type":
            if "omit_mcp_result_type" in mutations:
                value = result.get("outcome") == "Success" and _has(trace, "received", protocol="mcp", method="tools/call")
                reason = "Proxy witnesses omitted resultType and the complete application succeeds."
        elif invariant == "valid_control":
            if normalized["categories"] == ["success"] and _exact(result.get("report"), REPORT):
                value = True
                reason = "This positive control independently publishes the exact expected report."
            elif probe.get("kind") == "header_codec":
                value = probe.get("decoded") == probe.get("input") if isinstance(probe.get("decoded"), str) else None
                reason = "The independent decoder recovers the actual accepted input."
            elif probe.get("kind") == "peer_request" and requests:
                request = requests[-1]
                body = request.get("body")
                if request.get("method") == "server/discover" and isinstance(body, dict) and isinstance(schema, dict):
                    value = request.get("status") == 200 and schema.get("accepted") is True and body.get("id") == request.get("requestId")
                    reason = "The actual server/discover response satisfies the independent pinned SDK schema and request correlation."
        elif invariant == "header_roundtrip":
            if probe.get("kind") == "header_codec" and isinstance(probe.get("decoded"), str):
                value = _exact(probe["decoded"], probe.get("input"))
                reason = "Compare independently decoded text with the original codec input."
        elif invariant == "no_authority_roundtrip":
            if probe.get("kind") == "reference_serialization":
                before, after, raw = probe.get("bridgeCallsBefore"), probe.get("bridgeCallsAfter"), probe.get("roundtripResult")
                if type(before) is int and type(after) is int and isinstance(raw, dict):
                    value = probe.get("serializedWrapper") == "{}" and before == after and raw.get("kind") == "Error" and raw.get("code") == "InvalidReference"
                    reason = "Serialized application wrapper is inert; its deserialized copy is rejected before bridge dispatch."
        elif invariant == "counts_exclude_setup":
            window = raw_observed.get("measuredWindow")
            required = {"trace", "peers", "proxy"}
            if isinstance(window, dict) and required <= window.keys() and not window_errors:
                value = True
            reason = "Explicit half-open offsets delimit observed setup from measured host/peer/proxy ledgers."
        condition("invariant." + invariant, value, reason)
        invariant_results[invariant] = "unverified" if value is None else "passed" if value else "failed"

    # Truncated logs can never establish zero effects or complete coverage.
    for name, ledger in (("trace", trace), ("peers", peers), ("proxy", proxy)):
        if _has(ledger, "witness_limit"):
            check("complete." + name, "unverified", "Witness capacity was reached; receipt coverage is incomplete.")
    # Static cases cannot acquire execution credit from runtime-like receipts.
    if case.get("surface") in {"source_check", "source_mutant"}:
        check("static_execution", "unverified", "An actual checked effectful Meda compiler receipt is required.")
    statuses = {item["status"] for item in checks}
    status = "failed" if "failed" in statuses else "unverified" if "unverified" in statuses else "passed"
    return {"caseId": case["id"], "status": status, "passed": status == "passed",
            "normalized": normalized, "counts": counts, "checks": checks,
            "invariants": {"checked": [key for key, value in invariant_results.items() if value == "passed"],
                           "failed": [key for key, value in invariant_results.items() if value == "failed"],
                           "unverified": [key for key, value in invariant_results.items() if value == "unverified"]},
            "witnesses": {"available": sorted(available),
                          "missing": sorted(set(expected["witnesses"]) - available)}}
