# Meda

**Meda is an experimental programming language for software that AI agents write
and maintain.**

The goal is to let a coding agent make a correct change with limited surrounding
context. The design combines explicit operation types and effects with
behavioral contracts. Editing tools restrict which code an
agent may change and check that it preserves protected contracts and interfaces.
The intended language supports ordinary application code as well as programs
that call LLMs, tools, and other agents.

**Today, this is a research prototype.** A small, pure subset of Meda runs.
The working MCP and agent-to-agent integration runs in TypeScript. The Meda
version of that integration is still missing, and there is no stable release.

## Why build a language?

That is the question we are testing. We compare Meda with a conventional strict
TypeScript client using the same runtime and protocol adapters. Protections
supplied by that shared runtime are useful to either language.

The [first comparison](docs/runtime-comparison.md) produced the same outcomes in
both languages. It did not establish a language advantage or a maintenance
productivity gain. Our current recommendation is to prioritize the reusable
runtime and keep TypeScript as a first-class client while testing whether Meda
adds enough value to justify a new language. A library-first direction remains
a valid outcome.

## What exists today

| Part | Implemented | Still proposed or unproven |
| --- | --- | --- |
| Meda language | A Python-based parser, type checker, and evaluator for pure operations, records, enums, lists, and runtime-checked contracts. | The full language design, including direct external calls and effect checking. |
| Editing tools | Guarded single-file edits with revision checks, protected contracts, and validation before publication. | Better AI maintenance outcomes than equally equipped conventional tools. |
| Protocol runtime | A Python host, strict TypeScript client, and official SDK test peers for MCP and A2A. | Direct Meda integration, full acceptance, and production readiness. |

The [implemented language profile](experiments/gates/PROFILE.md) defines what
actually runs. [Design Draft 2.1](docs/design-draft-2.1.md) describes the larger
proposal; its examples are not all executable yet.

## Try actual Meda code

This [complete example](examples/clamp.meda) runs with the current interpreter:

```meda
operation clamp(value: Int, lower: Int, upper: Int) -> Int effects []
  require lower <= upper
  ensure result >= lower and result <= upper
{
  if value < lower {
    return lower
  }
  if value > upper {
    return upper
  }
  return value
}
```

`operation` declares a typed function. `effects []` means it is pure; this
prototype only supports pure operations. `require` checks a condition before
the body runs, and `ensure` checks the result afterward. These contracts run on
each invocation; they are not a proof that the implementation is correct.

From the repository root, using Python 3.11 or later, with no packages or API
keys to install:

```sh
python3 experiments/gates/meda.py check examples/clamp.meda
python3 experiments/gates/meda.py run examples/clamp.meda \
  --operation clamp --arguments '{"value": 12, "lower": 0, "upper": 10}'
```

The second command returns `{"profile": "meda-pure-b0/1", "value": 10}`.
For the language and editing checks:

```sh
python3 -m unittest discover -s experiments/gates/tests -v
```

## How MCP, other agents, and Meda fit together

Applications use typed operations exposed by a shared host. The host owns
credentials, permissions, budgets, and protocol adapters. MCP (Model Context
Protocol) connects to tools and data; A2A (Agent2Agent) connects to remote tasks.

```mermaid
flowchart TD
  TS["TypeScript application: implemented"] --> Host["Shared host and protocol adapters"]
  Meda["Meda application: direct calls planned"] -.-> Host
  Host --> MCP["MCP tool server"]
  Host --> A2A["A2A agent"]
```

Follow the [wiring walkthrough](docs/wiring-walkthrough.md) or start with the
actual [TypeScript workflow](experiments/interop_d0/client/workflow.ts). The
example reads evidence, submits a report task, polls it, and validates the
result. Its peers use real protocol SDKs with deterministic test behavior;
there are no LLM provider calls.

The earlier [Meda workflow sample](experiments/interop_compare/clients/policy.meda)
only computes the next action for a Python controller to execute. It does not
make direct protocol calls. New protocols will require their own adapters and
compatibility checks.

## What happens next

The next milestone is [one bounded Meda versus TypeScript experiment](https://github.com/meda-lang/meda/issues/10):
implement the minimum Meda support for direct host calls, run both clients
through the same workflow, and attempt one equivalent maintenance change.
Fix the defects that block that comparison, then make an explicit decision to
continue the language, focus on the library, or stop. The broader language
design is not a commitment to implement every proposed feature first.

For more detail, see the [roadmap](ROADMAP.md),
[research handoff and evidence index](docs/research-handoff.md), and
[tracked work](docs/issues/README.md).

## Project history

The [original prototype notes](docs/history/original-prototype.md) preserve the
earlier syntax ideas and the story of Meda's name and Sammy the seal.
`sample/`, `interpreter/`, and `interpreter_new/` are legacy work; use the
example and research implementation linked above for the current project.
