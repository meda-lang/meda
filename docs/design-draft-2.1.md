**Draft 2.1. Proposed target: Meda Edition 1.**

This focused amendment incorporates the [second adversarial review](https://chatgpt.com/space/page_96ab977aba3c81919ecb319a9ac7342c). It preserves the core architecture while specifying executable contract protection, cancellation ownership, callable compatibility, and the Gate A/B acceptance boundaries.

Meda is a programming language for AI-authored and AI-maintained software, including programs that use large language models. Its primary objective is a correct behavioral change with limited surrounding context, supported by explicit types, effects, domain invariants, and compiler-checked edit boundaries.

This revision replaces [Draft 1](https://chatgpt.com/space/page_7999496119cc8191a579ac58ed8bb3fb) as the proposed design and incorporates the [adversarial review](https://chatgpt.com/space/page_dec3ec48887c8191bed62e7b4ab9e2d0). It chooses a composable direct-style core, opaque domain types, reusable contract predicates, compact operation declarations, and a model runtime with explicit policy and authority. These choices define a concrete candidate; claims about better AI performance remain experimental.

“Must” describes the target edition. The first prototype implements a deliberately smaller subset, specified in section 24. This is a complete architectural proposal for that target, with semantic rules, worked programs, and conformance gates. It is not an implemented compiler or a claim that every future library and protocol schema is already frozen.

# 1 Goals and architectural commitments

Meda should support ordinary computation, data transformations, command-line tools, internal automation, and bounded model workflows. A program that never calls a model remains a first-class program.

The primary hypothesis is that enforceable interfaces let an AI make useful changes with less context and fewer regressions. A separate hypothesis is that a typed model runtime makes model applications easier to maintain. The evaluation must measure these independently; success on one does not establish the other.

| Commitment | Meaning |
| --- | --- |
| Reusable behavior | Ordinary application code can pass typed operations to collection and workflow abstractions. |
| Preserved domain invariants | A module can expose a type while retaining construction and update rights. |
| Explicit external behavior | Operation types carry effect bounds; the host grants actual authority. |
| Shared validation machinery | Ordinary contracts and model validators reuse a bounded, checkable pure subset. |
| Precise changes | The compiler supplies resolved context, revision guards, protected interfaces, and required validation. |
| Honest model boundaries | Generation is fallible; accepted structure, checked relationships, provenance, and truth are different properties. |
| One authoritative program | Source is versioned; semantic views and schemas are derived from it. |
| Evidence before expansion | The first executable milestone includes the AI change loop. |

Edition 1 uses direct-style operations. Calling an effectful operation executes it within the current structured scope; constructing a reference to that operation does not execute it. There is no universal deferred-computation type, second model-task declaration, or separate editable code database.

The target includes named operation references, limited type/effect generics, opaque records, and bounded collection concurrency. It excludes capturing closures, arbitrary effect handlers, macros, inheritance, operator overloading, shared mutable memory, detached tasks, arbitrary native extensions, public streams, durable workflows, autonomous model write tools, and general formal verification.

The compact source notation is the Draft 2 baseline. The earlier sectioned notation remains a benchmark frontend over the same semantics, rather than a second syntax accepted by the released language. A syntax comparison must not give one candidate better compiler tools or a weaker test suite.

# 2 Source and lexical rules

Source is UTF-8. Keywords and identifiers are case-sensitive. Identifiers use ASCII letters, digits, and underscores, beginning with a letter or underscore; Unicode is supported in text and comments. Restricting identifiers initially simplifies tooling and avoids visually indistinguishable names. Keywords cannot be identifiers. Language-level names beginning with `__meda` are reserved for the toolchain.

Files use the `.meda` extension. Both LF and CRLF are accepted; formatting emits LF, two-space indentation, and a final newline. Formatting is automatic in editing tools and available through `meda fmt`. Unformatted but syntactically valid source compiles. `meda fmt --check` is a separate CI policy.

`//` starts a line comment. `///` attaches documentation to the next declaration or field. Block comments are omitted in Edition 1. Comments and documentation are preserved by formatting and semantic edits; documentation is metadata, never an executable instruction to the compiler.

Statements end at a newline or the closing brace of their body block. Newlines inside argument lists, list literals, and record construction/update fields are insignificant. A statement continued elsewhere must wrap its expression in parentheses. A newline after `return` always ends that statement. There is no semicolon statement syntax and no automatic attachment of the next line to the previous statement.

Record fields, enum cases, parameters, arguments, and list elements are comma-separated; a final comma is allowed. The formatter uses trailing commas in multiline lists. Declaration headers have grammar-defined continuations; body statements and individual contract clauses remain newline-separated. An opening expression brace does not globally disable statement boundaries.

Text uses double quotes with `\"`, `\\`, `\n`, `\r`, `\t`, and `\u{HEX}` escapes. Triple double quotes delimit raw multiline text. Their content is preserved exactly after line-ending normalization, including indentation and leading/trailing newlines; an embedded delimiter must use ordinary escaped text concatenation. There is no interpolation in Edition 1. `Text + Text` concatenates text; scalar formatting uses standard-library conversion operations.

Character literals use `c"A"` and contain exactly one Unicode scalar after escape decoding. Decimal integer literals support interior underscores and a leading unary minus. Float literals require a decimal point or exponent. Hexadecimal/binary integer literals, arbitrary literal suffixes, and implicit string-to-number conversion are excluded initially. Duration literals use an integer followed by `ns`, `us`, `ms`, `s`, `m`, or `h`, such as `10s`.

Operation headers contain a name, optional generic parameters, named parameters, output type, and effect bound. A header may span lines until its body begins. Each require/ensure clause ends at its statement newline; a continued contract expression uses parentheses. A final examples block attaches to the preceding operation.

Statement/declaration keywords are reserved. The generation clause words model, instruction, input, policy, tools, and validate are contextual keywords inside a generation form and may appear in ordinary qualified names elsewhere. The name result is reserved for the postcondition value and cannot be declared as a binding or parameter. Built-in type names cannot be redeclared. These lexical decisions must be enumerated in the lexer fixture set.

# 3 Types and value semantics

## Primitive types

| Type | Meaning and required behavior |
| --- | --- |
| `Bool` | Exactly `true` or `false`; conditions have no truthiness conversions. |
| `Int` | Arbitrary-precision signed integer, limited by runtime resource budgets. |
| `I64`, `U64` | Explicit bounded integers; arithmetic overflow/underflow is a runtime numeric fault. |
| `Float` | Finite IEEE 754 binary64 values; operations that would produce NaN or infinity fault. Positive and negative zero compare equal. |
| `Text` | Immutable Unicode scalar sequence; no implicit Unicode normalization. |
| `Char` | Exactly one Unicode scalar, which may be part of a multi-scalar visible character. |
| `Bytes` | Immutable byte sequence. |
| `Unit` | One value, written `unit`. |
| `Duration` | Signed 64-bit nanoseconds; duration literal overflow is a compile error. |

`Int` is the default integer type because ordinary application logic should not silently lose precision or wrap. Bounded types serve explicit storage, protocol, and performance requirements. Numeric literals may be checked against an expected numeric type when their values are representable. That contextual literal typing does not permit conversion of an already-typed value.

Mixed numeric arithmetic is rejected. Conversions are explicit operations; conversions that can fail or lose required information return a `Result`. Integer division truncates toward zero; remainder has the dividend's sign. Division/remainder by zero and bounded signed minimum divided by minus one fault. `Float` division follows the finite-value rule. Applications handling untrusted numeric input can use checked library operations that return arithmetic errors instead of invoking faulting operators.

Basic floating arithmetic rounds to binary64 at each operation, with round-to-nearest ties-to-even and no contraction into fused operations. Transcendental library functions have documented accuracy rather than a cross-platform bitwise guarantee. Floating point is not a money type; applications use integer minor units or a future decimal library.

## Composite types

`List<T>`, `Map<K, V>`, `Option<T>`, `Result<T, E>`, and `Range` are standard generic/builtin types. All elements and keys have statically known types. There is no implicit top type, universal `null`, or dynamically typed escape hatch. Standard JSON parsing uses an explicit tagged `Json` value.

Lists are ordered. Maps preserve insertion order; replacing an existing key preserves its position. Map equality compares the ordered sequence of keys and values, making that observable order part of the value. Duplicate keys supplied to a map constructor are errors. Lists and maps expose lookup operations returning `Option`, not unchecked indexing. A map key must satisfy the compiler-defined `Hashable` capability. `Float` is deliberately excluded from map keys in Edition 1.

Records and enums are nominal: declaration identity matters, not merely field shape. Ordinary public records expose their fields and constructors; all fields must be supplied explicitly. Opaque records provide the protected construction boundary described in section 4. Defaults, implicit constructors, and inheritance are excluded.

```meda
record Experiment {
  id: Text,
  owner: Option<Text>,
  ageDays: Int,
}

enum Health {
  Healthy,
  Stale { days: Int },
  MissingOwner,
}

record Box<T> {
  value: T,
}
```

Enum values use qualified cases: `Health.Healthy`, `Health.Stale(days: 45)`, `Option.Some(value: "Jesse")`, and `Option.None`. No implicit conversion occurs between an enum and its textual name or integer ordinal. Enum order is not meaningful unless an application defines it.

Generic records, enums, and operations are supported. Generic arguments on types use `Box<Int>`. Explicit expression specialization uses `identity::<Int>(value: 4)` to avoid ambiguity with comparison operators. Type arguments may be omitted only when the checker finds one unique solution from arguments and expected output. An empty list without an expected element type is an error.

User-defined traits are excluded, but generic declarations may use compiler-defined constraints: `where T: Eq`, `Ordered`, `Hashable`, `Serializable`, or `ModelData`. Multiple constraints on one parameter use `+`, as in `where T: Eq + Serializable`. `Eq` supports structural equality. `Ordered` is available on Int, I64, U64, Float, Text, Char, and Duration; text/character order is lexicographic Unicode scalar order. `Hashable` implies `Eq`. `Serializable` and `ModelData` govern the wire formats defined later. Eq, Hashable, Serializable, and ModelData derive for eligible ordinary records/enums from their fields; Ordered does not. Opaque-record derivation follows section 4 instead. No structural subtyping, implicit variance, overloaded operations, or overloaded operators are permitted.

Finite recursive values are allowed through enums and containers. Cyclic values and direct infinitely sized record definitions are rejected. Ordinary generic records, enums, and containers may hold monomorphic operation references. Such values do not automatically acquire Eq, Hashable, Serializable, or ModelData. Host capability references cannot be stored or serialized by application code; authority is bound by the host.

Operation-reference types are structural in their parameter labels, parameter types, result type, and effect bound, as specified in section 6. Data types remain nominal. There are no higher-rank generic values or implicit variance for data containers.

Every value is logically immutable. let creates an immutable binding; var permits whole-binding reassignment. Both require initializers. Local annotations may be inferred uniquely; public interfaces, record fields, and module constants require explicit types.

```meda
let original: List<Int> = [1, 2]
var updated = original
updated = list.append(items: updated, value: 3)
let revised = experiment with { ageDays: 46 }
```

Reassignment and record update do not modify aliases. A record update preserves its nominal type and rejects unknown or duplicate fields. External code cannot update an opaque record. Runtime structural sharing and copy-on-write are permitted only when unobservable.

Scope is lexical. Parameters and local bindings cannot shadow an enclosing parameter or local binding; sibling scopes may reuse names. A local binding may share a module declaration's name and takes precedence in value expressions. Types resolve in type positions independently of local value names. The reserved qualifier self names the current module, so self.normalize refers to the module operation even beside a local normalize. Import aliases and self cannot be rebound. Adding a module helper therefore cannot invalidate an existing local binding. Duplicate module declarations remain errors. Module constants use literals, constructors, constant operators, and statically resolved monomorphic operation references; they cannot execute operations or host effects. Compare this narrower rule with Draft 2's global ban at Gate C.

# 4 Opaque domain types

A public opaque record is nameable outside its defining module, but its representation belongs to that module.

```meda
module identifiers

import std.text as text

public opaque record ExperimentId derive [Eq, Hashable] {
  raw: Text,
}

public enum IdError {
  Empty,
}

public operation parse(value: Text)
  -> Result<ExperimentId, IdError> effects [] {
  if text.length(value: value) == 0 {
    return Result.Err(error: IdError.Empty)
  }
  return Result.Ok(value: ExperimentId { raw: value })
}

public operation toText(id: ExperimentId) -> Text effects [] {
  return id.raw
}
```

Only the defining module may construct the record, read its representation fields directly, or apply with updates. Other modules may hold, pass, and return it through public interfaces. Exported observer and constructor operations are ordinary operations with ordinary effects and errors.

Opacity applies to every route: record literals, structural update, pattern matching, reflection, generic decoding, and host bindings. Edition 1 has no reflection escape. Opaque records do not derive Serializable or ModelData. Convert to a public transfer type explicitly; convert back through a checked constructor. A host adapter cannot inject an opaque value merely by claiming its wire type.

Opaque types derive no public structural capabilities by default. Their owner may explicitly derive Eq and Hashable if the representation supports them; Hashable also requires Eq. This exports equality/hash behavior without exporting fields. Ordered and automatic serialization remain unavailable. Generic derivation conditions are checked for each instantiation and form part of the exported type interface.

A public interface cannot mention a private nominal type. A public opaque type is the supported way to expose a name while hiding representation. This rule also applies inside callable types and generic arguments.

Opacity establishes which module's operations created or changed a value. It does not prove those operations correct, establish factual truth, or provide authorization revocation. An agent authorized to rewrite the owning module can change its validation behavior; protected contracts, tests, and edit grants govern that change.

# 5 Operations and control flow

An operation is the only user-defined callable construct. Every declaration has explicit parameter and result types and an effect bound. Its body uses explicit returns.

```meda
public operation clamp(value: Int, lower: Int, upper: Int)
  -> Int effects []
  require lower <= upper
  ensure value < lower implies result == lower
  ensure value > upper implies result == upper
  ensure (lower <= value and value <= upper) implies result == value
{
  if value < lower {
    return lower
  }
  if value > upper {
    return upper
  }
  return value
}
examples {
  { value: -3, lower: 0, upper: 10 } => 0
  { value: 4, lower: 0, upper: 10 } => 4
}
```

Calls supply every argument by name exactly once. Defaults, positional arguments, splats, overloading, and variadic parameters are excluded. Arguments evaluate left to right in written order; declaration order does not reorder effects. Named labels are part of the callable interface.

The checker rejects reachable fallthrough, including in Unit operations, which return unit explicitly. Direct and mutual recursion are allowed outside the contract-safe subset. Recursion is bounded by root execution limits; it is not a termination proof.

From strongest to weakest, precedence is: call/field selection/record update/postfix ?; unary ! and -; multiplication/division/remainder; addition/subtraction; ordering; equality; and; or; implies. Arithmetic associates left, implies right. Ordering and equality comparisons cannot chain. and, or, and implies short-circuit; other operands evaluate left to right. implies is allowed only in contracts and assertions.

Arithmetic uses the rules in section 3. Text + Text concatenates. Duration arithmetic uses checked library operations. Assignment is a statement; field assignment, increment, and compound assignment are excluded.

if and while conditions must be Bool. for iterates a snapshot List or Range and introduces an immutable item binding. range(start:, end:, step:) is half-open, requires nonzero step, and faults if step is zero; a step pointing away from the end produces an empty range. Map iteration uses map.entries explicitly.

match is a statement with block arms. Enum and Bool matches are exhaustive. Scalar matches need a final wildcard. Patterns are literals, qualified enum cases with named payload bindings, or _. Every payload field must be named or ignored. Duplicate unreachable arms are rejected. Nested destructuring and guards are deferred.

break and continue affect the nearest loop. Branches and loop iterations introduce scopes. if and match are statements in this edition; expression-valued forms are a separate syntax experiment, not required for callable composition.

Control heads use a block-delimited expression mode. A bare outer record constructor must be parenthesized before the following body brace. Parentheses, arguments, and list literals restore ordinary expression parsing. Thus match status { ... } differs syntactically from match (StatusRecord { ... }) { ... }, without consulting the symbol table. else can follow on the same or next line.

# 6 Reusable operations and effect generics

A named operation can be used as a value. It is a reference to an already checked declaration, not generated source or a string to evaluate.

```meda
operation map<T, U, effect E>(
  items: List<T>,
  transform: operation(value: T) -> U effects [E],
) -> List<U> effects [E] {
  var output: List<U> = []
  for item in items {
    output = list.append(
      items: output,
      value: transform(value: item),
    )
  }
  return output
}
```

A callable type records a mapping from unique parameter labels to exact types, its result type, and a finite effect-set upper bound. Parameter declaration order is not part of compatibility. Actual calls remain named and arguments evaluate in written call order. Label/type/result shapes must match exactly; there is no parameter or result variance. Missing, duplicate, or renamed labels are interface errors. Declaration order may be retained for display. A reference with effect bound S may be used in a position permitting T when S is a subset of T. Calling through that position charges T, its declared bound, to the caller.

Generic type parameters and effect parameters are different kinds. An effect parameter represents a finite set, and a list such as [Files.read, E] denotes their union. Effect sets are normalized; order and duplicates have no meaning. Explicit specializations use types and effect-set arguments in the declared order, for example map::<Int, Int, []>. Partial explicit specialization is not supported.

Inference collects ordinary type equalities and effect-set inclusion constraints. It selects a unique type solution and the least admissible effect solution; unresolved type variables, ambiguous effect solutions, or variables appearing only without enough constraints require explicit specialization. A generic operation used as a value must be instantiated from an expected monomorphic callable type or explicit arguments. Values do not contain uninstantiated type/effect quantifiers.

An operation's body is checked for all substitutions satisfying its constraints. A generic wrapper cannot drop E from its own bound while invoking a callback carrying E. Completely unconstrained effect parameters require explicit instantiation; they do not silently default to empty. Public APIs expose effect parameters and any restrictions on them. The predefined constraint where effect E: Concurrent restricts E to effects admitted by structured concurrency; wrappers using that facility must preserve the constraint.

Named references may be stored in ordinary records and lists, passed, returned, or selected by control flow. They have no structural equality or wire representation. Capturing closures, partial application, and higher-rank polymorphism are excluded. When reusable work needs data, pass an explicit context parameter; section 14 uses that pattern.

The language supports reusable effectful behavior in the target edition. Pure references are only the first experimental implementation step. Neither effect polymorphism nor operation values permit source code to mint host authority.

# 7 Expected errors and exact must use rules

Expected failure uses Result<T, E>; optional data uses Option<T>. Both are ordinary immutable tagged values. There are no catchable general exceptions.

Postfix ? unwraps Ok or returns Err from the current operation. The enclosing output must be Result<U, E> with the same error type. Error conversion is explicit. The propagated return runs ordinary postconditions. ? does not apply to Option.

The initial must-use guarantee is deliberately local:

- A standalone expression statement of direct Result type is a compile error.

- discard cannot directly discard a Result.

- A Result binding that is never read produces a warning, promoted to an error by the strict lint profile.

- Explicit matching, return, or ? is supported handling. A deliberately empty error arm counts as explicit dismissal.

The checker does not prove that every Result nested in an aliased or generic container was inspected. Passing List<Result<...>> to list.length is legal and does not establish error handling. Assignment may overwrite a Result binding; linting can diagnose suspicious overwrites without claiming a complete obligation analysis. Equality or forwarding may count as a read while leaving an application bug. These are explicit limits of the guarantee.

Use reusable error conversion rather than repeated incidental matching:

```text
results.mapError<T, E, F>(
  value: Result<T, E>,
  convert: operation(error: E) -> F effects [],
) -> Result<T, F> effects []
```

Type/effect checks reject invalid programs before application execution. Runtime faults include violated contracts, failed assertions, invalid faulting arithmetic, root resource exhaustion, and failures of the runtime itself. Outside the explicitly isolated validator boundary in section 8, a fault terminates the run, requests sibling cancellation, performs owned local cleanup, and reports a source stack. Postconditions do not roll back earlier effects.

An expected local model or I/O failure is a typed error. Root memory, root evaluator fuel, root deadline, and root cancellation cannot be converted to a successful value or swallowed by a validator. Section 15 defines the boundary explicitly.

# 8 Contracts and reusable validation

require runs after argument evaluation and before the body. ensure runs on every normal return, including a propagated Err. Parameters retain their entry values; result denotes the returned value. Clauses run in declaration order. Contracts remain active in release execution.

A contract is a Bool expression. It may call named user operations that the compiler establishes are contract-safe. Eligibility is derived from the checked body and reachable helpers; no author annotation can waive the rules.

A contract-safe operation must be pure, use an acyclic direct call graph including implicit require/ensure evaluation, and contain no while, recursion, indirect callable invocation, model call, parallel scope, or external effect. It may use immutable values, local reassignment, if/match, finite List/Range loops, and approved metered pure intrinsics. Calls to other eligible named helpers are allowed. This is a bounded executable subset, not a proof system. A helper whose own postcondition calls itself is ineligible even when its body is nonrecursive.

Eligible helpers may return any ordinary supported data, including Bool or a list of validation issues. The same helper can therefore participate in an ensure expression and a model validator. A helper whose body changes to violate eligibility is rejected wherever contract-safe use is required; the compiler reports the dependent contract.

A finite loop can still exceed fuel, and arithmetic can still fault. A false ordinary contract is ContractViolation. Failure to evaluate it is ContractEvaluationFault. Both terminate an ordinary run; neither is reported as a successful check. Contract evaluation has a local allowance charged against root resources.

Model validators use the same eligibility checker. Their fixed interface is value: T, context: I -> List<Text> with effects [], where I is the generation input type. Empty means acceptance; nonempty means rejection. Local validation faults or local validator fuel exhaustion become typed model validation errors. Root exhaustion still aborts the run.

Examples for pure comparable outputs are attached tests, never automatic prompt examples. assert is available in bodies/tests and faults if false. Tests, executed contracts, checked types/effects, model evaluations, and formal proofs have separate statuses. Edition 1 never reports proved.

Each test runs as an isolated implicit root with finite configured limits and fresh fake state. Assertion failure, numeric/contract fault, resource exhaustion, missing fake, invalid fake response, and infrastructure failure are distinct outcomes; a failed test does not prevent later tests from running. There is no live fallback. Ordinary Result.Err is data and must be asserted or matched, not automatically classified as test failure. Test blocks have implicit Unit output and may return unit; ? is invalid there because the enclosing output is not Result. Required checks pin the nonempty test ID set, fixture digests, compiler/profile identity, and runner definition. Empty or mismatched discovery fails validation. Gate B initially permits only pure tests; effectful fake tests enter with their runtime.

Contracts express required relationships for valid callers. Ordinary malformed user input should usually return a typed error. Opaque constructors preserve validated states after checks; contracts remain useful for relationships between inputs, outputs, and collections.

# 9 Effects authority and trusted adapters

Effects are interface bounds. At every call, the caller is charged the callee's declared bound, including instantiated callback bounds, even if the current callee body is purer. Inferred body effects verify the declaration and may suggest narrowing it; they do not secretly weaken the public interface.

Built-in effects are Console.write, Files.read, Files.write, Net.request, Clock.read, Random.read, Env.read, and Model.call. Model adapter transport belongs to Model.call and grants no arbitrary network API. Runtime bookkeeping does not expose clock/random facts through pure computations.

A trusted host registry may define additional effect identities for audited adapters, such as Experiments.read. Each identity has a versioned declaration and a classification used by tool and concurrency checks. A claimed read classification covers the semantic API operation, not merely an HTTP method. Auditing and conformance remain obligations of the trusted host.

Source imports generated bindings from the reserved host namespace. A binding defines an operation's exact types, effect bound, semantic read/write classification, limits, cancellation, serialization, and trace identity. The checker resolves it against a pinned registry manifest. Source cannot register native code, forge host modules, or relabel a write as a read. Type names in the manifest resolve to actual public declaration identities in the checked program.

The host grants allowed resources and destinations. Checks occur on every host access, including resolved file paths/symlinks, redirected network origins, and domain resource identifiers. Unsupported enforcement fails closed. The effect checker is not an operating-system sandbox; untrusted source and adapters need an appropriate host execution boundary.

Credentials remain opaque authentication references used only by their owning adapters. Application code cannot print or serialize them. Ordinary files and non-secret environment text can still contain sensitive data; opacity of credential handles does not provide general information-flow protection.

Registry bindings can use existing host SDKs without exposing arbitrary FFI to Meda code. The target includes a Rust host interface and one generated TypeScript or Python client. Host code outside the Meda boundary does not inherit Meda's guarantees.

# 10 Modules packages and entry points

Each .meda file declares a module matching its path beneath src. import qualified.name as alias imports an explicit namespace. Imports are private to the file and never execute application code. Wildcard imports and implicit re-exports are excluded.

Resolution is explicit: self.modulePath selects the current package, deps.alias.modulePath selects a declared dependency, and std/host select pinned reserved roots. Existing unqualified module paths resolve only within the current package; they never search dependencies. The qualifier self in expression position selects the current module. Dependency aliases must be unique and cannot use reserved roots. Nominal identity is the tuple of resolved package-instance identity, module path, and declaration identity. A lockfile package node includes canonical source identity, content digest, edition, and its resolved dependency graph; repeated aliases of the same node unify, distinct nodes do not. Locked graph resolution is deterministic and cannot depend on directory enumeration order. Changing a resolved node invalidates affected type/check receipts. Source packages cannot provide std or host. Gate B's single-file profile has no dependency resolver and must reject imports outside its explicit pure intrinsic allowlist.

Declarations are private unless public. Public interfaces may use public ordinary or public opaque types, never private types. Operation/type names share a declaration namespace. Module import cycles are rejected with the cycle; direct and mutual operation recursion within a module remain allowed.

The manifest records package name, version, edition, optional entry, and explicit local dependencies. meda.lock pins dependency content, compiler/standard-library compatibility, and host registry identities. Resolved runtime/model configuration is a separately immutable run snapshot. No run silently upgrades dependencies or providers.

```toml
[package]
name = "experiment-report"
version = "0.1.0"
edition = 1
entry = "app.main"

[dependencies]
# Explicit local packages during Edition 1.
```

The executable entry is a public operation with exactly args: List<Text> and output Result<Unit, AppError>. Args exclude the executable name. AppError is a prelude record with code: Text and message: Text. Library packages have no entry.

Success maps to process status 0; an application Err to 1; compilation or pre-run configuration failure to 2; runtime fault to 3. External host termination is distinguished in trace metadata. Test/check commands use documented nonzero statuses for failed checks and infrastructure failures.

The initial distribution has local packages and a bundled standard library. A public registry, cross-edition linking, native executable distribution, and package signing need later designs.

# 11 Typed model generation and shared policy

generate<T> evaluates to Result<Generated<T>, ModelError>. It contributes Model.call and the declared effects of its permitted tools. It is the single model intrinsic; ordinary operations provide names, reuse, and composition.

```meda
record Summary {
  title: Text,
  points: List<Text>,
}

let brief: GenerationPolicy = GenerationPolicy {
  timeout: 15s,
  maxOutputTokens: 800,
  maxAttemptsPerStep: 1,
  maxModelCalls: 1,
  maxToolRequests: 0,
  maxValidationSteps: 20000,
}

operation summarize(document: Text, policyValue: GenerationPolicy)
  -> Result<Generated<Summary>, ModelError> effects [Model.call] {
  return generate<Summary> {
    model "summarizer"
    instruction "Summarize the main claims in the supplied document."
    input document
    policy policyValue
  }
}
```

Generation clauses appear once in this order: model, instruction, input, policy, optional tools, optional validate. Model is a compile-time alias string. Instruction is compile-time Text. Input is an ordinary ModelData expression. Policy is a GenerationPolicy value, so applications can share, pass, and explicitly revise execution limits. Tools and validators resolve statically to checked declarations.

GenerationPolicy is a prelude record with exactly the six fields above. Timeout is Duration; all counters are Int. All fields except maxToolRequests must be positive; maxToolRequests may be zero. Invalid values produce InvalidPolicy before dispatch. Source policy cannot exceed host policy ceilings or broaden grants. Exceeding a ceiling is PolicyDenied; exhausting the currently available shared allowance is BudgetDenied. Neither case waits indefinitely for another call to release budget.

A model alias resolves through an immutable run configuration containing adapter/version, model selector, parameters, credential reference, and enforcement profile. Changing a model can change quality and latency even with the same source; configuration identity and affected evaluation results must make that visible. Credentials are never source values.

Input evaluation and policy evaluation happen once in source order and produce immutable snapshots. The runtime has no ambient chat history and adds no source files or local variables automatically. Instructions, serialized inputs, and tool outputs remain separate request components. This separation is inspectable but does not prove resistance to prompt injection.

The runtime validates the binding, type/schema, tool descriptors, validator eligibility, policy, and grants before an outbound request. After completion it decodes exactly, checks the full local schema, then invokes the optional validator. Only a candidate that passes all checks can become Generated<T>.

Generated<T> is a standard-library opaque value. Public pure observers are model.value(generated:) -> T and model.info(generated:) -> GenerationInfo. Application code cannot construct it, update its representation, or automatically serialize it. Explicit extraction does not implement whole-program taint tracking.

GenerationInfo contains origin identity, current invocation identity, adapter/model identity, request/schema/validator/tool digests, original completion status, usage when known, current dispatch/tool counters, latency observations, and a cache/replay marker. Origin and current-invocation fields are separate so a cache hit never pretends it made the original provider calls. Unknown values use Option rather than zero. No hidden chain-of-thought or invented confidence is recorded.

ModelError contains kind, sanitized message, traceId, attempts, modelCalls, toolRequests, toolExecutions, retryable, and remoteOutcome. Error kinds distinguish invalid policy, denied policy, unsupported capability, denied authority, provider failure, rate limit, timeout, refusal, truncation, schema failure, validator rejection, validator fault, budget denial, and invalid tool request. Sanitized message means a runtime-owned stable code/template, never unreviewed provider or application text. Validator issue strings, provider errors, rejected-value excerpts, malformed arguments, and raw wire bytes are content; they require the authorized content channel. Metadata-only persistence and default runtime diagnostics exclude them. Explicit application output remains governed by application authority.

remoteOutcome summarizes all attempts: NotStarted if none dispatched; Completed if all dispatched attempts have known terminal outcomes; Unknown if any dispatched attempt remains unresolved. Each attempt retains its own outcome in the trace. The aggregate does not mean the application succeeded or that tools were rolled back.

No implicit repair or semantic retry occurs after refusal, truncation, schema rejection, or validator rejection. Before any tool execution starts, a specifically classified retryable transport/rate-limit failure may retry the same immutable request. Each retry reserves new resources and consumes the per-step and generation-wide counters. After any tool execution starts, automatic request retries and generation restarts are disabled. Applications can make another explicit generation under a declared policy.

After input and policy expressions finish and a valid policy snapshot is available, generation starts its monotonic deadline. Binding resolution, cache lookup, request preparation, dispatches, waits, tools, decoding, validation, and publication all occur within it. Input/policy evaluation remains subject to ordinary root limits. The generation deadline bounds local waiting; it cannot guarantee remote cancellation or final billing. Late responses may add diagnostic observations but cannot publish another terminal result. There is no exactly-once request or unconditional currency-budget guarantee.

# 12 Data formats and provider schema projection

Serializable values use a typed JSON profile. Canonical hashes use RFC 8785-compatible property ordering, escaping, and finite-number formatting, with the schema identity included. Provider wire bytes are recorded separately when formatting differs. Decoders reject duplicate keys, invalid Unicode, unknown fields, missing fields, and noncanonical typed integer strings.

| Value | Typed wire form |
| --- | --- |
| Bool and Text | JSON boolean and string. |
| Finite Float | JSON number; non-finite results are rejected. |
| Int I64 and U64 | Canonical decimal strings, parsed without a JavaScript numeric conversion. |
| Char | String containing exactly one Unicode scalar. |
| List | Ordered JSON array. |
| Ordinary record | Object containing every declared field. |
| Enum | Object with $case and every named payload field. |
| Option and Result | Tagged enums with explicit None/Some or Ok/Err cases. |
| Map | Object with $map containing ordered key/value entries. |
| Bytes | Object with $bytes containing padded base64. |
| Duration | Object with $nanoseconds containing a canonical integer string. |
| Unit | Object with $case equal to Unit. |

The dollar-prefixed fields cannot collide with legal source field names. Canonical decimal integers use 0 or an optional minus followed by a nonzero digit and remaining digits; no plus, leading zeros, or negative zero is accepted. Bounded integer range checks remain local and exact.

ModelData is a strict subset: Bool, Text, finite Float, decimal-string integer types, Char, lists, ordinary records, enums, Option, and Result. It excludes maps, bytes, durations, Unit, recursive schemas, callable values, opaque records, secrets, capabilities, and Generated wrappers. Schema/value depth is at most 32; host byte/item limits apply separately. Opaque exclusion is transitive through containers and enclosing records.

General JSON interop uses an explicit Json tree. Its numeric token preserves exact decimal spelling until an explicit conversion to Int, Float, or another supported destination succeeds or returns an error. External service JSON need not use Meda's tagged wire profile; an adapter maps and validates it at the boundary.

Public visibility does not imply wire exportability. Ordinary public Meda operations may accept opaque values or callbacks. Schema generation is required only for actual serialized, host, or model boundaries, where the relevant capabilities must hold. A client generator reports non-exportable operations instead of weakening their types.

Each generation has two schema artifacts: the authoritative full local acceptance schema and the provider-compatible generation schema. Draft 2 explicitly permits projected enforcement under a host-selected profile. The projection may omit only documented length/cardinality, numeric-range, and pattern/format constraints that the local checker fully enforces. It records every omission. JSON primitive kinds, object fields, required fields, unknown-field rejection, and enum discrimination must remain supported provider capabilities; there is no silent fallback to unconstrained text or an arbitrary JSON blob.

An exact enforcement profile forbids any projection omission and rejects unsupported schemas before dispatch. Projected enforcement can increase the chance of a local rejection; it does not broaden the set of accepted Meda values. Provider claims never replace local validation. An invalid provider response remains a typed schema failure even when the provider advertised strictness.

The same exact local checks apply to model-generated tool arguments and trusted host results crossing into Meda. A malformed adapter result is a host contract violation, never a successfully typed application value. Adapter conformance includes all supported primitive, enum, bound, and projection cases.

# 13 Tools and invocation authority

A tool declaration derives a descriptor from an ordinary monomorphic operation.

```meda
/// Fetch an experiment by an identifier within the current team scope.
tool findExperiment {
  target experiments.find
  description "Look up an experiment by its exact identifier."
}
```

A generation opts into a static list with tools [findExperiment]. The operation's parameter labels and types define the argument object; its result defines the response. Both must be ModelData. A Result response carries domain failure as ordinary data. Generic targets must be concretely instantiated in a named wrapper before becoming tools.

Targets may be pure or use Files.read, Clock.read, Env.read, and trusted registered semantic-read effects. They cannot transitively use writes, generic Net.request, Random.read, or Model.call. No nested model tools or hidden generation recursion is allowed. A tool may internally use bounded concurrency only when its callback effects satisfy the same Concurrent restrictions and all child calls inherit its restricted authority and ledger. The outer tool invocation joins that work before the next tool request starts. Internal host calls retain their own host-call/time/size limits; tool-request counts describe model-requested invocations. Ordinary application code can still perform separately authorized writes.

The effective tool set is the intersection of source declarations and host authorization for the model invocation. Before generation, the trusted host binds each tool to an immutable context: resource roots or allowed IDs, tenant/account where relevant, readable environment names, approved typed result wrapper, and model destination policy. This context is separate from model-generated arguments.

Output minimization is implemented by an explicit checked target wrapper with its own narrow result type. The effective tool schema is derived from that wrapper, and the host pins its checked-build digest plus resolved symbol identity. Edition 1 does not silently drop fields from a broader tool result. A binding that requests a projection incompatible with its target/result schema is rejected before dispatch. The wrapper runs and its output is validated before any tool data reaches the provider. Changing a transitive wrapper helper invalidates an authorization pinned only to the old build, even when schema and symbol names remain unchanged. Host policy can authorize the new build without mandatory human reapproval.

Every transitive host call during tool execution uses the intersection of run authority, enclosing invocation authority, and the tool binding. A named operation reference carries no captured authority; invoking one inside a restricted tool cannot recover the broader authority of its declaration or original caller. Source may request a narrower binding but cannot issue a broader one.

Read-only means a restriction on external mutation. It does not establish confidentiality. Tool scopes prevent access to unrelated resources; authorized ordinary application code may still copy private text into a model input. Stronger information-flow guarantees are outside Edition 1.

Before processing each model-requested invocation, the runtime atomically debits one available generation and root tool-request allowance. If either is unavailable, generation terminates with BudgetDenied without validating or executing that invocation. Successfully debited requests count in toolRequests, including malformed, unknown, or denied ones. Unprocessed requests after termination consume no allowance; received-request telemetry is separate. A separate counter records executions actually begun. Requests execute sequentially in provider-listed order. Before each execution, the runtime validates the descriptor, authorization, input, remaining deadline, and resource allowance. Output is bounded during production and validated before delivery to the model.

Unknown names, malformed arguments, and denied access terminate generation with a typed model error. A legitimate domain Err is delivered to the model as data. Ordinary programming faults in tool code and violations by trusted adapters are run-fatal; the validator's special isolation rule does not extend to arbitrary tools.

Model text and tool results cannot add tools, change grants, or register code. Proposed external writes leave the model loop and enter ordinary checked application logic. Whether a particular write needs human approval is application policy. If that policy is represented by an opaque receipt, its issuing module or trusted host must bind it to the relevant payload and authority; a suggestively named public record is insufficient.

# 14 Structured bounded concurrency

Edition 1 provides a standard intrinsic, tasks.mapBounded, for runtime-sized batches:

```text
tasks.mapBounded<T, C, U, effect E>(
  items: List<T>,
  context: C,
  work: operation(item: T, context: C) -> U effects [E],
  limit: Int,
) -> List<U> effects [E]
  where effect E: Concurrent
```

The signature above specifies the intrinsic's type; source declarations put their where constraints in the grammar-defined declaration header. work is a monomorphic operation reference. Items and context are immutable snapshots taken at entry. The result order matches input order, independent of completion order.

limit must be positive; an invalid value is a precondition fault before any callback starts. Empty input returns an empty list and calls nothing. Each map permits at most limit started-but-unfinished callbacks of its own. A root scheduler separately limits runnable evaluator workers, and host-request concurrency has its own permits. Lower host capacity reduces achieved concurrency without changing result order.

Concurrent effects are pure computation, Files.read, Clock.read, Env.read, Model.call, and registered semantic-read effects marked concurrency-safe by the trusted manifest. Console.write, Files.write, Net.request, Random.read, and write-classified adapters are rejected. A generic wrapper must preserve the Concurrent effect constraint. There is no promise that reads or model calls complete in a particular external order.

If U is Result<T, E>, an item Err is data and does not cancel siblings. Any run-fatal callback fault, root cancellation, or root exhaustion stops new callbacks, requests cancellation of active siblings, and joins owned local cleanup. Dispatched remote work may continue; unknown outcomes remain recorded. No callback task escapes the map scope.

Nested maps are allowed. A suspended parent remains an unfinished callback in its enclosing map but releases runnable-worker capacity while waiting for children. It cannot monopolize the runnable permits its children need. Host-request permits remain held for each request's locally active lifetime; suspension alone does not release an in-flight request permit. Locally abandoned requests may still run remotely and retain unknown-outcome accounting. Root scope-count and memory quotas bound suspended work. Global host-request limits apply across all nested maps. Admission fairness and queue order are recorded scheduler behavior, not inferred from returned list order.

Bounded activity does not imply constant memory: List<U> retains N results. The runtime checks an item cap before launching work, enforces aggregate retained-result/allocation quotas, and may fault on root memory exhaustion. Partial completion is visible in the trace; it is not returned as a successful full list.

Each callback identity is derived from the map invocation and input index, including nested scope paths. Scheduler admission, failures, and cancellations use those identities for tracing and replay. Public async handles, detached tasks, streams, and persistence across process failure remain excluded.

# 15 Resource accounting and execution outcomes

Each run has a host-owned atomic ledger. Before execution, the profile resolves finite limits for root wall time, evaluator fuel, allocation/memory containment, recursion depth, scope count, input/output sizes, item/schema sizes, host calls, model calls, output-token reservations, tool requests, and concurrency. Missing limits never mean unlimited.

There are separate resource domains:

| Boundary | Outcome while root is live |
| --- | --- |
| Invalid source policy | Typed InvalidPolicy before dispatch. |
| Requested ceiling exceeds host policy | Typed PolicyDenied. |
| Current model/tool allowance cannot admit a request | Typed BudgetDenied; no indefinite admission wait. |
| Generation-local deadline | Typed Timeout; unresolved dispatched attempts remain Unknown. |
| Validator-local fuel or pure evaluation fault | Typed ValidatorFault or validation-budget failure. |
| Expected file/network/service failure | The operation's declared Result error. |
| Root memory fuel deadline cancellation or runtime integrity failure | Fatal run outcome; sibling cancellation and cleanup. |

Root failure always takes precedence over a local recoverable outcome. Final generation publication atomically checks that both the generation and root remain live. A late response cannot turn a terminated run into success. Validator isolation catches only its documented local pure failures and never a root signal.

Each generation owns its tool evaluators, nested maps, and local host waits in a cancellation scope. Deadline expiry atomically closes admission and signals that scope. Pure evaluators stop at metered checkpoints; adapter waits retire through bounded abandonment. Before returning Timeout, generation joins all owned local work and bounded cleanup under the same restricted authority. The deadline starts cancellation; cleanup can extend return latency by a host-configured finite allowance. If local containment cannot be established within that allowance, terminate the isolated worker and report fatal CleanupFailure; do not return recoverable Timeout with live local work. Dispatched remote work can remain Unknown and charged, but late responses cannot resume source execution or publish success. Terminal events use one recorded monotonic ordering: a genuine tool fault admitted before cancellation is root-fatal; after cancellation, abandoned continuations do not execute. Root/runtime integrity failure always takes precedence.

Before dispatch, the adapter must establish that the provider supports and applies the requested output ceiling under its declared accounting semantics; otherwise generation fails with UnsupportedCapability. A demonstrated ceiling violation is an adapter/provider conformance failure and is never treated as compliant accounting. Usage reconciliation cannot silently clamp an over-limit report or refund an invalid report; unusable or absent usage retains the conservative reservation.

For each provider request, reserve one call slot and the maximum per-request output allowance together before the adapter can send bytes. The dispatch transition becomes charged before transmission. Proven non-dispatch may release its reservation; a dispatched request still counts as a call even if the provider rejects it. Trustworthy usage can reconcile output allowance. Ambiguous or absent usage retains the conservative reservation. Every retry gets a new reservation.

Token accounting follows the adapter's declared semantics, including how reasoning or tool-call tokens count where relevant. Totals across adapters are host resource policy, not a unit of currency. Input bytes/tokens and cumulative tool conversation sizes have independent bounds.

The generation state machine is: prepare, admit, dispatch, receive, optionally validate/run/deliver tool requests and begin another model step, decode, validate, publish. Any eligible transition may terminate with a typed local error or fatal root outcome. A terminal result is published at most once. Per-step attempts reset only when a new model step begins; total model calls never reset within a generation.

Metering must cover variable-cost work. Big-integer arithmetic charges by operand-size-sensitive rules; text/collection operations, equality, parsing, schema expansion, canonicalization, and serialization charge examined or produced data. Allocation is reserved before creation. Standard-library and adapter calls cannot become unmetered islands.

The implementation may use conservative costs and size ceilings, but must publish their version and distinguish logical allocation quota from process memory containment. Structural sharing must not allow arbitrary live data to evade the chosen accounting model. Native operations that cannot be interrupted need bounded input/expansion limits or process isolation; checking a deadline after unbounded work returns is insufficient.

Compilation and schema generation have their own limits when accepting untrusted source. Root wall-time cancellation is observed at metered checkpoints; native boundary cancellation uses adapter-specific mechanisms. These rules bound local execution under the declared host assumptions, not remote provider work or the operating system's scheduling latency.

# 16 Traces replay and caches

A trace identifies the checked build, runtime, scheduler, standard library, adapters, host registry, and resolved configuration/policy. Events identify the run, scope path, operation invocation, branch/index, call occurrence, attempt, and transition. Source spans and symbol revisions supplement these identities; they do not replace occurrence identity.

Metadata events include host requests/completions, budget admission and reconciliation, scheduler admission, tool requests/executions, validation, cancellation, and terminal outcomes. Application-visible timing and GenerationInfo fields are observations that replay must reproduce. Provider IDs are recorded when supplied; exact backend model identity is not invented.

The runtime journals nondeterministic boundary decisions in a total observation order. It need not log every evaluator step. Exceptional root cancellation or deadline delivery during pure computation records the stable metered checkpoint/evaluation counter where it was observed. Trace ordering includes decisions that determine which branch receives a shared allowance.

Strict replay uses the recorded decisions and outcomes rather than racing real deadlines or readiness again. It runs only with a compatible exact checked-build/runtime/scheduler fingerprint initially. Replay drives the designated scope to the next recorded transition, delivers the recorded observation, and fails if that transition cannot occur. Pure evaluation remains deterministic under the pinned runtime/standard-library environment.

Every external effect, including writes, is intercepted. Replay compares the requested operation, input identity, and scope with the fixture and supplies its recorded outcome. It never writes application files, sends messages, contacts a provider, or falls through to a live adapter. Its own private diagnostics/output artifacts are separately identified host tooling actions.

A replayable trace requires all necessary content and a terminal completeness marker. Missing, redacted, incompatible, or unmatched observations fail explicitly. A metadata-only trace is useful for diagnostics but cannot reconstruct a full execution. Host access to a trace is checked independently from the historical authority recorded inside it.

Content recording is opt-in. Structural redaction covers prompts, inputs, outputs, and tool arguments/results. Low-entropy hashes can expose information through guessing; keyed or omitted digests are host policy. Raw hidden model reasoning is not collected.

Caching is opt-in. Edition 1 permits generation caching only when no tools are enabled. Its identity includes the checked-build digest, transitive validator/constants/schema identity, model/adapter parameters, normalized input, instruction, projection profile, security partition, and freshness policy. A conservative whole-build identity is preferred over incomplete dependency hashing.

A cache hit uses the same current-authority checks, full local acceptance contract, validator budget, generation deadline, and atomic root-live publication rule as a live result. It reserves no provider-call or provider-output allowance. An authorized valid hit can therefore succeed with no provider calls remaining; a miss requiring dispatch returns BudgetDenied when admission is unavailable. It preserves original provenance while reporting zero new provider dispatches for the hit. Current policy cannot be bypassed through cached data. Cross-principal reuse requires an explicit host policy; the initial CLI uses a private store.

Caches for external tool observations, cross-version replay, durable workflow recovery, and semantic replay across modified source are later features. A live rerun can differ from replay even with identical source and a pinned provider selector.

# 17 Runtime configuration and standard interfaces

meda.runtime.toml is host-selected configuration, separate from the source manifest. It defines model aliases, provider-enforcement profiles, host bindings, run grants, tool bindings, finite resource ceilings, recording, private storage, and cache policy. Application code cannot broaden or replace it mid-run.

Profiles are versioned structured data. Unknown fields and absent required bounds are rejected. Starter profiles may supply explicit documented defaults. Source and host bindings are checked against the chosen snapshot before application effects; provider-specific request failures may still occur later.

The standard library includes list, map, text, int, float, time, json, files, net, console, results, model, tasks, and test namespaces. Core scalar types, List/Map/Option/Result, GenerationPolicy, model errors/wrappers, range, and AppError form the prelude. Other operations require explicit imports.

Representative normative signatures include:

```text
list.append<T>(items: List<T>, value: T) -> List<T> effects []
list.get<T>(items: List<T>, index: Int) -> Option<T> effects []
list.length<T>(items: List<T>) -> Int effects []
text.length(value: Text) -> Int effects []
text.utf8(value: Text) -> Bytes effects []
model.value<T>(generated: Generated<T>) -> T effects []
model.info<T>(generated: Generated<T>) -> GenerationInfo effects []
console.write(text: Text) -> Unit effects [Console.write]
console.tryWrite(text: Text) -> Result<Unit, ConsoleError>
  effects [Console.write]
```

List lookup returns None for any invalid index. Text length counts Unicode scalars. Append/update operations return new logical values. Console.write emits a line and faults if its sink fails; tryWrite supports expected error handling. Terminal rendering escapes unsafe controls by default, while machine/pipe encodings have an explicit exact-byte contract. No implicit record-to-text conversion is provided.

All implemented standard operations have machine-readable definitions of labels, types, effects, capabilities, contract eligibility, resource charges, and host behavior. Configuration, errors, diagnostics, and edit messages use versioned schemas generated from shared declarations where possible. The prototype needs only schemas for its implemented subset; a release cannot leave its public interfaces as prose categories.

Serialized host exports require Serializable types; model/tool exports require ModelData. Export selection is explicit. Opaque values and callbacks remain fully valid within Meda without implying a JSON client representation. A generated client validates returned envelopes and exposes exact error variants. It cannot reconstruct a language capability or opaque proof of validation.

Whole-file I/O and request/response adapters own their resources. User-held open handles and arbitrary shell/native calls are excluded. The host bounds transport sizes, redirects, timeouts, and shutdown cleanup. A process or machine failure may lose final trace delivery; in-memory scopes do not imply durability.

# 18 Compiler context and guarded editing

The compiler exposes a versioned local JSON API. Source remains authoritative; the checked representation contains resolved symbols, instantiated types/effects, predicate eligibility, schema identities, and dependency information.

The initial API includes describe, begin_edit, replace_body, validate_edit, commit_edit, and transaction_status. Describe returns the target interface, contracts, source, direct dependency interfaces, associated tests, revision, and bounded continuation tokens. A later references API and rename/interface operations extend the same model.

Every transaction binds to a trusted EditGrant issued outside the editing agent:

```text
EditGrant {
  grantId,
  workspaceId,
  baseRevision,
  allowedTargets: [{ symbolId, editKinds }],
  protectedArtifacts: [{ path, contentDigest }],
  requiredChecks: [{ checkId, definitionDigest }],
  expiresAt: Option<Timestamp>,
}
```

Grant issuance is host policy. Existing user authorization can supply it; the protocol does not require repeated human confirmation. An agent may request a different scope but cannot issue or mutate its own grant.

begin_edit resolves the grant and exact revision. replace_body stages only the selected body and preserves signature, effects, contracts, attached examples, and documentation. Other edit classes require their own grant permission. A semantic scope check rejects changes disguised inside a body payload.

validate_edit parses, resolves, checks types/effects/contracts, formats, runs grant-required deterministic checks, and may run additional requested checks. Its receipt binds the staged snapshot, protected artifacts, check definitions, and outcomes. Agent-selected tests cannot replace required acceptance checks. Changes to public interfaces, schemas, contracts, protected acceptance tests, or acceptance criteria are reported as specification changes. A body replacement is implementation-only only when it does not change a protected specification dependency. Those implementation changes are reported separately, including their validation outcomes. Classification does not itself grant or revoke edit permission.

For every protected contract/check root, the checker derives a specification dependency closure over executable helper bodies, implicit contracts, referenced constants, relevant nominal/schema definitions, and pinned intrinsics/compiler identity. Compare both base and staged graphs, including added or removed edges. Changes anywhere in either closure are specification-affecting. Report affected root IDs and dependency paths. An implementation-only grant rejects them; an externally issued grant authorizing the relevant specification roots may permit them while retaining required acceptance checks. Eligibility alone is insufficient: a pure, eligible helper can weaken a predicate. Initial conservative whole-definition or whole-file pinning is permitted if its collateral restrictions are reported. Required tests protect their definitions and fixtures; ordinary calls into the implementation under test do not freeze that implementation. Explicit assertion/oracle helper roots are protected transitively; the distinction between the subject and its oracle is host-owned, not agent-selected.

commit_edit verifies the grant is still valid, the expected workspace revision matches, the staged snapshot matches the successful validation receipt, and required artifacts/checks remain protected. Publication cannot race a late edit to the validated content. An uncertain response is reconciled through transaction_status, never by blindly replaying writes.

The prototype publishes a single-file staged change through atomic replacement. The full protocol uses a workspace lock, staged files, and recovery metadata to give atomicity to protocol clients across multiple files. External filesystem observers may see materialization unless isolated; source-authoritative storage does not promise universal filesystem transactions.

Exact workspace guards deliberately reject unrelated concurrent changes initially. Read-set rebasing, persistent cross-revision node identity, subtree mutations, and editor-only typed holes are deferred until measurements justify them. A read-only expected-type/effect/local-scope query can be added without changing language execution.

A mediated API can preserve edit scope without controlling all filesystem access. A deployment claiming enforcement against an agent with other write routes must protect publication and compare all changes to the grant. That is a host boundary, not a language proof. Comments and repository text are untrusted content, distinct from trusted compiler facts.

Diagnostics carry a stable code, severity, source URI and byte span, editor-coordinate translation, symbol/revision, explanation, related spans, and optional guarded suggestions. Suggestions that widen authority or change a contract are not labeled semantics-preserving. Structured and human output represent the same facts.

# 19 Compiler runtime and toolchain architecture

The reference implementation uses Rust, a lossless syntax tree, a checked semantic representation, and an interpreter. Declaration/statement parsing uses recursive descent; expression parsing uses precedence rules. Optimization and native code generation are deferred.

Resolution gathers signatures before bodies, checks public visibility, resolves host bindings, and instantiates rank-1 generics. Type checking includes callable labels and effect widening, opaque construction, enum exhaustiveness, and wire-boundary eligibility. Effect checking uses interface bounds and generic constraints. Contract eligibility is a conservative whole-call-graph property of the instantiated helpers.

The checked representation is shared by execution, diagnostics, schema emission, context retrieval, and edits. Formatting preserves comments and literal spelling where required by the canonical rules; generated schemas and host clients are not separately hand-maintained definitions.

Runtime components are the metered evaluator, structured scheduler, atomic ledger, scoped host dispatcher, provider adapter interface, validator boundary, and trace/replay engine. Adapter SDK retries are disabled or explicitly controlled by the ledger. A missing provider feature never silently selects another provider.

| Command | Behavior |
| --- | --- |
| meda init | Create a package and explicit host-profile template. |
| meda fmt | Canonicalize valid source; --check only reports differences. |
| meda check | Check source and local schemas with no application/model effects. |
| meda check --profile NAME | Also check pinned bindings, policy, grants, and declared adapter capabilities locally. |
| meda run --profile NAME | Execute the entry under finite limits. |
| meda test | Run examples/tests with fake host effects and no implicit live fallback. |
| meda eval --suite NAME | Run an explicitly budgeted live-model evaluation. |
| meda describe SYMBOL --format json | Return bounded resolved context. |
| meda edit --protocol json | Serve grant-bound staged changes. |
| meda replay TRACE | Replay a complete compatible recording with real effects disabled. |

The minimum interpreter/checker and edit loop arrive before a provider adapter. Separate packages may implement syntax, checking, runtime, host, CLI, and shared interface declarations, but package boundaries should follow tested responsibilities rather than become a release prerequisite.

# 20 Complete batch reporting component

This is a complete two-module library component for the proposed language. Its public entry accepts a runtime-sized list from a host client or Meda caller. A host profile binds the reporter model alias, grants Model.call, and supplies finite run limits. The library manifest has no executable entry.

The component computes health findings, supplies notes for evidence synthesis, validates output references, and retains one result per input. A model must distinguish supported, conflicting, and insufficient evidence. The checks below establish identifiers, reference membership, and basic report structure; they do not establish sentence-level faithfulness.

File src/domain.meda:

```meda
module domain

import std.list as list
import std.text as text

public record Note {
  sourceId: Text,
  text: Text,
}

public record ExperimentInput {
  id: Text,
  ageDays: Int,
  owner: Option<Text>,
  notes: List<Note>,
}

public enum Finding {
  Stale { days: Int },
  MissingOwner,
}

public record FactsData {
  experimentId: Text,
  findings: List<Finding>,
  notes: List<Note>,
}

public opaque record Facts {
  data: FactsData,
}

public record InputError {
  message: Text,
}

public enum EvidenceState {
  Supported,
  Conflicting,
  Insufficient,
}

public record Report {
  experimentId: Text,
  state: EvidenceState,
  summary: Text,
  sourceIds: List<Text>,
}

public opaque record CheckedReport {
  data: Report,
}

public record ReportError {
  issues: List<Text>,
}

public operation prepare(input: ExperimentInput)
  -> Result<Facts, InputError> effects [] {
  if text.length(value: input.id) == 0 or input.ageDays < 0 {
    return Result.Err(error: InputError {
      message: "Invalid identifier or age",
    })
  }

  var seen: List<Text> = []
  for note in input.notes {
    if text.length(value: note.sourceId) == 0 or (
      list.contains(items: seen, value: note.sourceId)
    ) {
      return Result.Err(error: InputError {
        message: "Evidence identifiers must be nonempty and unique",
      })
    }
    seen = list.append(items: seen, value: note.sourceId)
  }

  var findings: List<Finding> = []
  if input.ageDays > 30 {
    findings = list.append(
      items: findings,
      value: Finding.Stale(days: input.ageDays),
    )
  }
  match input.owner {
    Option.None => {
      findings = list.append(
        items: findings,
        value: Finding.MissingOwner,
      )
    }
    Option.Some(value: _) => {
    }
  }

  return Result.Ok(value: Facts {
    data: FactsData {
      experimentId: input.id,
      findings: findings,
      notes: input.notes,
    },
  })
}

public operation exportFacts(value: Facts) -> FactsData effects [] {
  return value.data
}

operation hasSource(id: Text, notes: List<Note>) -> Bool effects [] {
  for note in notes {
    if note.sourceId == id {
      return true
    }
  }
  return false
}

public operation reportIssues(value: Report, context: FactsData)
  -> List<Text> effects [] {
  var issues: List<Text> = []

  if value.experimentId != context.experimentId {
    issues = list.append(
      items: issues,
      value: "Experiment identifier does not match",
    )
  }
  if text.length(value: value.summary) == 0 {
    issues = list.append(items: issues, value: "Summary is empty")
  }

  var seen: List<Text> = []
  for sourceId in value.sourceIds {
    if !hasSource(id: sourceId, notes: context.notes) {
      issues = list.append(items: issues, value: "Unknown evidence reference")
    }
    if list.contains(items: seen, value: sourceId) {
      issues = list.append(items: issues, value: "Duplicate evidence reference")
    }
    seen = list.append(items: seen, value: sourceId)
  }

  match value.state {
    EvidenceState.Supported => {
      if list.length(items: value.sourceIds) == 0 {
        issues = list.append(items: issues, value: "Supported report needs evidence")
      }
    }
    EvidenceState.Conflicting => {
      if list.length(items: value.sourceIds) < 2 {
        issues = list.append(items: issues, value: "Conflict needs two references")
      }
    }
    EvidenceState.Insufficient => {
    }
  }

  return issues
}

operation acceptedReportIsValid(
  value: Result<CheckedReport, ReportError>,
  context: FactsData,
) -> Bool effects [] {
  match value {
    Result.Err(error: _) => {
      return true
    }
    Result.Ok(value: checked) => {
      return list.length(
        items: reportIssues(value: checked.data, context: context),
      ) == 0
    }
  }
}

public operation accept(value: Report, context: FactsData)
  -> Result<CheckedReport, ReportError> effects []
  ensure acceptedReportIsValid(value: result, context: context)
{
  let issues = reportIssues(value: value, context: context)
  if list.length(items: issues) != 0 {
    return Result.Err(error: ReportError { issues: issues })
  }
  return Result.Ok(value: CheckedReport { data: value })
}

public operation exportReport(value: CheckedReport) -> Report effects [] {
  return value.data
}

test "Unknown evidence cannot create a checked report" {
  let facts = FactsData {
    experimentId: "checkout-17",
    findings: [],
    notes: [],
  }
  let candidate = Report {
    experimentId: "checkout-17",
    state: EvidenceState.Supported,
    summary: "A claim without supplied evidence",
    sourceIds: ["missing"],
  }
  match accept(value: candidate, context: facts) {
    Result.Ok(value: _) => {
      assert false
    }
    Result.Err(error: _) => {
    }
  }
}
```

File src/reports.meda:

```meda
module reports

import domain as domain
import std.model as model
import std.tasks as tasks

public enum Row {
  InvalidInput { id: Text, message: Text },
  ModelFailed { id: Text, kind: ModelErrorKind },
  InvalidReport { id: Text, issues: List<Text> },
  ReadyForDisplay { report: domain.Report, traceId: Text },
}

operation explain(facts: domain.Facts, policyValue: GenerationPolicy)
  -> Row effects [Model.call] {
  let data = domain.exportFacts(value: facts)
  let response = generate<domain.Report> {
    model "reporter"
    instruction "Explain the computed findings using the supplied notes. Distinguish supported evidence, conflicting notes, and insufficient evidence. Cite only supplied source identifiers. Do not invent owners, causes, outcomes, or actions."
    input data
    policy policyValue
    validate domain.reportIssues
  }

  match response {
    Result.Err(error: failure) => {
      return Row.ModelFailed(id: data.experimentId, kind: failure.kind)
    }
    Result.Ok(value: generated) => {
      let candidate = model.value(generated: generated)
      match domain.accept(value: candidate, context: data) {
        Result.Err(error: failure) => {
          return Row.InvalidReport(
            id: data.experimentId,
            issues: failure.issues,
          )
        }
        Result.Ok(value: checked) => {
          let info = model.info(generated: generated)
          return Row.ReadyForDisplay(
            report: domain.exportReport(value: checked),
            traceId: info.traceId,
          )
        }
      }
    }
  }
}

operation process(item: domain.ExperimentInput, context: GenerationPolicy)
  -> Row effects [Model.call] {
  match domain.prepare(input: item) {
    Result.Err(error: failure) => {
      return Row.InvalidInput(id: item.id, message: failure.message)
    }
    Result.Ok(value: facts) => {
      return explain(facts: facts, policyValue: context)
    }
  }
}

public operation run(
  experiments: List<domain.ExperimentInput>,
  policyValue: GenerationPolicy,
) -> List<Row> effects [Model.call] {
  return tasks.mapBounded(
    items: experiments,
    context: policyValue,
    work: process,
    limit: 4,
  )
}
```

The shared validator supports generation acceptance, the opaque constructor's expected-error handling, and its protected postcondition. The postcondition checks every successful construction even after a body-only edit. The constructor remains safe when another caller supplies a Report directly. Repeated evaluation consumes the specified budgets; its cost belongs in the benchmark rather than being silently optimized away.

CheckedReport means the named mechanical checks passed. It does not mean the report is factually verified or approved for an external action. Exporting it returns a plain transfer record; the wire value does not retain an unforgeable approval guarantee. A separate action API would need its own validated domain type and current authority.

Each generation has its own call-local error result; batch rows retain those failures. Root faults still abort the entire component. The returned list retains all rows and consumes memory proportionate to the results. The component demonstrates effectful callbacks and explicit context without closures.

The standard interface set for this component includes list.contains<T>(items: List<T>, value: T) -> Bool effects [] where T: Eq, classified contract-safe and metered by elements examined. GenerationInfo exposes traceId: Text in addition to the provenance fields specified earlier.

A host can obtain ExperimentInput values through an existing SDK and call this exported component through generated bindings. A later pilot adds an audited remote evidence lookup using section 13's tool binding; this example does not pretend to implement that external service. The absence of tool calls here keeps the full component executable with one model adapter or recorded fixtures.

# 21 Grammar outline

This grammar fixes the compact candidate's declaration structure. Lexical rules, statement separators, operator precedence, visibility, effect inference, and control-head disambiguation remain normative in the earlier sections. newline trivia is allowed where the declaration grammar continues. sep is a statement newline or end of its surrounding body.

```text
program       = "module" qname newline { import } { declaration } ;
import        = "import" qname "as" identifier newline ;
declaration   = ["public"] (record | enum | operation | constant)
              | tool | test ;
record        = ["opaque"] "record" identifier [typeParams]
                [constraints] [derive] "{" [typeFields] "}" ;
derive        = "derive" "[" capability {"," capability} [","] "]" ;
enum          = "enum" identifier [typeParams] [constraints]
                "{" [variant {"," variant} [","]] "}" ;
variant       = identifier ["{" typeFields "}"] ;
typeParams    = "<" genericParam {"," genericParam} ">" ;
genericParam  = identifier | "effect" identifier ;
constraints   = "where" constraint {"," constraint} ;
constraint    = identifier ":" capability {"+" capability}
              | "effect" identifier ":" "Concurrent" ;
capability    = "Eq" | "Ordered" | "Hashable"
              | "Serializable" | "ModelData" ;
typeFields    = identifier ":" type {"," identifier ":" type} [","] ;
type          = qname ["<" type {"," type} ">"] | callableType ;
callableType  = "operation" "(" [typeFields] ")" "->" type
                "effects" effectSet ;
effectSet     = "[" [effectName {"," effectName} [","]] "]" ;
effectName    = qname ;
operation     = "operation" identifier [typeParams]
                "(" [typeFields] ")" "->" type
                "effects" effectSet [constraints]
                {"require" expr sep} {"ensure" expr sep}
                block [examples] ;
examples      = "examples" "{" {"{" [fields] "}" "=>" expr sep} "}" ;
constant      = "let" identifier ":" type "=" constExpr sep ;
tool          = "tool" identifier "{"
                "target" qname sep "description" textLiteral sep "}" ;
test          = "test" textLiteral block ;
block         = "{" {statement sep} "}" ;
statement     = ("let" | "var") identifier [":" type] "=" expr
              | identifier "=" expr
              | "return" expr | "discard" expr | "assert" expr
              | ifStatement | "while" expr block
              | "for" identifier "in" expr block
              | "break" | "continue" | match | expr ;
ifStatement   = "if" expr block ["else" (block | ifStatement)] ;
match         = "match" expr "{" {pattern "=>" block} "}" ;
pattern       = literal | "_" | qname ["(" patternFields ")"] ;
patternFields = identifier ":" (identifier | "_")
                {"," identifier ":" (identifier | "_")} [","] ;
fields        = identifier ":" expr {"," identifier ":" expr} [","] ;
specialize    = "::" "<" genericArg {"," genericArg} ">" ;
genericArg    = type | effectSet ;
atom          = literal | qname [specialize]
              | qname [specialize] "{" [fields] "}"
              | "[" [expr {"," expr} [","]] "]"
              | "(" expr ")" | generation ;
postfix       = atom {"(" [fields] ")" | "." identifier | "?"
                | "with" "{" fields "}"} ;
expr          = implication ;
implication   = disjunction ["implies" implication] ;
disjunction   = conjunction {"or" conjunction} ;
conjunction   = equality {"and" equality} ;
equality      = comparison [("==" | "!=") comparison] ;
comparison    = addition [("<" | "<=" | ">" | ">=") addition] ;
addition      = multiplication {("+" | "-") multiplication} ;
multiplication = unary {("*" | "/" | "%") unary} ;
unary         = ("!" | "-") unary | postfix ;
generation    = "generate" "<" type ">" "{"
                "model" textLiteral sep
                "instruction" constExpr sep
                "input" expr sep
                "policy" expr sep
                ["tools" "[" [qname {"," qname} [","]] "]" sep]
                ["validate" qname sep] "}" ;
constExpr     = expr ;
qname         = identifier {"." identifier} ;
literal       = integerLiteral | floatLiteral | textLiteral
              | charLiteral | durationLiteral
              | "true" | "false" | "unit" ;
```

Only operations may declare effect generic parameters in Edition 1; record/enum generic parameters are types. Derive is permitted only for the specified opaque-record opt-ins. Higher-rank callable types and quantifiers inside value types are rejected. Public declarations and generic constraints are checked semantically after parsing.

Qualified enum cases use ordinary named-call syntax when they have payloads. Record constructors use braces. Callable values use ordinary call syntax and their static callable interface. A bare generic operation reference must acquire a concrete instantiation before becoming a value.

The grammar intentionally does not include closures, deferred computation values, model-task declarations, source-level capability construction, or a second parallel syntax. These omissions do not prevent reusable named operations or runtime-sized bounded traversal.

A parser implementation must add exhaustive fixtures for contextual keywords, multiline headers and clauses, nested callable types, effect-set specialization, same-line versus next-line else, record constructors before control blocks, trailing commas, and comment preservation. The EBNF is a design grammar; an executable grammar/checker corpus is an early deliverable.

# 22 Conformance corpus and acceptance cases

Language conformance and model quality have separate oracles. The compiler/runtime must pass deterministic acceptance/rejection cases before an AI authorship benchmark can interpret success rates.

| Area | Required cases |
| --- | --- |
| Callable values | Pure/effectful named references, exact labels, effect widening, monomorphic generic references, rejection of a callback whose effects exceed the caller. |
| Effect generics | Least sufficient inference, explicit wider sets, unconstrained variables, upper restrictions, and wrappers preserving Concurrent. |
| Opaque types | External construction/read/update rejection; allowed holding/passing; conditional equality/hash derivation; rejection of transitive automatic decoding. |
| Predicate eligibility | Direct eligible helpers, ineligible transitive calls, callback purity without structural eligibility, finite-loop exhaustion, changed helper invalidating a contract. |
| Result diagnostics | Direct ignored Result rejection; explicit dismissal; unused binding warning; legal length-only inspection of a result list without claiming deep handling. |
| Arithmetic and text | Large integers, bounded overflow, signed division/remainder, non-finite floats, Unicode scalars versus bytes, raw multiline text, exact JSON numeric conversion. |
| Model acceptance | Refusal, truncation, duplicate/unknown fields, integer strings/bounds, enum tags, projected constraints, validator rejection and isolated validator faults. |
| Authority | Source tool allowlist, host intersection, wrong tenant/path, transitive helper access, operation references that must not capture broader grants. |
| Budgets | Atomic competing reservations, proven non-dispatch refunds, unknown usage retention, local versus root failure precedence, late results after termination. |
| Tool loops | Malformed requests consuming allowance, domain errors as data, denied requests stopping generation, no automatic retry after tool execution begins. |
| Bounded maps | N equal to 0, 1 and 1000; stable result order; per-item Err; root fault cancellation; memory caps; nested maps without permit deadlock. |
| Replay | Competing branch admissions, changed host completion order, deadlines during pure work, recorded timing fields, missing/redacted events, no live effects. |
| Edits | Stale revisions, invalid grants, body-only scope, protected tests, required checks, stale validation receipts, interrupted commits, unchanged comments/contracts. |
| Interop | Opaque/callable public API without wire export; exact generated-client DTOs; wrong host schema; pinned registry/type identities. |

Each case must specify the observable result, diagnostic/fault category, and whether any host effect can have occurred. The corpus should expose semantic disagreement before it becomes undocumented implementation behavior.

The worked component also needs deterministic fixtures for malformed input, duplicate source IDs, unsupported references, conflicting notes, missing evidence, and provider failure. Fidelity of summaries requires independent reviewed examples. A nonempty summary and valid reference IDs do not establish truthful synthesis.

# 23 Evaluation of AI authorship and model usefulness

The primary experiment asks whether the language's enforced boundaries support correct changes with less context and fewer regressions. Source notation, semantic features, compiler tools, and runtime facilities are distinct variables.

Begin with 12–20 maintenance tasks across several modules as a screening corpus. Include a bug fix under an unchanged contract, a new error/enum case, schema evolution, extraction of duplicated behavior, an opaque construction boundary, a collection invariant, a scoped-access change, and independent concurrent edits. Repeated histories matter more than one-shot demos.

First check that each task is solvable from the context the compiler proposes to supply. If an unstated convention elsewhere determines correctness, strengthen the interface or count the extra context. Do not attribute hidden requirements to model failure.

Compare compact and sectioned frontends over the same checked semantics. Compare ordinary text editing with compiler-supported changes. Include an existing-language control with comparable compiler context, scoped edits, independent tests, and runtime facilities where feasible. Explicitly report any guarantee the control cannot match.

Protect acceptance tests and task scope from the editing agent. Track completed correct changes, regressions, retrieved context, prompt/tool/repair/output tokens, elapsed time, validation work, and reviewer effort. Syntax errors remain in total repair cost even when reported separately. Use multiple models and repeated trials.

Predeclare a practically meaningful improvement margin and enlarge the sample enough to distinguish it from variation. The screening corpus is not automatically sufficient statistical evidence. An inconclusive result remains inconclusive. If the equally equipped existing-language control gives the same useful outcome at lower cost, revise the new-language claim for that workload.

Current models have unequal pretraining exposure. Initial equal documentation budgets support a near-term comparison, not a claim about every future model. Controlled adaptation with matched semantic corpora can be later research; it is not required to test whether interfaces actually preserve invariants or reduce needed context.

Model-runtime evaluation is a separate suite. It pins datasets, prompts, validators, configuration, samples, scoring, and budget. Test evidence-grounded synthesis against deterministic rendering and existing-language implementations using the same adapters. Report structural acceptance, factual/task quality, abstention, refusal, latency, and usage separately. A model judge is another model judgment with its own recorded configuration.

Development/tuning data and held-out acceptance data remain separate. Changing a judge, contract, or acceptance fixture is a specification change. meda eval never runs silently during a normal check or edit validation.

No single result establishes a perfect language. The project can remain worthwhile as language research without an empirical superiority claim; practical positioning should follow the evidence.

# 24 Implementation plan and decision gates

The target semantics and first implementation are intentionally different scopes. A small prototype is a way to test an architectural claim, not evidence that omitted features are unnecessary.

| Gate | Build | Required decision |
| --- | --- | --- |
| A Semantic corpus | Exact core rules, parser fixtures, representative programs, edit request/diagnostic schemas, and benchmark task definitions. | Resolve contradictions that alter accepted programs or claimed guarantees. |
| B Pure change loop | Bool/Int/Text/Unit, records/enums, built-in containers, named operations, loops/match, restricted contracts, formatter, describe, guarded body replacement, check/test. | Does the full AI maintenance loop improve useful outcomes under matched tools and budgets? |
| C Composition variants | Named pure references, opaque records, reusable eligible predicates; then limited effect generics and effectful callbacks. | Which mechanisms improve locality/correctness enough to retain? Test additions separately where practical. |
| D One model component | Typed host boundary, one adapter, shared policy, full local validation, explicit projection, local/root outcomes, mocks, and one generated host client. | Does native integration add value independently of the source-language experiment? |
| E Real workflow | Bounded maps, one audited remote read if required, scoped tools, detailed accounting and transition tests. | Can the intended workflow run without application-specific compiler changes or authority bypass? |
| F Replay and broader editing | Complete event identities/journal, strict replay, cache policy, interface edits/rename, recoverable multi-file commit. | Do the stated replay/edit guarantees survive adverse interleavings and interrupted publication? |
| G Edition readiness | Second adapter, maintained applications, documentation, compatibility policy, stable implemented schemas and conformance. | What can be supported as the first public edition? |

Gate B uses no live providers, tools, host extension ABI, caches, replay, concurrency, capturing closures, or deep Result obligations. It may initially omit user-defined generics and opaque/callable features while using a fixed pure corpus. Fixed input limits and a supervised worker deadline provide experimental containment; it does not advertise the finished resource model.

Gate B evaluates the compiler-assisted change protocol and implemented pure subset only. Run the applicable screening tasks; unsupported tasks are excluded and reported, not counted as failures or successes. Gate C adds matched tasks for opaque invariants, reusable predicates, and callable composition. Conclusions about those mechanisms require those comparisons.

Gate C must occur before freezing a general-purpose edition. A pure callback experiment does not settle reusable effectful workflows. Likewise, a successful literal-data model demo does not establish integration quality or model usefulness.

The roadmap does not require implementing every review suggestion immediately. It does require testing the differentiating change loop before most runtime investment and specifying each guarantee before exposing it to users. Full provider/schema/versioned interface tables are generated for implemented surfaces as they enter their gates.

The executable acceptance work begins with a versioned Gate A corpus and Gate B protocol schemas. A corpus case records source, invocation or edit, expected phase/code/value, permitted effects, and the earliest supporting profile. Unsupported cases remain deferred and visible; they do not count as passes. Gate B maintenance tasks map to available edit operations: existing-body repairs use replace_body; extraction, new declarations, schema changes, and multi-file changes are excluded until their authorized staged edit path exists. Fixture/smoke execution is not an AI comparison. A Gate B decision requires independent acceptance checks, a matched existing-language control, named models, repeated trials, and measured whole-change cost under the preregistered protocol.

# 25 Resolution of the adversarial findings

| Review finding | Draft 2 decision | Remaining validation |
| --- | --- | --- |
| R1 Reusable behavior | Named operation values, limited effect generics, explicit context, and mapBounded. | Compare pure/effectful abstraction cost and useful maintenance outcomes. |
| R2 Domain invariants | Module-owned opaque records, protected updates, explicit wire conversion. | Reject every fabrication/decoding path and test representative domain APIs. |
| R3 Reusable contracts | One conservative contract-safe helper analysis shared with model validators. | Eligibility, resource-failure cases, and usefulness of collection predicates. |
| R4 Late authorship experiment | Pure compiler change loop at Gate B. | Matched control and whole-change outcomes before runtime expansion. |
| R5 Weak corpus | Multi-module histories, runtime-sized batches, evidence synthesis, and an external consumer. | Build independent cases and evaluate against deterministic alternatives. |
| R6 Deep Result promise | Exact shallow ignored-result errors and unused-binding diagnostics. | Explicit acceptance/rejection cases; no hidden deep guarantee. |
| R7 Budget outcome ambiguity | Defined local error domains, root precedence, atomic reservation and publication. | State-transition and race tests. |
| R8 Variable-cost work | Metering/size/admission rules cover native and compiler work as well as evaluator steps. | Publish the actual cost model and host containment assumptions. |
| R9 Replay ordering | Stable occurrence identities and a compact decision journal, including exceptional metered checkpoints. | Full replay remains unavailable until conformance tests pass. |
| R10 Provider schema policy | Explicit projected or exact provider profile with unchanged authoritative local acceptance. | Adapter capability matrix and invalid-output fixtures. |
| R11 Tool authority | Immutable host-bound scopes intersected on every transitive access. | Wrong-resource tests independent of model obedience. |
| R12 Edit authority | Trusted grants, protected artifacts, required validation, receipt-bound commit. | Stale/unauthorized/tampered transaction cases. |

The revised core also charges declared callee effects, distinguishes public visibility from exportability, and uses conservative transitive cache identity. First-class capability syntax, universal computation values, general proof checking, fine-grained edit rebasing, and typed holes remain deferred experiments.

Draft 2 narrows model validators to the same structurally checked pure subset used by contracts. That is a deliberate change from Draft 1's unrestricted pure validator bodies. It gains one reusable eligibility model at the cost of rejecting some otherwise pure algorithms. The corpus must determine whether that restriction is practical.

The compact syntax and explicit policy record are concrete working choices. They remain reversible before edition commitment. No benchmark result is assumed, and the target does not claim novel punctuation or a semantic IR alone creates an AI advantage.

# 26 References and design status

The authoritative project context is the [Meda repository](https://github.com/meda-lang/meda), previously inspected at commit [6d01d7a1ff77f2fd04d0b7175f0b24bcf14ee19e](https://github.com/meda-lang/meda/tree/6d01d7a1ff77f2fd04d0b7175f0b24bcf14ee19e). That implementation does not implement this proposed edition. Historical examples should remain labeled until replacements exist.

[Draft 1](https://chatgpt.com/space/page_7999496119cc8191a579ac58ed8bb3fb) records the earlier baseline. The [adversarial review](https://chatgpt.com/space/page_dec3ec48887c8191bed62e7b4ab9e2d0) supplies the counterexamples and competing designs addressed here.

Established precedents include [Dafny contracts](https://dafny.org/dafny/DafnyRef/DafnyRef), [Koka effects](https://koka-lang.github.io/koka/doc/book.html), [Unison abilities](https://www.unison-lang.org/docs/language-reference/abilities-and-ability-handlers/), [MLIR shared operation definitions](https://mlir.llvm.org/docs/DefiningDialects/Operations/), and [RFC 8785 canonical JSON](https://www.rfc-editor.org/rfc/rfc8785). These motivate mechanisms, not claims of Meda performance.

The provider/local acceptance distinction is informed by the documented schema subsets and validation boundaries in [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) and [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output). Adapter versions must pin their actual capability contracts rather than depend on an unversioned documentation page.

[BAML generated clients](https://docs.boundaryml.com/guide/introduction/what-is-baml) illustrate a language-to-host adoption path. [Wasmtime security guidance](https://docs.wasmtime.dev/security.html) illustrates host-boundary and terminal-rendering concerns. Meda does not require either implementation.

The design's definite claims concern proposed semantics and enforcement boundaries. Whether its notation, abstractions, and tooling improve AI-authored software requires the experiments in section 23. The worked source is specification material until a conforming compiler and runtime execute it.
