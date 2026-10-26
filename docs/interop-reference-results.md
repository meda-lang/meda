# Real protocol reference implementation results

October 25, 2026. Profile `meda-interop-d0/1`.

The conventional TypeScript client now executes an MCP evidence read followed
by an A2A delegated task through the common host and official SDK peers. This
establishes an executable reference candidate. It does not close D0 acceptance,
execute the effectful Meda arm, or measure maintenance productivity.

The recommendation remains **library-first**. The protections demonstrated in
this packet come from the common host/adapters, conventional typed bindings,
application validation, and process supervision. Meda must demonstrate an
incremental benefit against this implementation before further language scope
is justified.

## Observed pilot outcome

The [complete first-attempt receipt](../experiments/interop_d0/results/reference-pilot.json)
selects all 111 inventory cases and retains every attempt:

| Measure | Count |
| --- | ---: |
| Cases with execution receipts | 93 |
| Execution exceptions without a complete case receipt | 3 |
| Cases not implemented or not run | 15 |
| Full acceptance cases passed | 0 |
| Executed cases with a failed obligation | 2 |
| Executed cases with incomplete evidence and no failed obligation | 91 |

The 93 executed cases comprise 51 workflows, 12 direct host probes, nine peer
probes and 21 adapter probes. Expected outcome-category checks pass in 86 rows,
remain ambiguous in six, and fail in one. These individual checks do not replace
the full acceptance obligations. All six incorrect domain reports are rejected.
The compiler used 193,384,448 bytes observed peak RSS and 1.85 seconds in this run,
within its unchanged supervised limits.

The two failed rows are substantive evidence to retain:

- **Cancellation refusal:** an explicit `TaskNotCancelable` response is followed
  by one automatic cleanup cancellation, exceeding the frozen allowance of zero.
  The proposed repair should record the prior refusal and suppress that repeat;
  it must not manufacture a completed task state. A2A refusal does not establish
  termination: cancellation can also be unsupported at the current stage
  ([A2A 1.0 cancellation semantics](https://a2a-protocol.org/v1.0.0/specification/#315-cancel-task)).
- **Wrong RPC ID:** the proxy records the mutation, but the host receives no
  response body before its request timeout. The row therefore reports unknown
  delivery instead of the required protocol rejection. Its receipt does not
  establish whether the intended malformed envelope reached the decoder.

Explicit cancellation, duplicate evidence fact ID, and foreign-peer reference
probes each encountered an execution exception. Their original rows remain
errors, with no acceptance credit. The 15 unrun rows comprise two missing workflow
fixtures, nine Meda source checks, and four host/source mutant experiments.

A separate [five-case diagnostic rerun](../experiments/interop_d0/results/diagnostic-reruns.json)
completed with an unchanged source snapshot. Explicit cancellation returned
`RemoteCanceled`; wrong RPC ID and duplicate fact ID returned `ProtocolRejected`;
the foreign-peer reference returned `InvalidReference`. The cancellation-refusal
case reproduced its extra cleanup request. The rerun therefore has one failed
and four still-unverified cases. It diagnoses reproducibility without replacing
the original exceptions or failed wrong-ID row, and does not establish that the
intermittent execution problems are resolved.

The whole-tree immutability check is **false**: an RSS supervisor unit test was
added during the run. Comparing the start hashes with the final files identifies
only `tests/test_runner.py` as changed; client, host, adapters, peers, oracle,
inventory and runner hashes are unchanged. The receipt retains this failure of
the broader freeze condition. An earlier interrupted development prefix is also
retained separately. This packet is a reference pilot, not a frozen acceptance
sign-off or a maintenance measurement.

Final isolated verification passes **85 new test methods**, plus the unchanged
Gate A/B suite's **23** and earlier comparison suite's **15**. The
[verification record and logs](../experiments/interop_d0/results/verification.json)
preserve the commands and counts. Unit and regression success does not override
the independent acceptance result above.

## What is implemented

The [reproduction guide](../experiments/interop_d0/README.md) installs exact,
hash-locked dependencies: official MCP Python SDK 2.3.0 and its MCP 2026-07-28
schema, official A2A Python SDK 1.2.3 for the 1.0 JSON-RPC wire contract, and
TypeScript 5.9.3. The dependency provenance records release commits and artifact
hashes. A candidate manifest pins the independent inventory, limits, tool schema,
Agent Card template, and specification-source fingerprints. Each run records its
actual loopback endpoints and binding hashes.

Both protocol peers run in separate processes with verified local TLS and
preprovisioned, server-validated credentials. A fault proxy forwards actual SDK
requests before mutating, dropping, or delaying responses. SDK peer observations
distinguish task creation, continuation, ownership denial, and cancellation from
what the client believes happened.

The host enforces grants, one submission and continuation, request and body-byte
allowances, root deadlines, binding identity, task-reference membership, and
bounded cleanup. Unknown delivery is preserved after a dispatched request loses
its acknowledgement. Application code validates the entire report before
proposing success. The TypeScript binding keeps task authority in private
membership; serializing the application wrapper yields inert data.

## Defects found before the pilot

Review and executable adversarial probes found substantive implementation bugs,
which were repaired with retained regression tests:

| Failure | Repair and observed evidence |
| --- | --- |
| Timeout after dispatch could claim the remote operation completed | Delivery remains unknown until the relevant response is validated; a peer-created task with a lost acknowledgement remains unknown. |
| Malformed task state could lose delivery uncertainty | Typed envelope rejection preserves the dispatched operation's unknown status. |
| Concurrent finish calls could publish twice | One finalizer owns cleanup and publication; abort can override before publication. |
| Conflicting A2A part fields or malformed MCP content could reach domain validation | Supported protocol envelopes are checked before extracting domain data. |
| Slow-drip HTTP headers could evade the absolute deadline | An owned-socket watchdog interrupts reads; an independent 150 ms probe returned timeout at 152.5 ms, previously 593 ms. |
| A short response could be accepted despite a larger Content-Length | Premature body completion is rejected as transport failure. |
| Aborting silent HTTP or TLS waits could outlive cleanup | Cancellation reaches the owned socket during handshake and response I/O; regression tests require the call to join before publication. |
| References did not explicitly retain their peer binding | References now retain endpoint and pinned-card identity and reject a changed peer before discovery. |
| Process IDs could select the wrong RSS entry in this environment | Supervision resolves the actual child in the exposed PID namespace; a real allocation probe checks measurement and retirement. |

Compiler setup initially exceeded its real memory allowance. ES2022 library
selection and conventional `skipLibCheck:true` keep strict application checking
within the existing 10-second/256-MiB supervised limits. This skips checking the
internals of pinned dependency declarations; it does not remove type checking
of application source or imported types. Failed development attempts are not
maintenance measurements.

## Interpretation and remaining boundaries

The independent oracle preserves missing evidence as `unverified`; an executed
row is not automatically a passed acceptance case. Exact report comparison,
business dispatch counts, peer task creation, response-loss behavior, schema
rejection, and observable retirement are narrower claims than all of the
profile's invariants together.

Local cleanup and remote cancellation are separate facts. An independent live
SDK stream probe published after the local call/socket retired, then observed
remote cancellation within a separate 500 ms window before fixture shutdown.
No rollback or remote stop guarantee follows merely from local cancellation.

Memory supervision samples RSS rather than enforcing an OS memory sandbox.
Deadline/cancellation evidence covers numeric loopback TCP/TLS/HTTP waits;
external DNS blocking is outside that evidence. The byte counters bound HTTP
entity bodies, not TLS or HTTP framing. The decoder validates this supported
profile, not arbitrary protocol messages or extensions. Authentication uses
local test bearer credentials rather than a production OAuth deployment.

The complete no-source-continuation-after-close invariant remains unverified.
A controller can prevent new host admission and publication after closure,
while asynchronous process retirement cannot by itself establish that no
previously runnable source instruction executes. Source-internal authority
visibility, full discovery accounting, and cleanup timing also require stronger
independent evidence than the current per-case receipts provide.

## Scope decision before the next packet

D0-02 and D0-03 stay open. The implementation received an initial pass and two
host repair cycles; further work should begin with an explicit scope decision,
not silently turn missing observations into passes. D0-04 through D0-07 remain
dependent work, including the actual effectful Meda comparison and controlled
maintenance study.

The recommended prospective amendment separates three testable promises:

1. Closing a root immediately revokes new host-effect admission and successful
   publication for both language arms.
2. The supervisor retires owned local work within a measured bound; residual
   pure computation during asynchronous termination is not new authority.
3. Remote cancellation is reported independently and may remain unknown.

This is a proposed clarification for the next revision, not a retrospective
change to this run's acceptance criteria. If the stronger zero-source-step
promise is essential, it needs an execution model and evidence that establish
it before either arm enters the comparison.

Keep protocol versions, capabilities, discovery and lifecycle translation in
adapters rather than language syntax. A future LLM protocol should enter through
an explicit binding manifest and equivalent authority, drift, malformed-response,
delivery-uncertainty and cancellation tests. Passing these MCP/A2A slices is not
evidence that an untested protocol is automatically compatible.

The immediate work is to resolve the remaining acceptance mismatches and scope,
then freeze a passing reference baseline. Only then should the minimum effectful
Meda client be added over these same adapters. There is no language-value or
maintenance-speed claim from this packet.
