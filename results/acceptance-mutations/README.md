# Controlled mutation verification

This bounded follow-up executes four frozen host/TypeScript mutation cases.
Each has an unchanged control and a deliberately modified implementation over
real SDK peers. See [the design and limits](../../docs/acceptance-mutations.md).

- [Regression summary](validation.json): all 210 tests passed across six suites.
- [Raw frozen execution](frozen-run.json): four cases, each with its control,
  actual result, independent observations, source hashes, and ordinary assessment.
- [Behavioral screen](screen.json): three injected defects detected and one
  repeated submission contained by the canonical host.

Full acceptance remains open: three cases are **unverified**, and the repeat-
submit case is **failed** because its frozen attribution excludes the shared
host that actually enforces the denial. This failure is explicitly retained;
there are no other failed frozen checks. No Meda source-mutation arm was run.
The source snapshot is unchanged during the frozen execution. Original
inventory, canonical runtime/client, and historical result files are unchanged.

Logs: [language](gates.log), [protocol/host](interop.log),
[earlier comparison](comparison.log), [decision screen](decision-screen.log),
[runtime](runtime.log), and [TypeScript package](typescript-package.log).
The first older-comparison invocation lacked `MEDA_COMPARE_TSC` and failed before
TypeScript compilation; its [log](comparison-initial-environment-error.log) and
[partial summary](validation-initial-environment-error.json) are preserved.
Setting the compiler path to the already installed, pinned TypeScript compiler,
as CI does, resolved it without changing code. Already passing suites were not
repeated. `validation.json` records the successful suites and that setting.

The CI command in the design document reevaluates the raw receipts. A successful
bounded screen requires all behavioral checks and permits only the explicitly
reported attribution mismatch. Its `acceptanceClosed` value remains false.
