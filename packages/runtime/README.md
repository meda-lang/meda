# meda-runtime

Experimental Python host and process supervisor for Meda's fixed evidence/report
profile. Python 3.11+; Linux supervision is exercised on Python 3.12. The installed
package uses only the standard library and imports no research harness code.

```sh
python3 -m pip install ./packages/runtime
```

```python
from meda_runtime import HostConfig, Limits, run_application

# Trusted parent supplies approved endpoints, CA, grants and bearer tokens.
receipt = run_application(config, ["node", "/path/to/application/main.js"], {
    "documentId": "evidence-42",
    "includeIds": ["f1", "f2"],
})
print(receipt["result"])
```

`config` is a validated `HostConfig`. See the [runtime guide](../../docs/runtime-library.md)
for its configuration example, CLI, outcomes and supported guarantees. The
[TypeScript example](../../examples/evidence-report/README.md) shows a complete
application. The [installed-package verifier](../../tools/runtime-demo/verify.py)
builds and installs a wheel into a fresh environment and runs actual protocol
workflows outside the repository.

No registry release is published. This profile supports evidence revision 1 and
five host operations; it is not a general protocol SDK or an OS security sandbox.
