# Bounded MCP and A2A workflow specification

Status: **Planned; no execution or conformance result yet.** Profile:
`meda-interop-d0/1`. Updated October 25,
2026. This is the next experiment after the [shared runtime comparison](runtime-comparison.md).
It tests real Meda and TypeScript clients using the same host and adapters.

Read synthetic MCP evidence, delegate a deterministic A2A report, then validate
it. No paid model or production account is required. Protocol-specific behavior
belongs in adapters, not the language grammar.

## 1 Versioned protocol profile

Pin **MCP 2026-07-28 Streamable HTTP** and **A2A v1.0.0 JSON-RPC over HTTP**.
Standards requirements come from the linked specifications; additional restrictions
belong to this profile.

| Boundary | Wire contract |
| --- | --- |
| MCP discovery | `tools/list`, with bounded pagination. The peer implements `server/discover`; clients may omit that optional request. |
| MCP evidence read | `tools/call`, name `evidence.read`, argument `{documentId: "evidence-42"}`. The descriptor supplies input and output schemas. |
| MCP transport | A separate POST with `Content-Type: application/json` for each JSON-RPC request. Send `Accept: application/json, text/event-stream`; implement JSON and request-scoped SSE responses. |
| MCP metadata | Each request includes `params._meta` protocol version and client capabilities; this profile also supplies client name/version. Headers include matching `MCP-Protocol-Version` and `Mcp-Method`; `tools/call` also has matching `Mcp-Name`. No initialize handshake or protocol session is used. |
| A2A discovery | Fetch the configured `/.well-known/agent-card.json`; select the pinned compatible `JSONRPC` interface and origin. Send `A2A-Version: 1.0`. |
| A2A operations | POST JSON-RPC with `Content-Type: application/json`. `SendMessage` starts or continues; `GetTask` observes; `CancelTask` requests cancellation. `GetTask` and `CancelTask` use `params.id`. |

MCP [transport rules](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
and [request metadata](https://modelcontextprotocol.io/specification/2026-07-28/basic/index)
govern these details. Implement `x-mcp-header` parameter mirroring, descriptor
constraints, and prescribed ASCII/Base64-sentinel encoding; exclude invalid tool
descriptors and reject header/body mismatches. The approved `documentId` string
declares `x-mcp-header: DocumentId`. Test encoding independently of document access.
Bound SSE events, correlate notifications, accept one matching final response,
and retire the stream. The profile excludes subscriptions and advertises no
elicitation capability; unsupported input requests cannot initiate another tool
or credential flow.

The peer's required `server/discover` behavior is checked separately against
[MCP versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning).
It is not an extra mandatory client handshake.

For A2A, a new `SendMessage` has a fresh `messageId`, `role: ROLE_USER`, one
structured `data` part, and `configuration.returnImmediately: true`. A response
contains either `task` or `message`; a valid direct message becomes
`DirectReply`, which this task-based application rejects without inventing a
task. A continuation sends a new message ID with the existing task ID and, when
known, its matching context ID. Task IDs are server-issued. The
[pinned specification](https://a2a-protocol.org/v1.0.0/specification/)
defines these envelopes and methods. Do not reuse pre-1.0 method names or `kind`
discriminators. A2A streaming, push notifications, and required extensions are
not advertised by the controlled peer.

## 2 Application contract

Freeze these application contracts before implementing clients.

The MCP descriptor's `outputSchema` requires exactly:

```json
{"documentId":"evidence-42","revision":1,"facts":[{"id":"f1","value":"blue"},{"id":"f2","value":"square"}]}
```

Use `structuredContent` as the authoritative evidence value. Normalize an absent
MCP `resultType` to `complete` as required for client compatibility; an explicitly
unknown value is invalid. The controlled 2026 peer emits `resultType`, while a
compatibility fixture omits it and must still succeed with valid content. Require a complete,
non-error tool result and independently validate the local schema, unique fact
IDs, exact requested document ID, and revision. Text content remains untrusted
display data; never parse it as a fallback success. The MCP
[tools specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
distinguishes structured tool results, output schemas, and tool errors. The
host's audited read classification is not inferred from a server's annotation.

The A2A request data is `{kind: "evidence-report", evidence: <validated evidence>,
includeIds: ["f1", "f2"]}`. Here `kind` is an application field inside `data`,
not an A2A discriminator. A controlled clarification variant omits `includeIds`.
The peer requests that value; the harness supplies it through a live-root input
channel. The client sends at most one continuation. An input-required snapshot
can be observed while that same root remains open. With no supplied answer, the
controller finishes as `NeedsInput` and closes the root; it neither invents an
answer nor starts a replacement task. A controller that elects to wait remains
subject to the root deadline. Deadline expiry is a fatal root outcome, not
`NeedsInput` or success.

Successful completion requires one artifact with one JSON `data` part containing
exactly `{documentId: "evidence-42", revision: 1, selected: [{id: "f1", value:
"blue"}, {id: "f2", value: "square"}]}`. Each arm's pure application validator checks
requested ID order, exact membership, values, revision, and absence of extras.
A completed remote task with invalid output yields `DomainRejected`, never
application success. This checks agreement with supplied evidence, not truth
about the world. Both validators implement the same pinned contract; the
independent acceptance oracle computes expected values separately. Domain
acceptance belongs to application code, while the shared host validates protocol
and response schemas.

## 3 Binding and authority

The host owns endpoint URLs, credentials, tool allowlists, schema identities,
effect classifications, grants, and quota state. Both language clients call the
same typed binding surface: `readEvidence`, `submit`, `observe`, `provideInput`,
and `cancel`. Binding effects distinguish evidence read, task submission,
observation, continuation, and cancellation; ordinary source cannot obtain a raw
network escape hatch. Discovery is host control work, still metered and traced.
Any static Meda advantage is measured separately from enforcement both clients
receive from this host.

Use two independently launched local peers over TLS with a test CA trusted only
by the harness. Give each peer a distinct random bearer credential. Its registry
maps that credential to principal, tenant, resource audience, allowed operations,
and expiry; servers actually validate these fields and task ownership on every
request. An asserted principal/tenant header is not authentication. Invalid,
expired, wrong-audience, and cross-principal requests must fail. Credentials stay
in the host and must be absent from source values, reports, and ordinary logs.

This is a **pre-provisioned credential test profile**, not production identity or
full MCP OAuth conformance. MCP
[authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
is a separate HTTP authorization specification. Interactive authorization,
discovery of authorization servers, token acquisition/refresh, and consent UX
are deferred and cannot be advertised as implemented. A2A `AUTH_REQUIRED`
becomes a blocked authorization outcome; no credential is sent in task content.

At admission, the host re-fetches the applicable tool descriptor or Agent Card,
checks its canonical digest against the run manifest, and compares endpoint,
version, schemas, and required capabilities. Observed drift yields
`BindingChanged` before the business request; never silently regenerate bindings
or broaden authority. Redirects are rejected. Discovery itself has fixed allowed
origins. This detects observed drift, not an impossible atomic guarantee that a
remote implementation cannot change between discovery and dispatch. Response
validation remains mandatory.

## 4 Root and task lifecycle

`TaskRef` is an opaque host-issued reference containing a private registry key.
The registry binds it to root, authenticated principal/tenant, adapter and schema
identity, endpoint, task ID, and optional context ID. Meda's opaque type and the
TypeScript client's strongest practical typed wrapper use this same registry.
Host validation rejects forged, foreign, expired, or closed-root references even
when a checker is bypassed. Meda rejects generic handle serialization statically.
TypeScript may serialize an inert wrapper such as `{}`; no usable token or secret
may escape, and deserialization cannot restore authority.

The root stays live during clarification, polling, and explicit cancellation.
On root closure, all local references become invalid. `NeedsInput` includes the
last remote observation and cleanup status, not a resumable handle. There is no detach,
cross-root reattach, restart recovery, or durable handle claim. Remote work can
outlive local cleanup; ownership of local work is not proof of remote deletion.

Track remote task state separately from request delivery and local root outcome.
Map known remote states to pending, working, input-required, auth-required, or
their distinct terminal outcomes. Unknown/unspecified states stop dependent
effects with `UnsupportedRemoteState`. Task ID/context mismatches fail validation.
The [A2A task lifecycle](https://a2a-protocol.org/v1.0.0/topics/life-of-a-task/)
provides the remote concepts; the following local restrictions are ours.

A lost response after dispatch is `Unknown`, not proof of failure. In particular,
a lost submission acknowledgement may leave no trustworthy task ID to poll.
Do not automatically resend submissions or continuations. A2A message-ID
deduplication is optional; IDs are correlation, not an exactly-once guarantee.
The shared host atomically enforces at most one submission dispatch and one
continuation dispatch per root, even for explicit repeat calls. An unknown receipt
never releases either allowance. Credit this protection to the host; it does not
promise exactly-once execution across roots or inside a remote server. Recovery
by a new explicitly authorized root is outside scope.

An explicit source `cancel` is an ordinary granted `CancelTask` request while the
root remains live. It consumes normal allowance and returns a typed observation
or error; the application may then inspect the outcome or finish.

Root abort or closure instead closes application admission and records ordering.
Only the host may use reserved cleanup authority for `CancelTask` on a known task.
An acknowledgement, terminal-state refusal, or lost reply is recorded separately.
Closing an MCP HTTP response stream signals cancellation
under the [MCP cancellation rules](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/cancellation).
Neither cancellation mechanism proves rollback. Join local workers and waits
within the cleanup allowance; otherwise terminate the isolated worker and report
fatal `CleanupFailure`. After root closure, no late result may execute source code
or publish success.

## 5 Default resource limits and observable outcomes

Freeze these experiment limits equally across clients.

| Resource | Default |
| --- | --- |
| Root work deadline | 15 seconds monotonic, including discovery, waits, decoding, and final validation |
| Individual HTTP request | 2 seconds, capped by remaining root time, or remaining cleanup time for reserved cleanup work |
| Cleanup extension | 1 second after root closure; no application work |
| Outbound requests | 16 total, including discovery and cancellation; 2 reserved for cleanup, unavailable to application work |
| Concurrent local requests | 1; host caps submission and continuation dispatches at one each per root |
| Polling | At most 3 polls, with 100 ms minimum between polls; polling consumes normal request allowance |
| Discovery | At most 2 tool-list pages per discovery; bounded by normal request allowance |
| Input/output | 64 KiB per request/response, 256 KiB cumulative inbound bytes, JSON nesting at most 16 |
| MCP SSE | At most 16 events, each at most 16 KiB, within the same response and aggregate byte limits |
| Logical values | At most 32 facts, each text at most 256 Unicode scalars; integers limited to 0 through 1,000,000 |
| Worker containment | 256 MiB process limit; 100,000 evaluator steps for Meda, plus the common supervised deadline |

Counter exhaustion is a typed admission denial before dispatch. Root deadline,
cancellation, memory failure, and containment failure are terminal root outcomes.
Completion may publish with zero remaining call allowance if full validation has
finished while the root remains live; the call budget is not a publication
budget. Progress cannot extend the root deadline. Byte limits apply while reading
streams, not after buffering them. Compiler/schema work has a separate 10-second,
256 MiB supervised limit and is charged to experiment cost.

Trace metadata includes run/build/binding identities, operation and occurrence
IDs, admission decisions, requests begun, bytes, sanitized outcome categories,
task-reference lineage, cancellation ordering, and one terminal publication.
Unknown remote outcome/usage remains unknown. Raw credentials and response content
are excluded; authorized fixture capture is a separate channel.

## 6 Acceptance corpus

Enumerate each family's cases, expected phase/outcome, dispatches, task creations,
publication count, and cleanup witness. These families are not independent
statistical tasks.

| ID | Observable acceptance assertions |
| --- | --- |
| W01 Successful flow | JSON and request-scoped SSE evidence variants produce the exact report, one created task, and one successful publication. |
| W02 Clarification | Input resumes the same task/context once; peer records the supplied IDs. No answer creates no replacement task and ends as NeedsInput with cleanup status. Waiting past deadline remains fatal. |
| W03 Unknown delivery | Drop submission or continuation response after peer receipt. Record Unknown, zero automatic resends, at most one task; no false success or NotStarted. |
| W04 Cancel and race | Cancel while pending; race completion before/after local closure; lose cancellation response. At most one publication, no late source continuation, independently observed local cleanup. |
| W05 Protocol identity | Wrong version/header pairing, RPC ID, task/context ID, unsupported extension, or A2A legacy envelope cannot advance. Exercise header mirroring/encoding, invalid descriptors, and peer `server/discover`. Distinguish direct reply from malformed protocol; valid MCP results without resultType retain the specified compatibility behavior. |
| W06 Authentication and grants | Missing/expired/wrong-audience credential, cross-principal task access, ungranted continuation/cancel, and forged handle fail; authorized controls pass. |
| W07 Descriptor drift | Change tool schema, selected endpoint, required capability, or Agent Card identity before admission. Reject before the business dispatch; discovery counts remain visible. |
| W08 Data acceptance | Malformed, oversized, over-depth, tool-error, wrong-document, duplicate-fact, and domain-wrong completed artifact variants never publish success. |
| W09 Resource boundaries | Zero ordinary requests, exact final allowance, infinite progress, excess pages/events, and byte/deadline exhaustion respect the frozen limits and cleanup reserve. |
| W10 Handle lifetime | Meda rejects serialization statically; TypeScript may emit inert data, never credentials or restorable authority. Forgery, roundtrip restoration, stale-root and foreign-root use fail; live-root controls pass. |
| W11 Remote states | Submitted/working/input-required/auth-required/completed/failed/canceled/rejected and unknown-state cases preserve distinctions and have explicit application outcomes. |
| W12 Attribution | Bypass both checkers; remove host grant/quota checks in isolated mutants; inject well-typed client mistakes and a wrong domain validator. Independent oracles detect each relevant regression. |

The planned execution requires an external fault proxy, independent assertions,
and at least one local upstream SDK-based peer per protocol, after exact compatible
versions are pinned. No such interoperability result exists yet. Shared host/peer code alone is
insufficient interoperability evidence. Preserve raw outcomes and failed attempts.
Passing this corpus supports only this versioned profile, not universal protocol
conformance, agent intelligence, or language superiority.

## 7 Admission and stopping conditions

Before any claimed execution, freeze a manifest containing specification URLs and
content digests, exact SDK/package versions and lockfile hashes, protocol schemas,
tool descriptor and Agent Card digests, host/client/compiler builds, fixtures,
grants, credential-profile identity, limits, expected test IDs, and exclusions.
Unresolved SDK compatibility or missing required transport behavior blocks the
run; do not silently substitute the old custom fixture and label it standard.

Stop implementation expansion if the slice requires unrelated language features,
if both clients cannot receive equivalent host facilities, or if the selected
protocol requirements cannot fit the stated profile. Record the conflict and
revise the profile before collecting comparative results. Never add application
specific compiler knowledge to obtain a passing workflow.

Deferred: production OAuth and deployment hardening; MCP legacy compatibility,
subscriptions, Tasks extension, sampling, elicitation, and stdio; A2A streaming,
push notifications, files/URLs, arbitrary extensions, and multi-agent fan-out;
durability, reattach, replay, caches, global remote quotas, and real model quality.
The subsequent maintenance comparison and product decision follow
[the evaluation protocol](interop-evaluation.md); this workflow's correctness
alone does not establish Meda's maintenance advantage.
