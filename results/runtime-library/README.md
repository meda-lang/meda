# Runtime package verification

This work makes the existing evidence/report host independently installable and
adds a conventional TypeScript consumer. It implements the library-first next
step from [the decision screen](../../docs/decision-screen-results.md). It does
not close full D0 acceptance or establish a language productivity result.

## Installed artifacts

[installed-packages.json](installed-packages.json) records a Python wheel and npm
tarball built from the frozen source inventory, installed into a fresh temporary
venv/application directory outside the repository. The Python consumer uses
isolated mode and cannot import `experiments`; the TypeScript consumer resolves
the tarball package from its own `node_modules`. Neither installed package has
runtime dependencies or experiment/test modules in its artifact inventory.

The seven local SDK cases check:

| Case | Required result |
| --- | --- |
| Success | Exact validated report |
| Required input | Same remote task continued once |
| Lost submit response | Unknown delivery, one submit, no resubmission |
| Wrong response ID | Protocol rejection before creating a task |
| Wrong fact value | Application domain rejection |
| Reordered facts | Application accepts and normalizes the report |
| Explicit cancellation refusal | Refusal preserved; no cleanup cancellation retry |

Every row additionally checks CLI exit status, one publication, child retirement,
supervisor join, peer task count, fixture shutdown, and the named output scans.
The receipt preserves individual checks, host trace, peer/proxy observations,
artifact hashes/file inventories, and source hashes before and after execution.
[verification.json](verification.json) records the accompanying regression checks.

## Extraction and public API fixes

The canonical host, HTTPS transport, and process controller now live in
`packages/runtime`. Historical experiment entry points forward to that code;
scenario hooks remain in the development runner. Fresh experiment snapshots now
hash the canonical package as well as their local code. Previously checked-in
receipts and candidate manifests are unchanged.

Package review also added early configuration validation, hidden credential
fields in debug representations, bounded/strict worker frames, and explicit
public error behavior. Known credentials are rejected in initial input and
command arguments. Application proposals containing known credentials or private
references are rejected before publication; untrusted diagnostics are redacted
without changing runtime-owned receipt fields.

## Reproduce and interpret

Run the commands in the [runtime guide](../../docs/runtime-library.md). New runs
belong under `generated/` with a fresh filename. The checked-in receipt is one
observed run, not a timing guarantee or a reproducible binary-build claim.

The development driver uses the existing official SDK fixtures; the installed
consumer does not. Tests use local deterministic HTTPS peers, numeric loopback
addresses and test credentials. They make no model-provider calls. The public
profile supports five operations and evidence revision 1. Report correctness is
an application validator's responsibility.

A clean scan covers its named observed channels only. Runtime metadata that
happens to equal a credential is not credential-derived application output.
Process-group retirement and sampled RSS remain supervision aids, not an OS
sandbox. DNS deadline behavior, production authentication, full discovery
accounting, source-continuation evidence and complete acceptance remain bounded
by [issue #11](https://github.com/meda-lang/meda/issues/11). No registry release is
published by this change.
