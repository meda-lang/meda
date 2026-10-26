# Meda interoperability evaluation plan

Status: proposed evaluation plan, October 25, 2026. No trials described here have
run. The [design amendment](interop-design-amendment.md) and
[workflow specification](interop-workflow.md) define the proposed
`meda-interop-d0/1` slice. The existing pure comparison remains separate evidence.

The question is whether Meda adds enough protection or maintenance value to
justify its compiler and tooling cost when a conventional typed client receives
the same host, adapters, permissions, validation and editing safeguards. Protocol
interoperability is an admission requirement, not evidence of language value.

## Hypotheses and attribution

| Hypothesis | Matched challenge | Evidence to record |
| --- | --- | --- |
| Declared effects improve change safety | Introduce a transitive external call beneath an unchanged effect interface | Which checker rejects the change, at what phase, and the repair/context cost |
| Opaque types preserve construction boundaries | Change task-handle or validated-result construction across modules | Static rejection, runtime membership checks, invariant failures and repair cost |
| Meda and its tools improve maintenance over equally equipped TypeScript | Change behavior across modules under a bounded edit grant | Independently accepted changes, rejected unauthorized edits, review effort and total cost |

The first two hypotheses concern source mechanisms. The third concerns the
language and its editing tools together. A bundled result must not be presented
as a syntax-only result. Cleanup, authority, quotas, endpoint restrictions and
response validation belong to the shared host unless an additional source-level
guarantee is separately demonstrated. Remote task ownership belongs to the peer
and its authorization boundary. Correct workflow sequencing remains application
behavior checked against independent expectations.

Use valid controls beside matched source defects. Include well-typed wrong
programs, especially duplicate submission after uncertain delivery and invalid
final evidence. Direct host probes bypass both language checkers. Isolated host
mutants remove one enforcement check to verify that its oracle detects the loss.
Do not credit shared runtime prevention to a language. Record any additional
earlier static rejection and its measured repair/context benefit separately.

## Fair clients and tooling

TypeScript uses the actual pinned strict compiler, discriminated unions,
exhaustiveness checks, runtime decoders and an appropriate pinned lint profile.
Private or branded handle APIs are paired with shared runtime membership and
ownership checks; erased brands alone do not establish runtime authority. It
receives an idiomatic scoped API for cancellation and cleanup. Ordinary strong
TypeScript facilities stay enabled even when they eliminate a possible Meda
advantage. Bespoke tools and their upkeep are recorded rather than treated as free.

Both arms receive equivalent context retrieval, versioned interfaces, revision
guards, edit grants, protected artifacts, validation and atomic publication.
Neither can modify the trusted host, checker, grant, or hidden acceptance suite
during an ordinary maintenance trial. Grant-changing tasks explicitly identify
their additional authority. TypeScript assertions and other escape routes are
handled by the declared baseline policy and runtime checks, not silently removed
from the language for this benchmark.

Use the same adapters and host binary, fresh peer state and equivalent snapshots
of credentials, budgets and inputs. Compare normalized observables after each arm
satisfies the independent oracle. Equality between two wrong answers is failure.
Record unavoidable differences in context APIs, diagnostics, accepted edits and
runtime containment before running. Report implementation maturity separately
from source-language properties.

## Finite build boundary

The [roadmap](interop-roadmap.md) defines seven work packets, D0-01 through D0-07.
The first five freeze the profile, build the common host and both clients, and
establish external acceptance and attribution. D0-06 admits the editing driver
and pilot; D0-07 runs and analyzes the held-out screen. This is the single packet
inventory for scope and iteration accounting.

Each packet permits one initial candidate and at most two repair cycles against
its agreed acceptance criteria. After that, an unresolved blocker stops admission
and produces a design decision: narrow a claim, revise the packet explicitly, or
pause the language work. A revision records a new scope and budget; it does not
silently reset this cap. Passing packets cannot acquire unrelated features under
the label of a repair.

This is a cap on scope and iterations, not an estimate of engineering hours.
Record actual implementation and review effort for both clients and shared code.
General scheduling, arbitrary FFI, durable workflows, full replay, broad protocol
coverage and unrelated language features are outside this milestone. If Meda
requires them merely to participate, stop and assess that implementation burden.

## Admission before model trials

The evaluator must verify all of these conditions:

- Both actual source clients pass the workflow's external normal and adverse
  cases. No claimed Meda mechanism is simulated by a handwritten substitute.
- Unauthorized dispatch, false accepted evidence, hidden uncertainty and dispatch
  of application work after local termination have explicit negative cases and
  independent witnesses. Reserved host cleanup requests remain separately allowed.
- Each task has a precise objective, equivalent allowed edits, a failing start
  and an accepted reference repair. References are smoke checks, not model trials.
- Repair workers cannot read hidden acceptance tests, reference repairs, other
  trials or the other language's implementation. Instruction-only isolation fails
  this requirement.
- A model driver records exact available model identifiers, version/selectors,
  sampling, prompts, candidate submissions, enforced limits and usage. Fresh
  subagents with unavailable model identity are not a substitute.
- Source, dependencies, peers, compiler options, grants, prompts, visible examples,
  acceptance rules and analysis code are frozen by digest. Hidden tests remain
  outside repair-worker filesystems.

The manifest must name two distinct model families and their actual version
selectors before execution. Names and provider prices are intentionally unset
until the driver is available. Missing required metadata means the controlled
study is not runnable; a demonstration cannot be relabeled as this study.

## Pilot and held-out screen

The development pilot uses two tasks: an ordinary report-schema change and an
effectful lifecycle change. Two models, two fresh repetitions and two languages
produce **16 trials**. Its purpose is to find harness failures, ambiguous tasks
and impractical limits. Pilot tasks and their variants never enter held-out scores.

Planning ceilings are 20 minutes of active trial wall time, 40,000 total charged
input/output tokens, and three submitted candidates per trial. These are proposed
limits, not known provider capabilities. The freeze must specify token accounting,
context-window treatment and cancellation behavior. Apply identical limits within
each model's paired language trials. One calibration revision is allowed after
the pilot; rerun the pilot under a new manifest and retain the earlier results.
Do not tune limits separately to favor either language.

The held-out screen has a planning floor of **12 independent maintenance tasks ×
2 models × 3 fresh repetitions × 2 languages = 144 trials**. This is a screening
design, not a power calculation. Use four ordinary behavior/schema/refactoring
tasks, four protocol/lifecycle/policy tasks and four effect/opacity/edit-boundary
tasks. Distinct tasks must change different requirements; input variants of one
bug do not count as independent tasks. Include sequential maintenance histories
where relevant, keeping every dependent history in one analysis cluster.

A separate author prepares held-out tasks without seeing pilot outcome rankings.
Audit the reference repairs and task solvability before freeze. Repair agents get
the same task objective, equivalent documentation budgets and their own visible
feedback. Randomize language order within model/task blocks and retain the seed.
Reviewers receive candidates in shuffled order without model or trial outcome
labels; source language itself cannot realistically be blinded.

Acceptance is evaluated after the candidate is final. Hidden results never guide
additional repair attempts. A changed task, judge or oracle starts a new study
version; it cannot retroactively turn an earlier failure into a pass.

## Outcomes and cost definition

The primary correctness outcome is an independently accepted change within the
trial limits, with no protected-artifact violation or regression. Report each
task/model/arm outcome, all candidates and failure categories. Timeouts and
infrastructure failures remain visible in the full denominator. A verified
infrastructure incident may trigger one replacement of the entire paired block
under a predeclared incident rule; retain the original block separately.

For this plan, **whole-change cost** is model inference cost plus metered execution
cost plus active human review time valued at a fixed **$100 per hour**.
That rate is an analysis convention, not a market claim. Use actual charges or
recorded billable usage with the frozen applicable price schedule. Do not infer
tokens from characters or treat subscription usage as free. Report unknown costs
as unknown and withhold cost-based conclusions when material inputs are missing.

Report aggregate cost per accepted change, including expenditure on failed trials;
if no change is accepted, the ratio is undefined and no efficiency win is possible.
Also report each cost component, success rate, total expenditure, wall time,
retrieved context and human minutes. Human repair produces a separately labeled
assisted outcome; its extra time and cost are reported separately and do not
change the primary model-only acceptance result or cost numerator.
Record compiler/tooling build and upkeep cost separately and show amortization
scenarios rather than hiding it inside a favorable trial average.

## Decisions and stopping rules

An unexplained safety or oracle failure blocks the affected profile. Equivalent
host protection supports runtime reuse; it does not establish protocol universality
or a Meda advantage. A pilot is diagnostic. The screen can justify further work,
expose usability problems, or show no promising difference; it cannot automatically
support a superiority claim.

The proposed confirmatory practical targets remain either **10 percentage points
higher accepted-task success**, with whole-change cost no more than **10% higher**,
or **20% lower whole-change cost**, with success no more than **5 percentage points
lower**. The 10% cost ceiling makes “no material cost regression” explicit for this
plan. These are proposed decision thresholds, not results.

Before a confirmatory run, preregister its task population, analysis, sample size
and uncertainty method using independent task-level variation. Preserve pairing;
do not count repetitions, assertions or input variants as independent tasks. Use
95% confidence intervals for the relevant differences/ratios, with the exact
method and any multiple-comparison adjustment frozen before outcomes are seen.
A positive claim requires the corresponding bounds to support every part of its
chosen practical target. Bounds spanning benefit and no useful benefit mean
inconclusive. A small observed tie is not evidence of equivalence.

If ordinary TypeScript tooling and the host supply every demonstrated benefit,
prioritize the library and require a new falsifiable language hypothesis before
expanding language scope. If a sufficiently informative confirmatory study rules
out the practical benefit needed to cover compiler/tooling upkeep, redirect the
product toward the library. Research may continue, but its positioning must stay
distinct from a demonstrated maintenance advantage.
