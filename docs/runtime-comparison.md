# Meda shared runtime comparison results

Executed October 25, 2026. **A conventional strict TypeScript client completed
the same implemented workflow as Meda, with identical decisions, observations,
and dispatch traces. This supports building the shared host/adapters as a reusable
library. It does not yet establish a benefit from a new language.**

The Meda arm uses the real `meda-pure-b0/1` parser, checker and evaluator. The
TypeScript arm uses the actual 5.9.3 compiler with strict checking, finite action
types and readonly records. Both run through the same host implementation; no
Meda programs are translated into hand-written Python stand-ins.

## Results

| Check | Meda | TypeScript | Interpretation |
| --- | --- | --- | --- |
| Workflow cases | 12/12 | 12/12 | Same expected outcomes, decisions, observations and host traces in all 12 pairs |
| Matched static defects rejected | 4/4 | 4/4 | Wrong field type, missing field, misspelled action, missing enum case |
| Valid static control | 1/1 | 1/1 | Rejection is not caused by a broken checker setup |
| Fresh-agent repair demonstrations | 3/3 | 3/3 | Small, easy branch repairs; no productivity conclusion |

The workflow covers successful evidence→task execution, pending input, supplied
input, lost submission responses, malformed/oversized/wrong-type/wrong-ID
responses, zero/exhausted allowance, completion at the quota boundary and denied
read access. The sixteen original acceptance cases for each repair passed; three
post-review supplemental cases also passed without further candidate edits.

Nine direct host/peer checks passed while bypassing both source checkers. Two
temporary host mutations—removing operation authorization and call limits—were
detected. Fifteen new test methods and all twenty-three existing gate test methods
passed. Counts describe this fixed corpus, not independent statistical samples.

## What comes from which layer

| Behavior | Demonstrated source |
| --- | --- |
| Request shape, configured operation grant, endpoint restriction, per-root call ceiling, bounded/validated peer response | Shared host library |
| Remote task ownership across synthetic principals and local roots | Shared host plus fixture peer checks |
| Correct polling, pending-input handling, terminal publication precedence, stopping after uncertain submission | Application policy written in either language and checked by acceptance tests |
| Record/variant type errors and the separate enum completeness probe | Each language's actual checker |
| Production authorization, effect checking, structured cleanup, durable recovery and complete MCP/A2A support | Not measured |

The distinction matters. A deliberately wrong but well-typed client resubmitted
after an unknown outcome. In **both languages**, the peer created two tasks.
The host disabled its own automatic retries, but did not prevent an application
from explicitly requesting another submission. The independent oracle detected
the policy defect. Static typing alone did not catch it.

Similarly, the current host does not enforce a final application-domain contract
on a client's stop payload. Schema validation is not evidence of factual or
business correctness. No claim that every useful protection comes from the
library follows from this experiment.

## Maintenance evidence

Six fresh-context agents repaired equivalent source defects: uncertain-delivery
resubmission, missing-input task replacement and a zero-budget off-by-one error.
Each saved candidate passed its one visible-check invocation and the independent
acceptance evaluation. None received hidden acceptance feedback before finishing.

These are **uncontrolled repair demonstrations**. They used the available agent
interface, one candidate per task/language, and no
enforced filesystem isolation or equal hard inference deadline. Exact model
revision, sampling and token cost were unavailable. The tasks are single-function
branch repairs, not held-out multi-file changes. The tie is inconclusive for
productivity.

The original pending-input task was ambiguous about missing input at zero budget.
The post-review interpretation preserved existing budget precedence. That
supplemental check was kept separate, and no task packet or candidate was rewritten
after acceptance results.

## Recommendation

**Prioritize the reusable host/adapters and keep TypeScript as a first-class
reference client. Keep Meda's language value as an unproven hypothesis.** The
current evidence does not justify growing the language merely to obtain the
tested runtime protections, because the conventional client already uses them.

Do not abandon Meda on this small screen alone: its proposed effectful runtime,
opaque boundaries and guarded multi-file maintenance are not implemented in this
comparison. The next decisive test must use the same adapters through an actual
effectful Meda boundary and an equally equipped conventional client. Use held-out
multi-file tasks, several named models, repeated fresh trials and all-attempt
review/cost measurements. Keep the conventional client's runtime validation,
strong types and editing safeguards intact.

The preregistered practical margins for that later study are at least 10 points
better task success without material cost regression, or at least 20% lower
whole-change cost at comparable success within 5 points. Those margins need a
properly powered independent-task study; these demonstrations cannot satisfy it.
If that stronger comparison adds no material value over the compiler/tooling
maintenance cost, redirect toward the library product.

## Scope and reproduction

This is an isolated decision-boundary experiment using actual local subprocesses
and HTTP connections. The wire fixtures are custom protocol-shaped messages;
they do not implement official MCP/A2A and their identity headers are synthetic,
not production authentication. Dynamic descriptor drift, cumulative deadlines,
global remote quotas, secure sandboxing, SSE, durable recovery and full replay
remain unmeasured. The proposed effectful Meda runtime did not participate.

See [the experiment README](../experiments/interop_compare/README.md),
[the preregistered protocol](../experiments/interop_compare/EXPERIMENT.md),
[machine-readable results](../experiments/interop_compare/results/baseline.json)
and [repair results](../experiments/interop_compare/results/maintenance.json).
Source digests and the complete TypeScript package fingerprint are recorded.
The first failed development oracle and subsequent strengthening are retained
and explained in the README rather than silently excluded.
