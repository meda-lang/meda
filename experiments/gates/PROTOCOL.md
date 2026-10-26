# Gate B experimental editing protocol

The trusted host starts `meda.py edit SOURCE --grant GRANT`. The editing stream
cannot create or modify grants. The source, grant, check file, and toolchain must
be outside the agent's other write routes for any scope-enforcement claim.
The schema version is 1; JSON Schema files in `schemas/` describe wire shapes.
Runtime validation is implemented by the host and method signatures.

A grant pins its base source digest, operation-name targets, explicitly authorized
specification roots, source test IDs, acceptance file/digest, and optional expiry
as Unix seconds. Acceptance cases must have distinct IDs and be nonempty.
The grant and acceptance files are read on startup and checked again before
validation and publication. Filesystem paths in the grant are host-owned.

Example request sequence:

```json
{"method":"begin_edit","params":{"expectedRevision":"SOURCE_SHA256"}}
{"method":"replace_body","params":{"transaction":"RETURNED_ID","symbol":"solve","body":"{\n  return value\n}"}}
{"method":"validate_edit","params":{"transaction":"RETURNED_ID"}}
{"method":"commit_edit","params":{"transaction":"RETURNED_ID","receiptId":"RETURNED_RECEIPT","expectedRevision":"SOURCE_SHA256"}}
{"method":"transaction_status","params":{"transaction":"RETURNED_ID"}}
```

Successful responses contain `ok: true` and `result`; rejected requests contain
`ok: false` and a structured `diagnostic`. A failed acceptance check returns a
successful protocol response with validation status `failed`; it issues no
committable receipt. A subsequent body edit invalidates every earlier receipt.

Body scope is checked by parsing the staged source and masking only the selected
body in both versions. All other source bytes must match. This rejects injected
declarations and changes to headers, contracts, source tests, and documentation.
The initial protocol supports operation names in a single file, not persistent
cross-revision symbol IDs.

Every protected contract is a root. Its helper closure includes body calls,
implicit require/ensure calls, referenced module constants, and all nominal
types conservatively. Base/staged closures are compared. The host reports affected
root IDs and `describe` supplies helper dependencies. Changes require the relevant
root in `allowSpecificationRoots`; otherwise `SpecificationChange` rejects them.
Acceptance files are pinned whole. External custom oracle-helper execution is
not implemented; allowing it later requires transitive protection too.

Validation binds source/grant/check/toolchain digests and actual outcomes into an
in-memory receipt. Publication rechecks the original revision under a cooperative
file lock and uses same-directory atomic replacement. All protocol clients must
honor the lock. An agent with arbitrary filesystem access can bypass the host;
this prototype does not claim to contain such an agent. It also does not provide
durable restart recovery or universal transactions for external filesystem writers.
`transaction_status` reconciles uncertain replies only while the process remains
alive. Crash recovery and multi-file publication remain Gate F work.

The schema includes evidence fields but does not constitute a security proof.
The implementation and its tests are the current executable contract. The planned
Rust implementation must run the same outside-in acceptance cases.
