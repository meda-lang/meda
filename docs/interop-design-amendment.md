# Meda interoperability design amendment

Status: accepted experimental direction; semantics below are proposed and not
implemented. October 25, 2026. This amendment supplements Draft 2.1 sections 4,
9, 10, 15, 17, 23 and 24. The [workflow specification](interop-workflow.md) fixes
the protocol slice and acceptance cases; the [evaluation protocol](interop-evaluation.md)
fixes the comparison and decision rules.

The [executed comparison](runtime-comparison.md) established that a strict
TypeScript client can use the same implemented host protections as Meda. It did
not exercise Meda's proposed effectful boundary. The next investment is therefore
a reusable host and one bounded interoperability experiment. Meda must demonstrate
incremental value through enforceable source boundaries or maintenance outcomes.
The usefulness of the library is a separate hypothesis from the usefulness of a
new language.

## Architecture and attribution

Both clients call the same host operations, which use the same protocol adapters.
The common host receives a fixed run configuration and owns admission, resource
accounting, identity partitions, cancellation and terminal publication. An adapter
implements a pinned external protocol and decodes its responses. Application
source implements workflow policy. Compiler checks constrain source programs;
they do not establish remote truth or grant authority.

| Layer | Responsibility in this experiment |
| --- | --- |
| Meda checker | Module visibility, nominal types, opaque construction boundaries, declared effects and ordinary source checking |
| TypeScript reference tools | Strict typing, private or branded wrappers, module restrictions, validation and comparable guarded editing |
| Shared host | Per-call authorization, finite budgets, binding identity, response limits, root ownership and bounded local cleanup |
| Shared adapters | Pinned protocol messages, capability negotiation, schema decoding and accurate remote-outcome reporting |
| Application in either language | Sequencing, response to required input, uncertainty policy and domain acceptance |
| Remote peer | Its own task ownership, execution and cancellation behavior |

Direct host tests must continue to bypass both language checkers. A protection
that survives that bypass is not credited solely to Meda. Source defects and
host mutations are separate experiments, and every rejected case records the
rejecting layer and whether any remote effect occurred.

## Proposed profile meda-interop-d0/1

The new profile preserves the existing `meda-pure-b0/1` profile and its corpus.
Its application executes ordinary source calls to generated host bindings. A
checked Meda operation must actually invoke the host, receive a typed outcome,
and continue or terminate inside the same supervised run. Returning a decision
record for a Python orchestration loop to interpret does not satisfy this gate.

The implementation cutline is deliberately small:

1. **One local package with multiple modules.** Module paths, explicit imports,
   public/private visibility, acyclic imports and nominal declaration identity
   are enforced. A content manifest pins the package, compiler and host registry.
   Dependency resolution, a package registry and cross-edition linking remain
   outside this profile. The application modules separate workflow policy,
   domain validation and binding use.
2. **Monomorphic effect sets and direct calls.** Every operation declares a finite
   effect bound. Calling an operation charges its declared bound, even when its
   current body is pure. Transitive helpers cannot erase effects. Contract
   predicates remain pure and cannot call a host binding. Effect variables,
   callable values and effectful callbacks are deferred.
3. **Opaque records with real owner checks.** Only a defining module may construct,
   inspect or update its opaque representation. Cross-module literals, field
   access and patterns cannot bypass that boundary. Attempted generic decoding
   is rejected; this profile does not implement a general decoder for opaque
   values. Opaque values have no automatic wire representation. Validated domain
   values and host-issued remote references are distinct types.
4. **Sequential typed host calls.** The pinned binding declares exact argument,
   result and error types. The profile may use explicit monomorphic outcome enums
   without implementing general user generics or the full `Result` machinery.
   It must not claim unimplemented must-use or generic guarantees. The public
   binding schema and source codecs must agree.
5. **Owned local execution.** Root limits, per-request bounds and finite cleanup
   allowances are explicit. Expected local failures are typed outcomes; root
   cancellation, exhaustion and integrity failure terminate the run. The host
   prevents a late response from resuming abandoned source or publishing success.

No `generate` form, live model provider, autonomous tool selection, general FFI,
raw network API, bounded parallel map, public async handle, durable workflow,
cache or strict replay is needed. These exclusions are checked, not silently
emulated. Agent delegation is an explicit application operation; it is not an
autonomous model write tool.

## Remote references and opacity

`TaskRef` denotes an opaque reference to a remote task within one local run. It
is not a Promise, an open transport, a durable recovery token, or proof that the
remote service will honor cancellation. The reserved trusted host module owns its
representation and constructor path. The registry pins that module's actual
nominal type identity and issuance rules. A wire string claiming to be a task ID
cannot be deserialized directly into a `TaskRef`.

Issuance occurs only after the common host validates the received task identity
and binds it to the configured peer, security partition, registry identity and
root. The runtime bridge may represent it internally as a host-issued token;
application code receives only the opaque source value. The TypeScript wrapper
uses the same issuance path. Every subsequent use still passes current host
checks. A forged token submitted directly to the host, a different principal, a
different peer and a closed root must all fail independently of static typing.

Source may hold, copy and pass a valid reference while its root is live. This is
not a linear ownership system. Closing the root invalidates its local references;
it does not prove that the remote task stopped. Persistence and reattachment in a
new run are deferred and cannot be simulated by serializing the opaque value.

An ordinary domain opaque type follows its defining module's checked constructor
and observers. Its validity does not establish authorization. Editing the owner
can weaken its invariant, so acceptance tests, protected specifications and edit
grants remain necessary in both arms.

## Registry contract for changing protocols

MCP, A2A and later protocols enter through adapter bindings rather than new
language keywords. Each binding pins its adapter and protocol profile, request
and response schemas, exact source type identities, effect bound, semantic
read/write classification, capabilities, destinations, credential reference,
limits, cancellation semantics and trace identity. Setup rejects incompatible
bindings and missing required capabilities before the affected business request.
Authenticated discovery and revalidation are permitted host control operations
and consume explicit resource allowances. A discovered incompatible change during
a run closes affected future business admission; already dispatched work retains
its recorded outcome. Discovery cannot silently broaden checked authority.

Evidence reading and task observation are distinct from task submission,
continuation and cancellation, which mutate remote task state. An HTTP method
or peer-supplied descriptor cannot override that audited classification. Wire
extensions may be handled only under the pinned profile's declared rules;
unknown task states cannot be treated as successful completion.

Credentials remain host-owned. Clients cannot supply arbitrary destinations,
register adapters, forge the `host` namespace or fall back to unrestricted
network access. Both client workers need an appropriate common execution boundary
if adversarial source is in scope; an effect checker alone is not that boundary.

Root shutdown closes application admission and joins bounded local cleanup.
Remote cancellation is a distinct authorized protocol operation, not an assumed
effect of releasing a local connection. Unknown delivery remains unknown. The
application must stop according to the declared uncertainty policy; opacity and
effect checking do not prevent every explicit duplicate submission. Any shared
deduplication mechanism added later must be available to both clients and receive
separate attribution.

## Fair TypeScript reference

The conventional client retains strict checking, precise outcome unions, runtime
validation, private or branded wrappers, supported module restrictions and the
same host authority. It receives comparable context, protected acceptance tests
and edit safeguards. The experiment records which protections come from the
compiler, configured tooling or library. It does not intentionally weaken the
reference to manufacture a Meda advantage.

Lifecycle correctness is initially a shared-host hypothesis. A language-specific
claim requires evidence that its source boundary or editing tools prevent
relevant defects beyond the equally equipped reference. Different diagnostics
or syntax alone do not establish that benefit.

## Revised gate ordering and stopping boundary

Draft 2.1 section 24 now permits a bounded portion of Gate C and a new exploratory
**D0 interoperability comparison** before broad model-runtime investment. D0
depends on the required module, opaque and direct-effect cases from Gate C. It
does not complete Gate C, the Gate B maintenance study, Gate D's model component
or Gate E's broader workflow requirements. Existing results retain their original
scope and counts.

| Dependency | Acceptance boundary |
| --- | --- |
| Freeze the binding contract and workflow oracle | Protocol versions, authority, outcomes, scope exclusions and observable failure cases are explicit |
| Implement the minimum checker profile | Cross-module opaque misuse and undeclared/transitively erased effects fail before any host request; valid controls pass |
| Implement the common host bridge | Both real source clients call the same operations; authorization and cleanup survive checker bypass |
| Execute the paired protocol workflow | Required scenarios pass against independent protocol checks, with dispatch and terminal-outcome evidence |
| Admit maintenance trials | Cross-file edit safeguards, isolated acceptance, named model configurations and matched resources are demonstrably available |

If the workflow requires a feature outside this cutline, record the blocking case
and revise the scope explicitly before expanding the compiler. Do not absorb the
whole proposed runtime into D0. Build effort, failed approaches and baseline
tooling effort are retained in the evaluation. Passing protocol tests permits
maintenance evaluation; it does not establish language superiority or independent
market demand for the library. The evaluation protocol defines the bounded
continue, revise and stop decisions.
