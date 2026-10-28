# Bounded Meda versus TypeScript decision screen

Profile: `meda-decision-screen/1`. Defined October 27, 2026, before the paired
workflow and maintenance attempts. This is a prospective contract for
[issue #9](https://github.com/meda-lang/meda/issues/9) and the smaller experiment in
[issue #10](https://github.com/meda-lang/meda/issues/10).

The question is whether checked, direct Meda host calls and application source
provide enough additional benefit over strict TypeScript using the same host and
adapters to justify further language investment. A usable protocol host is a
shared result. It is not by itself evidence for a new language.

This profile does not replace `meda-interop-d0/1`, complete its acceptance gate,
or satisfy the controlled multi-model study in [the broader evaluation
plan](interop-evaluation.md). Preserve previous inventories, failed receipts,
unverified guarantees, and source freezes. Record new results separately.

## Admission and implementation boundary

Both clients must execute the same evidence-to-report workflow through the
existing common host, protocol adapters, local TLS fault proxies, and official
SDK peers. Each arm gets fresh peer state, equivalent grants, credentials,
inputs, limits, and scenario configuration. Random task IDs and ports may differ.
The peers are deterministic fixtures; no LLM provider calls occur in this screen.

The Meda arm must execute real `.meda` source through an extension of the existing
parser, checker, and evaluator. Source performs direct calls to five typed host
operations: read evidence, submit a task, observe it, provide requested input,
and cancel it. A Python bridge may encode/decode values and transport these
calls; it must not decide application control flow or perform domain validation
on Meda's behalf. Preserve the original pure profile's behavior. Declare the
supported effect and opaque-reference semantics before executing the screen;
record unsupported features rather than implying the full design is implemented.

Keep the actual strict TypeScript compiler and its existing private-reference
binding. Both applications perform their own report validation. Distinguish
static checks, binding membership, host enforcement, application logic, and peer
behavior when attributing any rejected defect.

## Shutdown contract

There are two different entry paths into closing a root:

- **Abort or deadline:** close normal host admission and make the fatal outcome
  win over every success that has not yet been committed. A result computed
  earlier but not committed cannot win a later race against an earlier abort.
- **Normal finish:** receive one application result proposal and stop processing
  new worker calls. Retire the worker, then have `Host.finish` close normal host
  admission, perform bounded reserved cleanup, and commit the result. Late or
  duplicate worker output invalidates the proposal. An abort before commit can
  still replace the proposal with the fatal outcome. An abort after commit
  cannot change a published result.

The existing `root_close` trace event during normal finish therefore does not
mean that all successful publication is forbidden. It records closed admission
while the already-received proposal awaits publication. `root_abort` identifies
fatal closure. This distinction applies identically to both languages.

| Promise | Required observation | Limit of the observation |
| --- | --- | --- |
| No new application authority after closure | Once the shared closure lock records abort or normal close, subsequent ordinary admission/dispatch attempts are rejected. Ordered traces contain no non-cleanup dispatch after that event; a direct post-close probe is rejected. | A request dispatched before closure may already have a remote effect. |
| Abort wins before publication | A barrier closes the root before releasing a pending observation response. The final outcome is fatal, there is exactly one publication, and no successful publication occurs. A separate publish-first control retains its committed success after a late abort. | This does not reverse earlier remote effects. |
| Owned local work retires within a measured bound | Record monotonic timestamps at the controller's first abort/retirement request and at confirmed worker exit. In each fatal-path screen case the worker must be reaped within 3 seconds of that request; record supervisor join and active transport cancellation separately. Normal finish retires the worker before host publication. | This is a supervised local process experiment, not a hard real-time OS guarantee or hostile-code sandbox. |
| Cleanup has limited authority | Cleanup can only use the host's reserved request allowance and existing cancellation grant. Record its dispatches separately from application work and its measured elapsed time against the configured 1-second cleanup budget. | Cleanup may fail or time out; an attempt is not proof of remote cancellation. |
| Remote uncertainty remains visible | Keep cancellation response, cancellation refusal, lost response, and local worker exit distinct. A validated refusal suppresses automatic cleanup until a new validated nonterminal observation changes eligibility. | `TaskNotCancelable` does not prove completion; local retirement does not imply rollback. |

The 3-second retirement ceiling is a prospective screen bound, allowing the
existing bounded wait and kill/reap stages. It does not rewrite the older D0
criteria. Its starting point is the controller's retirement request, not an
unobserved claim about exactly when the OS scheduled a deadline response.
Timestamp the worker's retirement directly; whole-workflow elapsed time is not
a substitute. Missing timing evidence is unverified, not a pass.

**No claim of zero source instructions after close is made.** Pure computation
may continue during asynchronous termination. The promise is that it cannot gain
new host authority or publish a successful result after fatal closure, and the
owned worker is subsequently retired within the observed bound. A stricter
source-step guarantee would require a separately specified execution model.

## Five required workflow cases

Freeze the case inventory and expected observations before executing either arm.
The evaluator must not import either client's validator to decide acceptance.
Two matching wrong answers fail. Counts below concern application business calls;
discovery and reserved cleanup are recorded separately.

The fixed evidence is document `evidence-42`, revision `1`, with facts `f1=blue`
and `f2=square`. Unless overridden, selection order is `["f1", "f2"]`. Successful
publication must contain exactly that document, revision, and selected facts in
that order, without extra fields or invented values.

| Case | Scenario | Independent expected result and witnesses |
| --- | --- | --- |
| S1: success | MCP JSON evidence; A2A returns Working then Completed. | `Success` with the exact report; one read, one submit, one observe; one peer task created; no continuation or cancellation. |
| S2: required input | Submit without selection; peer requests input; provide `["f1", "f2"]`. | `Success` with the exact report; one read, one submit, one continuation, zero observes. Peer creation and continuation witnesses identify the same task. |
| S3: uncertain delivery | Drop the submit response after the peer commits the task. | `TransportFailure` with `remoteOutcome: Unknown`; one read, one submit, one peer task created, zero resubmits, observes, continuations, or cancellations. No report or successful publication. Proxy proves the response was dropped after forwarding the committed call. |
| S4: malformed response | Replace the MCP evidence response's JSON-RPC ID with a mismatched ID. | `ProtocolRejected`; one read, zero submits, zero peer tasks, zero later business calls, no report or successful publication. Proxy mutation and response witnesses must establish that the malformed reply was actually delivered. |
| S5: invalid domain result | Preserve the protocol envelope but replace a selected fact's value in the completed report. | `DomainRejected`; one read, one submit, one observe, one peer task, no successful report. The wrong value reaches the application; its source validator rejects it. |

For every case require one final publication, retired application and peer
processes, joined supervision, complete expected witnesses, and no credential or
internal-reference matches in the observed application output channels. Keep the
scope of that channel scan explicit; it is not a proof about every possible
program observer. Record normalized outcomes and call sequences only after each
arm independently satisfies the case criteria. Record missing witnesses,
execution errors, timeouts, and mismatches as such; never widen expectations to
turn them into passes.

Add bounded prerequisite probes for post-close admission, both publication race
orders, and explicit cancellation refusal. These support the declared shutdown
and cleanup claims; they are separate from the five application scenarios and
from the larger historical acceptance inventory.

## Frozen maintenance task: unordered report facts

A report-producing service starts returning its `selected` facts in any order.
Change only application report validation so that both clients accept a valid
permutation and return a canonical report ordered by the caller's `includeIds`.
Keep the evidence and wire schemas, host, adapters, SDK peers, input handling,
compiler/checker, and acceptance expectations unchanged.

The change has these requirements:

1. The report must have exactly the current fields, matching document ID and
   revision. Every selected fact must have exactly `id` and `value` with the
   existing type and size bounds.
2. Selected IDs must be an exact permutation of the requested IDs. Reject
   duplicates, missing or extra facts, unknown requested IDs, and any fact whose
   value differs from its matching supplied evidence fact. Existing validation
   of requested IDs remains in force.
3. On success, return the same public report shape, with facts reordered to
   `includeIds`. Do not mutate the input report, evidence, or requested IDs.
4. Empty requested selection accepts an empty selected list. A valid subset
   accepts exactly that subset. A rejected report keeps the existing
   `DomainRejected` application outcome and cannot publish success.
5. The original ordered-success cases and error handling remain unchanged.

Allowed edits are the TypeScript report-validation function in `domain.ts` and
the corresponding pure `validateReport` operation in the Meda source. A necessary
local helper must be declared as part of the editable scope before either
attempt. No changes to opaque references or host effects are needed.

Both arms receive the same task wording, data schema, editing scope, explicit
requirements, visible example fixtures, and validation-command access. They
receive their own language's baseline source and profile documentation. Freeze
both baseline source hashes and the task packet before starting either attempt.
The original ordered validator must fail the visible reordered-success example,
which proves the task requires a behavioral change.

Visible examples include the unchanged ordered report and a valid reversed
report that must normalize back to the request order. Final acceptance also
covers different request orders, subsets, empty selections, duplicate/missing/
extra facts, wrong values, wrong document/revision, and unknown requested IDs.
Include one end-to-end run using the existing reordered-report fault fixture.
The exact final fixtures remain outside the repair packet; run them only after
both candidates are frozen. Preserve the original report ordering rejection as
a baseline result, then store the changed requirement's receipts separately.

## Attempt protocol and interpretation

Use one fresh repair worker per language. Keep the parent model configuration
and instruction budgets equivalent. Each arm may submit at most three
candidates using only its visible checks. Preserve every submitted source,
visible-check receipt, timestamps, and parent interventions. Freeze each final
candidate before revealing final acceptance results; those results cannot guide
additional repairs in the scored attempt. A parent repair, if needed, is a
separate assisted result rather than a replacement for the original failure.

Record actual available model identity, version/selector, reasoning setting,
usage, elapsed time, and isolation mechanisms. Unknown metadata stays unknown;
do not infer tokens from characters, price unmetered usage at zero, or fabricate
wall-time enforcement. A shared-filesystem subagent with instructions not to
read the other arm or final fixtures is instruction-isolated only. If filesystem
isolation or exact model/usage metadata is unavailable, label the exercise an
**uncontrolled maintenance demonstration**. It cannot support productivity,
cost, statistical superiority, or the broader Gate B claims.

Hash and retain the contract, case inventory/oracle, baseline sources, dependency
locks, host/adapters, compiler options, task packet, candidates, and receipts.
The contract freeze must precede candidate execution; record any later amendment
with its reason and whether it invalidates a comparison. Do not overwrite older
results. Count implementation files/lines and record available implementation
and review effort separately from maintenance outcomes. This single task tests
one small behavioral change, not general software maintenance.

## Product decision

Publish a short decision after the screen, including failed and unverified rows:

- **Continue Meda:** identify a concrete source-level protection or maintenance
  benefit and its implementation burden, then name the next test that could
  disprove its usefulness. A successful direct-call demo alone is insufficient.
- **Library-first:** the shared host is useful, while the language has not shown
  enough additional value to justify expansion. Keep the conventional client.
- **Stop or narrow further:** the minimum profile itself requires substantial
  machinery, unreliable fixtures, or claims the evidence cannot establish.

An effect checker catching an undeclared external call is a language mechanism;
request quotas, credentials, response validation, cancellation cleanup, and
network limits remain shared host/adaptor mechanisms unless a separately tested
source guarantee adds something. Report the maintenance result as one paired
example, and keep larger protocol-conformance and production-readiness gaps open.
