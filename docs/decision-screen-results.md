# Decision: prioritize the shared runtime

Executed October 27, 2026. **Recommendation: library-first; pause further Meda
language expansion.** The minimum direct-call Meda implementation works, but
this screen does not show enough additional protection or maintenance benefit
to justify developing the full language now. Preserve it as a research example.

Both applications used the same host, adapters, official SDK peers, grants,
limits, fault scenarios, and independent expectations. The Meda arm executed
actual source through the existing parser/checker/evaluator with a narrow binding
extension. Its application logic was not substituted with Python.

## Results

| Observation | Meda | TypeScript | Interpretation |
| --- | --- | --- | --- |
| Required real-protocol workflows | 5/5 | 5/5 | Success, required input, unknown delivery, malformed response, and invalid domain result all satisfy independent expectations. |
| Prerequisite lifecycle probes | 6/6 | 6/6 | Missing input, cancellation refusal, two abort barriers, late abort after publication, and root deadline behave as specified. |
| Matched static defects rejected | 4/4 | 4/4 | Wrong host argument type, missing record field, misspelled task state, and missing state branch. |
| Undeclared external effect | Rejected | Call accepted | A real extra check in this Meda profile. The TypeScript control has no corresponding effect declaration. |
| Misspelled outcome / error code | Accepted / accepted | Rejected / rejected | Meda uses Text for these payloads; TypeScript uses finite unions. This is a current implementation weakness, not an inherent language limit. |
| Maintenance final acceptance | 18/18 | 18/18 | Both implement report-order normalization and preserve rejection behavior. |
| Visible repair submissions | 1 | 1 | One uncontrolled demonstration per arm; no productivity or cost advantage established. |

All 11 paired scenarios had matching outcomes, application calls, and normalized
protocol dispatches after each arm independently passed. The 39 execution-source
hashes were unchanged during the baseline run. Both original validators rejected
the reversed-report scenario; both frozen repaired validators then passed that
end-to-end scenario. No final acceptance feedback was used for further repair.

The cancellation defect is fixed: a validated explicit refusal records its
provenance and suppresses subsequent automatic cleanup. It does not manufacture
a terminal remote state. A later validated nonterminal observation restores
cleanup eligibility; an uncertain cancellation response does not suppress it.
The original failed pilot receipts remain untouched. The new P2 receipts in the
baseline file are separate repair evidence.

The shutdown contract distinguishes abort from normal finish. Abort blocks new
application dispatch and overrides uncommitted success. Normal finish retires
the worker before closing admission and committing its proposal through the
host. Reserved cleanup and remote uncertainty are separate. In these runs,
maximum measured request-to-worker-retirement was below 8 ms and maximum host
finish/cleanup elapsed time was below 52 ms, within the prospective 3-second and
1-second bounds. These are observations on this machine, not performance claims
or hard real-time guarantees. No zero-source-instructions-after-close guarantee
is asserted.

## What belongs to which layer

Credentials, operation grants, request/body budgets, protocol validation,
reference ownership, cleanup policy, and final publication belong to the shared
host or bindings. Both languages benefit from them.

Meda's declared-effect checking rejects an undeclared host call, including through
helpers and pure contracts. That mechanism is useful. This experiment does not
establish that a new language is necessary to obtain it: a conventional client
with narrower capability interfaces or additional checking remains a possible
control for future work. The existing TypeScript unions already reject two
mistakes the small Meda profile accepts.

Application source controls polling, input continuation, avoiding resubmission
after an uncertain outcome, and report-domain relationships. Acceptance tests
check those behaviors in both arms. Structural validity does not establish
factual truth.

## Cost and limits

The additional Meda path required 298 lines of language/binding implementation,
118 lines of worker bridging, 124 lines of application source, and a 17-line
addition/4-line replacement in the shared pure core. These are physical source
line counts, including comments and blank lines, not effort or quality scores.
The experiment also adds separate runners, an oracle, static probes, maintenance
fixtures, and tests. That evaluation machinery is additional work, not product
functionality. The shared host fix and supervisor instrumentation benefit both
clients and are counted separately.

Integration revealed a real boundary issue: A2A's Protobuf Struct yielded report
revision as JSON `1.0`. The Meda binding initially rejected it; the final binding
normalizes finite integral values within its declared bound to Int and rejects
fractions, booleans, non-finite numbers, and out-of-range values. A regression
covers this. The final immutable screen ran after the fix.

The task requirements, hidden fixture file and baseline hashes were frozen before
two fresh repair agents ran. Each saw its own source and the same requirements
and visible examples. Editing was limited to the validator body and protected
source hashes stayed unchanged. Isolation was by instruction on a shared
filesystem, not enforced filesystem separation. Exact served model revision,
reasoning setting and token usage were unavailable. Elapsed check time is not
model productivity. This is one uncontrolled maintenance demonstration, not the
full Gate B study or evidence of statistical equivalence.

The profile is deliberately limited: fixed bindings, monomorphic effects, no
general modules, user-defined opacity, effect polymorphism, concurrency, or
integration of effectful code into the guarded editing API. Local test bearer
credentials are not production OAuth. Network evidence covers numeric loopback
endpoints, and sampled RSS supervision is not a hostile-code sandbox. Official
SDK peers have deterministic behavior; there were no LLM provider calls.

## Recommended next investment

Keep the conventional TypeScript client first-class and make the host's small
API easier to use and test independently of the experimental language. Retain
[the broader acceptance backlog](https://github.com/meda-lang/meda/issues/11)
before making production-readiness claims. Do not expand the language merely to
reproduce protections already provided by that host.

The strongest case for continuing Meda is the combination of declared effects,
contracts, and protected edits for larger changes with limited context. This
screen did not test that combination: the effectful profile lacks the guarded
edit integration and the maintenance task is small. Reopen language investment
only with a specific larger task and an equally equipped conventional control
that could falsify the claimed benefit. The current evidence supports a bounded
pause, not a claim that the language can never be useful.

## Reproduce and inspect

See the [runnable examples and commands](../experiments/decision_screen/README.md),
[predeclared contract](decision-screen-contract.md),
[baseline receipts](../experiments/decision_screen/results/baseline.json),
[static checks](../experiments/decision_screen/results/static-checks.json), and
[maintenance receipts](../experiments/decision_screen/results/maintenance.json).
All 141 local test methods pass: 91 host/protocol/supervisor tests, 23 original
pure-language/editing tests, 15 earlier comparison tests, and 12 direct-language
tests. Those method counts are separate from the 22 workflow executions and 18
maintenance cases per arm. Full D0 acceptance remains open.

The 18-case maintenance counts cover the composed input/binding/validator path.
Malformed Meda record shapes can be rejected before the edited source validator,
while the TypeScript validator receives `unknown` and checks those shapes itself.
Those rows must not be credited as language-specific application protections.
