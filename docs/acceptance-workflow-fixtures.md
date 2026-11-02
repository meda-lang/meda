# Input deadline and local cleanup fixtures

This bounded follow-up to [#11](https://github.com/meda-lang/meda/issues/11)
implements the two workflow rows that the first D0 pilot could not execute.
It does not expand the public runtime API or resume language development.

| Frozen case | Fixture behavior | Expected result |
| --- | --- | --- |
| `W02-wait-deadline` | Read evidence, submit a task, receive `InputRequired`, then remain alive without an answer until the root deadline | Fatal `Timeout` |
| `W04-cleanup-cannot-join` | Submit a task, start a held local activity, abort before returning the task to the application, and exhaust the host's join allowance | Fatal `CleanupFailure` |

The waiting option lives only in the research TypeScript client. A pending
promise and keepalive timer model an input provider that never answers. The
ordinary supervisor enforces the deadline and retires the process. Normal
missing-input behavior still returns `NeedsInput`; supplied input takes
precedence and completes normally. There is no new interactive input service.

The join fault is a real test thread occupying the host's existing activity
slot. It deliberately ignores cancellation until the canonical `Host.finish()`
has exhausted its cleanup allowance and published its result. The fixture then
releases and joins the thread, including when execution raises. Its receipt
records whether the activity was still alive at publication and joined after
release. The Node process retires normally: this is a cooperative local activity
fault, not evidence that a process resisted `SIGKILL` or escaped containment.

Neither fixture manufactures its terminal result. The canonical runtime,
transport, frozen inventory, independent oracle, and historical receipts are
unchanged. The fault thread has no network or application work, so teardown
does not generate a late request or publication.

## Verification

Four focused test methods exercise the two faults, ordinary missing-input
behavior, supplied-input precedence, the ordinary abort control, and teardown
after a publication exception. They check actual timing, worker retirement,
single publication, no normal dispatch after closure, and released activity.

The [verification record](../results/acceptance-workflow-fixtures/README.md)
contains the regression results and repeated runs of the exact frozen scenarios
with their original resource limits. CI also executes those two inventory rows
and rejects execution errors, unexpected outcomes, changed sources, or failed
frozen checks.

The broader acceptance status remains **unverified**. In particular, the wait
barrier observes the host receiving `InputRequired`; it is not an independent
acknowledgement that application code reached its wait. The frozen oracle still
requires stronger evidence for source continuation, discovery accounting,
secret visibility and cleanup timing. The extra fixture observations do not
silently satisfy those obligations.

## Remaining originally unrun rows

These are the other 13 rows from the original pilot's 15-row unrun backlog.
This follow-up does not claim a new complete 111-case run.

| Group | Case IDs | Disposition |
| --- | --- | --- |
| Reference source checks | `W10-meda-construct_task_ref`, `W10-meda-read_task_ref_field`, `W10-meda-update_task_ref`, `W10-meda-serialize_task_ref`, `W10-meda-decode_task_ref` | Deferred with language expansion; do not count the narrower decision-screen probes as these cases |
| Effect source checks | `W12-meda-transitive_undeclared_effect`, `W12-meda-pure_contract_host_call`, `W12-meda-declared_bound_laundering`, `W12-meda-valid-effect-control` | Deferred with language expansion; retain the original requirements |
| Host mutants | `W12-mutant-remove-grant`, `W12-mutant-remove-quota` | Executable in the later [mutation follow-up](acceptance-mutations.md), with independent observations and paired controls |
| Application mutants | `W12-client-repeat-submit`, `W12-wrong-domain-validator` | TypeScript arms executable in the [mutation follow-up](acceptance-mutations.md); Meda arms remain unexecuted |

The missing independent witnesses remain separate work. Issue #11 stays open;
these executions neither establish general MCP/A2A conformance nor production
readiness.
