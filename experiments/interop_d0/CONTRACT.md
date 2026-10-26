# D0 implementation interfaces

Working implementation contract for D0-01 through D0-03. Profile
`meda-interop-d0/1`; Meda source execution is a later dependent packet. Normative
scope remains docs/interop-workflow.md. Acceptance inventory is authored
independently. This file coordinates the implementation; it is not a passed gate.

## Shared host API

Python `host.py` exposes `Host(config)` with `call(operation, arguments) -> dict`,
`finish(application_result) -> dict`, and `trace` list. Host config is trusted
controller input: MCP URL, A2A URL, credentials, test CA path, pinned descriptor
and Agent Card, principal/tenant, resource limits. Config never enters client
source. Prefer explicit keyword config dataclass; describe exact fields in code.

Operations: `readEvidence` arguments `documentId`; `submit` arguments `evidence`
and optional `includeIds`; `observe` and `cancel` arguments `ref`; `provideInput`
arguments `ref` and `includeIds`. Each submission/continuation gets a fresh ID.

Call results are discriminated by `kind`:

- `Evidence`: `value` is validated evidence data.
- `Task`: `ref` is a host-minted opaque transport token; `state` is one of
  Submitted, Working, InputRequired, AuthRequired, Completed, Failed, Canceled,
  Rejected; `artifact` is decoded application data only when present.
- `DirectReply`: no task reference; the workflow rejects it as unsupported.
- `Error`: `code` is a stable category, `remoteOutcome` is NotStarted, Completed
  or Unknown; `fatal` marks a terminated root. Never expose remote raw messages.

Errors include AuthorityDenied, BindingChanged, BudgetDenied, Timeout,
ProtocolRejected, ResponseLimit, UnsupportedRemoteState, TransportFailure,
RootTerminated, InvalidReference and CleanupFailure. Lost dispatched responses
have remoteOutcome Unknown. Root deadline/containment errors are fatal.

`finish` closes the root, performs bounded authorized cleanup and returns
`{result, cleanup, trace}`. A fatal root outcome overrides proposed application
success. Application publication occurs at most once. Trace excludes secrets and
raw content; local peer/proxy witnesses are separately controlled test evidence.

## TypeScript worker

Sources in `client/` compile to ignored `dist/`. `main.ts` reads one initial
stdin JSON line `{kind: "start", input: {...}}`, then performs actual awaited
host calls. Each emits a stdout JSON line `{kind: "call", id, operation,
arguments}` and waits for stdin `{kind: "response", id, value: <call result>}`.
Final output is `{kind: "finish", result: <application result>}`. Stdout contains
only this protocol. Failures terminate explicitly; no implicit retry.

The trusted binding module uses private wrapper/WeakMap membership for task
references. Application policy cannot construct a usable TaskRef or obtain its
transport token through ordinary observers. JSON.stringify may produce inert
data. Source is a trusted prototype until actual worker isolation is verified;
do not claim compiler checks constitute an OS boundary.

Input fields: documentId default evidence-42, includeIds default [f1,f2],
requestClarification boolean, suppliedInput optional list, cancelAfterSubmit
boolean. Optional controls for negative client probes live in separate mutant
sources, not normal production branches.

Application result: `{outcome, report?}` where outcome is Success, NeedsInput,
DomainRejected, AuthorizationRequired, RemoteFailed, RemoteCanceled,
RemoteRejected, UnsupportedReply, PollLimit or the host's Error code. Errors
retain remoteOutcome/fatal metadata. Validate report in application source using
the same domain contract before claiming Success. Poll at most three times;
host owns minimum poll spacing and quotas. InputRequired with suppliedInput
continues the existing task once; otherwise finish NeedsInput.

## Upstream SDK peers

`sdk_peers.py` exposes a process CLI for each peer, using installed pinned SDKs.
Use separate processes and local TLS. A controller config supplies port, CA-issued
certificate/key, credential registry, fault/scenario and private witness path.
Export descriptor/card builders for manifest preparation; clients must never
import peer handlers. Peer observations record protocol methods, task creations,
received continuation values and cancellations without recording credentials.
Generate ephemeral credential material and certificates only in ignored temporary
test directories. No real accounts or external service calls occur in trials.

An independent fault proxy may alter/drop/delay bytes without replacing upstream
SDK parsing/dispatch. Any requirement not yet exercised remains not_run or blocked,
not implicitly passed by another test.
