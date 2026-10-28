# @meda/evidence-client

An experimental TypeScript client for Meda's fixed evidence/report host profile. It has no runtime dependencies. This package is private and is distributed as a local tarball for evaluation; it is not published to npm.

`runWorker` connects application code to the Python `meda-runtime` host over bounded JSONL on standard input/output. The Python host owns credentials, authority checks, budgets, transport deadlines, and final result publication.

```ts
import {runWorker, record} from "@meda/evidence-client";

void runWorker(
  value => record(value) && typeof value.documentId === "string"
    ? {documentId: value.documentId}
    : null,
  async (host, input) => {
    const evidence = await host.readEvidence(input.documentId);
    if (evidence.kind === "Error") {
      return {outcome: evidence.code, remoteOutcome: evidence.remoteOutcome};
    }
    return {outcome: "EvidenceRead", facts: evidence.value.facts};
  },
);
```

The application must return a JSON object with an `outcome` string for the supervisor and await each host call before issuing another. Standard output is reserved for worker protocol frames. Application-specific relationships, such as whether selected report facts match the evidence, remain application validation.

## Public API

- `runWorker<Input, Output>(decodeInput, application): Promise<void>` decodes one start input, supplies `HostApi`, and emits one final result or a generic failure.
- `createBindings(exchange)` returns `{host, close}` for an existing transport. The caller supplies the exchange implementation and its transport lifecycle.
- `HostApi` exposes `readEvidence`, `submit`, `observe`, `provideInput`, and `cancel`.
- `TaskRef`, task/result/error types, `Evidence`, `Fact`, and `Report` describe this profile.
- `record`, `decodeEvidence`, and `decodeIds` help decode unknown input. `bindingError` creates a typed host error. No application report validator is exported.

Task references have private runtime membership scoped to their binding. Serializing one produces `{}`; a cast, reconstructed value, or reference from another binding cannot issue a task operation. `close()` retires the binding and its references. A response arriving after close is rejected as `RootTerminated` with `remoteOutcome: "Unknown"`, because an already dispatched operation may have run.

`remoteOutcome: "Completed"` describes delivery of a host exchange. It does not prove that a remote task reached a terminal state. Cancellation does not imply rollback.

## Profile and limits

This is an evidence/report profile, not a general MCP or A2A SDK. The client expects evidence revision **1**, one to 32 facts, unique fact IDs, and nonempty IDs and values of at most 256 Unicode scalar values. Supplied selection lists contain one to 32 unique, nonempty IDs. Omitting selection on submission allows the workflow to request input. Changing the Python host's expected revision does not extend this client's decoder.

These decoders follow the supported host profile. Historical pure maintenance fixtures that accept an empty selection are not an additional host capability.

The worker bounds each incoming frame to 65,536 bytes including its newline while reading, before UTF-8 decoding or JSON parsing. It rejects malformed UTF-8, partial frames at EOF, unsolicited or duplicate frames, wrong response correlation, concurrent calls, and completion with an outstanding host call. Outgoing frames have the same wire limit. Worker failures produce a bounded generic result without exception text.

The worker runs ordinary Node application code. This package does not provide operating-system isolation or prevent application code from using Node facilities or writing to stdout. The Python supervisor and deployment environment determine the process boundary.

## Build and test

From this directory, using Node 24:

```sh
npm ci --ignore-scripts
npm test
npm pack
```

Development dependencies are pinned to TypeScript 5.9.3 and `@types/node` 24.10.1. The tarball contains compiled JavaScript, declarations, this README, and the license. The separate installed-consumer check in the repository exercises it without importing experiment files.
