# Real-protocol acceptance follow-up

This follow-up narrows one part of [issue #11](https://github.com/meda-lang/meda/issues/11):
the three first-pilot execution exceptions and the two substantive mismatch
cases. It does not close the broader `meda-interop-d0/1` acceptance gate.

## Safe failure attribution

Unexpected per-case exceptions now record a closed `errorStage` value alongside
the exception type. The possible execution labels are locally authored
(`workflow_execution`, `host_probe_execution`, `adapter_probe_execution`, and
`peer_probe_execution`); an oracle failure is recorded as `oracle_assessment`.
Unknown surfaces fall back to `case_dispatch`.

Exception messages are still discarded because a dependency exception can
contain credentials, endpoints, protocol content, or private task references.
Tests inject secret-bearing exception text and verify that neither the text nor
a peer-supplied surface can become receipt metadata.

## Focused replay

Five isolated rounds replayed these cases against the canonical runtime merged
in PR #16:

| Case | First pilot | Follow-up result | Rounds |
| --- | --- | --- | ---: |
| `W04-explicit-cancel` | Execution exception | `RemoteCanceled` | 5/5 executed |
| `W04-explicit-cancel-terminal-refusal` | Extra cleanup cancellation | `TaskNotCancelable`; no failed frozen checks | 5/5 executed |
| `W05-wrong-rpc-id` | Timeout/unknown delivery | `ProtocolRejected` | 5/5 executed |
| `W08-evidence-duplicate_fact_id` | Execution exception | `ProtocolRejected` | 5/5 executed |
| `W10-host-foreign_peer` | Execution exception | `InvalidReference` | 5/5 executed |

All 25 rows executed, had the expected outcome category and phase, and had no
failed frozen check. Every round reported an unchanged source snapshot. The
exact aggregate and command are retained in
[`results/acceptance-followup/replay-summary.json`](../results/acceptance-followup/replay-summary.json).

This is evidence that the known execution failures and mismatches are not
reproducing in this focused candidate. It is not a claim that their historical
first-attempt receipts passed, nor a full acceptance result. Every row remains
`unverified` because the frozen oracle still requires stronger independent
witnesses for properties such as source continuation, full metering, and secret
visibility.

## Remaining work

Issue #11 remains open. The next useful packet should add the missing independent
witnesses or explicitly narrow the promises, implement or defer the remaining
fixtures and mutants, and only then run a complete immutable 111-case candidate.
Historical result files remain unchanged.
