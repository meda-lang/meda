# Executable Meda research profile

Profile: `meda-pure-b0/1`. Python 3.11 or later, Linux/macOS, standard library only.
This interpreter runs a subset of Draft 2.1. It is an experimental acceptance
implementation. The planned reference compiler remains Rust.

## Source and supported behavior

Use `operation name(label: Type) -> Type effects [] { ... }`. Every call supplies
all labels exactly once, in any order. Arguments evaluate in written order.
Operations return explicitly on every reachable path. Declarations can be
forward-referenced. `self.name` selects a module operation or module constant.

Types are `Bool`, arbitrary-precision `Int`, `Text`, `Unit`, `List<T>`, monomorphic
nominal records and enums. `true`, `false`, `unit`, double-quoted text, and decimal
integers are literals. `Int` division truncates toward zero; remainder has the
dividend's sign. Boolean conditions have no truthiness. `and`/`or` short-circuit.
`implies` is permitted in contracts and assertions only.

Statements end at newlines or the closing block brace. Named arguments, lists,
record fields, and parentheses allow multiline expressions. `return` followed by
a newline returns Unit. No semicolons. `//` comments are retained in source edits.
Text supports `\"`, `\\`, `\n`, `\r`, `\t`, `\u{HEX}` and Unicode scalars.

`let` is immutable; `var` allows whole-binding reassignment. Local annotations are
optional when unambiguous. Values are immutable; record updates create copies:
`old with { count: 5 }`. Lists iterate snapshots. Local-on-local shadowing is an
error; a local may share a module declaration's name. Empty lists need a type.

`if`/`else`, `while`, `for item in items`, `break`, `continue`, and exhaustive
Bool/enum `match` statements are implemented. Record construction is `Item { x: 1 }`.
Enum construction is `State.Ready` or `State.Waiting(days: 4)`; matching uses
`State.Waiting(days: days) => { return days }`. Payload patterns name every field.
Only Bool/enum/wildcard patterns are supported in this profile.

Pure intrinsics: prelude `range(start:, end:, step:)`; explicit imports
`import std.list as list` and `import std.text as text` expose
`list.append(items:, value:)`, `list.length(items:)`, `text.length(value:)`.
Ranges are half-open and zero step faults. Text length counts Unicode scalars.

`require` and `ensure` precede the opening body brace, one clause per line.
`result` names the postcondition value. Contract helpers must be pure, acyclic
including implicit contracts, and contain no `while`. Finite loops are metered.
Contracts execute on every invocation. Tests use `test "name" { assert ... }`.
Each test receives fresh evaluator state; faults fail that test and later tests run.
An empty suite cannot satisfy `test`. Separate acceptance cases invoke operations
through JSON, validating inputs at the boundary.

## Commands

From the repository root:

```sh
python3 experiments/gates/meda.py check experiments/gates/corpus/large-integer.meda
python3 experiments/gates/meda.py run experiments/gates/corpus/large-integer.meda
python3 -m unittest discover -s experiments/gates/tests -v
python3 experiments/gates/benchmark.py --smoke --output /tmp/meda-smoke.json
```

`run --operation NAME --arguments '{"value": 3}'` invokes a pure library operation;
it does not implement the target edition's application entry signature.
`fmt` writes formatted source to stdout; `fmt --check` returns 1 on differences.
The profile formatter normalizes LF, structural indentation and the final newline,
preserving literal spelling and comments. Full edition wrapping/trailing-comma
formatting remains deferred. Guarded body publication preserves every other byte;
it does not silently run a whole-file formatter.

`describe --operation NAME --grant grant.json` returns checked context.
`edit --grant grant.json` consumes one JSON request per line. Methods are
`describe`, `begin_edit`, `replace_body`, `validate_edit`, `commit_edit`, and
`transaction_status`. See `schemas/` and `PROTOCOL.md`. Exit codes: 0 success,
1 failed test/format check, 2 parse/check/input/protocol setup failure, 3 source
runtime fault, 4 host/infrastructure failure. Runtime errors are structured JSON.

## Explicit limits

There are no providers, tools, I/O effects, live fallback, opaque types, operation
values, generics beyond builtin List, effect polymorphism, maps, Option/Result,
postfix `?`, examples blocks, package resolution, full visibility enforcement,
float/bounded numeric types, character/duration/raw multiline literals, scalar
match patterns, or cross-file edits. These constructs are rejected, not emulated.
The manifest of deferred acceptance cases keeps their status separate.

The profile caps source at 128 KB, values at 100,000 top-level items/scalars,
integer values at 16,384 bits, call depth at 80 and evaluation at configurable fuel
(default 100,000). These are experimental containment limits, not Edition 1's
resource model. Parsing/checking and host protocols require a supervised worker
when processing adversarial input. The CLI is for local trusted experimentation;
it is not a service sandbox. Acceptance tests invoke its external process under
a 5-second supervisor. Python controls run under CPU/memory/wall limits.

## Python comparison profile

Use annotated, keyword-only Python functions and explicit returns. Both arms see
the same task and visible examples, receive the same attempts/time allowance, and
are judged on identical acceptance inputs/outputs. Allowed Python operations are
pure arithmetic, conditionals, loops, lists/dicts, direct functions and
`len`, `range`, `sum`, `abs`, `min`, `max`. The control uses Python's actual parser
and runtime in a bounded worker. AST checks preserve interfaces and forbid imports,
attributes, classes, decorators, dynamic code and unrelated declaration changes.

The Python arm currently has syntax/scope checking and acceptance validation but
no third-party static type checker. That is a material tooling asymmetry. Treat
results as a harness screen until the baseline gains equivalent typed checking.
Source numeric semantics also differ outside this task set; the tasks avoid
negative remainder and other cross-language differences.
