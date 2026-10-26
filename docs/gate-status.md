# Meda semantic gates status

Updated October 25, 2026. Gate A/B baseline repository: `6d01d7a1ff77f2fd04d0b7175f0b24bcf14ee19e`.

Draft 2.1 and its interoperability amendment specify the next bounded experiment.
The pure research implementation and shared-runtime comparison are executable.
The full Gate B controlled model study and the real-protocol D0 workflow have not run.

| Work | Status and evidence |
| --- | --- |
| Focused design amendment | Contract dependency protection, owned timeout cleanup, label-based callable compatibility, narrower shadowing, package identity and test boundaries are specified. |
| Gate A executable profile | 55 source cases specify values or parse/check/runtime diagnostics and run from outside through the CLI. |
| Edit enforcement | Tests cover selective/transitive helper weakening, constant changes, new dependency edges, unrelated edits, explicit specification grants, stale revisions/receipts, altered checks, scope escape and repair after type errors. |
| Gate B interpreter and tools | Pure operations, nominal records/enums, lists, loops/match, contracts, profile formatter, context description and single-file guarded edits are implemented. |
| Maintenance harness | 12 paired Meda/Python tasks, 24 reference-repair smoke rows. Every broken start is rejected and every reference repair accepted. |
| Full Gate B model trials | Not run. The harness requires an explicitly configured model driver. The separate shared-runtime study completed six uncontrolled fresh-context repair demonstrations; these do not satisfy the named-model controlled-study requirements. |
| Full gate decision | Open. The Python control needs comparable static checking; independent models, repeated trials, held-out tasks and outcome analysis are outstanding. |

The test command runs 23 test methods, including the parameterized 55-case CLI
corpus. The smoke runner also exercises all 12 Meda repairs through validation and
atomic publication. Stored [smoke results](../experiments/gates/benchmark/smoke-results.json)
are labeled `oracle_smoke`, `modelTrials: 0`, and `gateBDecision: not_evaluated`.
Smoke elapsed times are harness measurements and must not be interpreted as model
performance or language implementation benchmarks.

The prototype's implementation language is Python, chosen to execute the corpus
with the available runtime and no package installation. The production reference
design remains Rust. This does not change the target language semantics, but the
implemented profile is deliberately smaller; [PROFILE.md](../experiments/gates/PROFILE.md)
and the [deferred cases](../experiments/gates/corpus/deferred.json) define the boundary.

## Next acceptance gates

1. Freeze the [D0 protocol profile and acceptance artifacts](interop-workflow.md)
   under work packet D0-01 in the [roadmap](interop-roadmap.md).
2. Build the shared real-protocol host/adapters and strict TypeScript reference,
   then the minimum checked effectful Meda profile. Preserve direct host probes
   and independent expected outcomes; passing integration does not establish
   language value.
3. Admit the [maintenance pilot and held-out screen](interop-evaluation.md) only
   after matching edit facilities, protected workers, a named model driver and
   enforced budgets exist. Preserve failed attempts and all-attempt costs.
4. Retain the broader Gate B/C/D/E/F obligations. The pure Python control still
   lacks comparable static checking and cannot independently support a language
   advantage claim. D0's TypeScript control does not retroactively fix that study.

The [design amendment](interop-design-amendment.md) permits this bounded C/D0
sequence before broad model-runtime investment. It leaves general composition,
generation, concurrency, replay and edition readiness outside the new milestone.

## Shared runtime comparison on October 25

An isolated [Meda and TypeScript comparison](runtime-comparison.md) now executes
the real pure Meda client and a strict TypeScript client over identical shared
host/adapters. Both pass 12 workflow cases and reject the same four static defects.
Direct host tests and client-policy mutants distinguish library enforcement from
application sequencing. Three fresh-context repairs per arm pass, but these are
uncontrolled repair demonstrations, not the full Gate B model comparison.

The result supports prioritizing reusable host/adapters with a first-class
TypeScript client. It leaves Meda's incremental language value unproven. The
custom loopback wire fixtures do not establish MCP/A2A conformance or complete
Gate D0; the effectful runtime, actual protocol peers and binding-drift work remain
open. Existing Gate A/B implementation and pass counts are unchanged.

## Planned interoperability profile

`meda-interop-d0/1` now has a workflow specification, twelve acceptance families,
a paired evaluation plan and seven dependency-ordered work packets. These are
planned acceptance requirements, not executed cases. Protocol pins are MCP
2026-07-28 Streamable HTTP and A2A 1.0.0 JSON-RPC; exact SDK/schema/build pins must
be frozen before execution. The profile requires real checked direct host calls,
one-package modules/visibility, opaque references, monomorphic effect checking
and bounded root cleanup. The current pure interpreter implements none of those
new mechanisms yet. No existing gate is marked complete by this amendment.
