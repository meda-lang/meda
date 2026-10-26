# Shared runtime comparison protocol

Status: preregistered development experiment, written before comparison results.
Protocol created at 2026-10-25T07:14:48Z. Baseline Meda commit:
`1053416ff04d100072fd0cd32458111726bae60d`.

## Question and scope

Which protections and maintenance advantages in a small agent workflow come from
the application language, and which come from a runtime that an ordinary typed
client can also use?

The executable Meda implementation is the existing `meda-pure-b0/1` interpreter,
not the proposed effectful runtime. The first comparison therefore runs two
**decision clients**: real Meda source and a conventional strict TypeScript
module. Each receives a checked immutable snapshot and returns a typed decision.
One shared host executes admitted decisions through the same adapter functions.
The host owns network I/O, task state, authority, budgets, and publication.

This experiment measures the implemented decision boundary. It does not measure
Meda's proposed effect system, opaque capabilities, native model integration,
structured concurrency, production cleanup, or durable replay. It is a precursor
to the effectful Gate D comparison, not completion of Gate D or the full Gate B
maintenance study.

**Important identification limit:** choosing a shared host deliberately places
many protections in that host. Equal runtime outcomes therefore demonstrate
shared enforcement in this architecture; they do not prove that a fully
implemented language could add no protection. A language-value verdict requires
evidence beyond equality on deliberately shared behavior.

## Arms and fixed controls

| Component | Meda arm | TypeScript arm |
| --- | --- | --- |
| Application behavior | Checked Meda decision operation | Strictly checked TypeScript decision function |
| Runtime boundary | Shared host contract and admission checks | Exactly the same contract and checks |
| Remote adapters | Same implementation, configuration and fixtures | Same implementation, configuration and fixtures |
| Inputs and expected results | Identical scenario inputs and independently specified expectations | Identical inputs and expectations |
| Source checking | Actual existing Meda parser/checker | Actual TypeScript compiler, not a homemade approximation |
| Execution | Existing Meda evaluator in bounded process | Emitted JavaScript in bounded process |
| Local effect containment | Pure implemented language subset plus host process boundary | Explicitly documented module/process boundary; TypeScript types alone do not sandbox JavaScript |

Use strict TypeScript checking and ordinary idioms: discriminated unions,
exhaustive switches, readonly data where applicable, and runtime validation at the
shared boundary. Record the exact compiler version/options. Do not omit a
reasonable baseline safeguard solely to manufacture a Meda advantage. Conversely,
do not claim TypeScript's erased types provide runtime validation or containment.

Each arm gets separate initial state and an equivalent fresh peer instance or
reset. Do not let the second arm inherit a completed task, cache, quota, credential,
or side effect from the first. Compare normalized results and observable dispatch
traces, not random IDs, ports, clocks, or process startup times.

Freeze source, host, fixtures, this protocol, checker configuration and harness
digests before recording results. Subsequent repairs produce a new manifest and
an explicit rerun; never silently combine pre-fix and post-fix rows.

## Claims and attribution tests

The experiment must report at least three layers separately.

1. **Client checks.** Inject matched source defects such as wrong return type,
   incorrect decision variant, missing required field, and wrong argument label.
   Record the actual checker diagnostic and whether execution was prevented.
   Include a valid control for every rejection. Checker tests are not runtime
   security tests.
2. **Shared host protections.** Submit equivalent invalid decisions or observations
   from both arms, including a bypass fixture that emits decisions directly
   without either source checker. Test wrong principal/tenant, stale binding,
   unauthorized operation, exhausted budget, malformed remote output, and
   uncertain delivery. If the shared host rejects the bypass too, attribute that
   protection to the host. This is a useful result, not evidence of language
   superiority.
3. **Application correctness and maintenance.** Test nontrivial decision bugs
   that remain well typed, such as retrying an uncertain submission, mishandling
   pending input, or accepting invalid final evidence. Identical acceptance
   expectations distinguish correct behavior from merely matching behavior.

Where practical, remove one host check in an isolated mutant and demonstrate
that its corresponding test fails. Such an ablation validates the test's
sensitivity; it is never a configuration offered to users. If ablation is not
implemented, report that absence instead of claiming causal enforcement proof.

Do not accept a passing echo round trip as an independent oracle. Expected
dispatch counts, accepted values, terminal state, and error categories must be
specified outside both client implementations and the common decoder. Compare
both arms against those expectations, then compare arms with each other.

## Minimum scenario families

Freeze concrete case IDs and expectations in a machine-readable fixture before
the measured run. The following families are the minimum useful screen; the
implementation may split them into multiple rows.

| Family | Observable expectation |
| --- | --- |
| Successful evidence and agent result | Approved evidence read and task workflow produce the exact accepted result |
| Pending task | Observation/polling progresses without another task submission |
| Input required | Missing input remains pending; supplied authorized input continues the existing task |
| Unknown submission outcome | No automatic duplicate submit; uncertainty remains visible |
| Cancellation or local stop | No further local dispatch after termination; no invented remote rollback |
| Wrong principal or tenant | Host rejects before unauthorized peer dispatch |
| Binding/schema drift | No silent use of changed operation semantics |
| Malformed peer response | Typed boundary failure; no accepted domain value |
| Exhausted budget | Exact admission ceiling; valid work below the ceiling still succeeds |
| Validly typed client bug | Acceptance oracle catches an incorrect action or final value |

Fixture peers may use loopback HTTP/process transport to expose actual framing
and process boundaries. They remain locally authored fixtures. Do not call them
independent protocol implementations, official MCP/A2A conformance, or production
authorization testing. If official peers or suites are unavailable, record them
as unmeasured, not failed or passed.

## Small maintenance screen

After baseline correctness and matched task validation, run fresh-context repair
trials on the same task objective, equivalent broken behavior, and equivalent
visible examples. A single model family with a few tasks is a development screen
only. Model version, sampling, token usage and elapsed inference time must be
reported only when actually exposed by the execution interface. Unknown means
unknown; wall time and output bytes are not token estimates.

Suggested matched tasks, using only the implemented pure interface:

1. **Do not duplicate uncertain work.** Repair a branch that resubmits after an
   unknown submission outcome. Known pending tasks must still be inspected;
   proven not-dispatched work can follow the specified retry policy.
2. **Preserve pending input.** Repair a branch that reports success or submits a
   new task when an existing task requires input. Continue only when the
   supplied input is present and approved under the given snapshot.
3. **Honor the polling allowance.** Repair an off-by-one admission decision.
   A task completed at the boundary may publish; an additional poll must not
   consume nonexistent allowance.
4. **Validate evidence before publication.** Repair a branch that accepts a
   terminal remote artifact without checking the required local evidence rule.
   Valid artifacts must remain publishable; terminal failure is not success.

These are task suggestions until the fixture manifest is frozen. Do not claim
all four were tested if only a subset is implemented. All starting programs
must fail at least one independent acceptance case, and reference repairs must
pass before model trials. Reference repairs are smoke evidence, not AI results.

For an initial screen, use one fresh trial per selected task/language pair,
allow at most three submitted candidates, and enforce the same 180-second
proposal budget per trial where the driver supports reliable timing. Alternate
language order deterministically. If the available agent interface cannot enforce
these limits or expose submission/time records, label the run an **uncontrolled
repair demonstration** and report which controls were missing. Do not relabel
it as the full preregistered experiment.

Repair agents receive only their task packet, source, profile instructions,
visible examples and their own prior feedback. They must not receive the other
arm's source, hidden expected values, reference repair, or analysis results.
An instruction not to read hidden files is not a sandbox. Record whether actual
filesystem isolation was enforced. Full parent-history forks contaminate a
blind trial; use fresh-context agents or a model driver that receives only the
packet. Evaluate saved candidates outside the agent with unchanged tests.

## Metrics

Report counts with denominators and explicit stage labels:

- Baseline cases passed/failed for each arm against the independent oracle.
- Equal/different normalized decisions and dispatch traces.
- Matched static defects rejected and diagnostic stage.
- Host bypass/ablation cases detected, with the enforcing layer named.
- Maintenance task acceptance, submitted candidates, and failures for every
  trial. Keep infrastructure/time failures separate but in the denominator.
- Source changes and changed functions for repairs; code size is descriptive,
  not a quality score. Any review burden is measured separately or unmeasured.
- Real measured cost/time where available, without comparing only successful
  trials or mistaking interpreter startup for language-design efficiency.

Do not report a confidence interval or superiority percentage from a handful of
uncontrolled agent trials. Do not pool repeated variants of the same defect as
independent evidence of a general language advantage.

## Preregistered decision rules

These rules precede results. They intentionally support a limited decision.

1. Any unexplained mismatch against the oracle, unauthorized dispatch, false
   final value, or lost uncertainty blocks the corresponding profile. Fix and
   rerun before promoting it.
2. Equal success on shared-host safety cases supports **runtime reuse is viable
   for these cases**. It does not establish universal protocol compatibility or
   justify stopping the language by itself.
3. A source-check advantage is credited only for a matched defect not already
   caught by the baseline's reasonable checker/linter configuration; document
   the exact extra mechanism and its cost. A host denial is not credited to a
   language checker.
4. The maintenance screen can reveal usability failures and motivate follow-up.
   It cannot establish a general productivity advantage. Ties, unknown costs,
   or small observed differences mean **inconclusive**, not Meda wins or loses.
5. If both clients complete the workflow and all demonstrated protection lives
   in the shared host, prefer further investment in the reusable host/adapters
   while keeping the language claim unproven. That is an implementation priority,
   not a final product-abandonment decision.
6. A full language/product decision still needs the same adapter boundary used
   by an implemented effectful Meda client and an equally equipped typed control,
   held-out multi-file tasks, multiple named models, repeated fresh trials, and
   whole-change review/cost evidence. Stop or redirect if that stronger study
   supplies no material benefit against the ongoing compiler/tooling cost.

For that later study, a reasonable screening target is at least 10 percentage
points higher task success without material cost regression, or at least 20%
lower whole-change cost at comparable success (within 5 points). These are
predeclared practical margins, not proof thresholds; power and uncertainty must
be designed using independent task-level variation. The small initial screen
cannot meet that evidentiary burden regardless of a favorable percentage.
