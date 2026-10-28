"""Record the exact local implementation/dependency/fixture candidate."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from .host import Limits, digest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def runtime_source_paths(root=ROOT):
    """Canonical implementation inputs, excluding build/cache outputs."""
    package = root / "packages/runtime"
    return [package / "pyproject.toml", *sorted((package / "src/meda_runtime").rglob("*.py"))]


def source_snapshot():
    paths = set(runtime_source_paths(ROOT))
    for pattern in ("*.py", "client/*.ts", "tsconfig.json"):
        paths.update(HERE.glob(pattern))
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths) if path.is_file()}


def main():
    from .sdk_peers import build_agent_card, build_tool_descriptor

    files = ["acceptance.json", "requirements.lock", "package-lock.json",
             "dependency-provenance.json", "specification-sources.json"]
    descriptor = build_tool_descriptor()
    card = build_agent_card("https://127.0.0.1:443/a2a")
    output = {"profile": "meda-interop-d0/1", "freezeKind": "development_candidate",
              "acceptanceClosed": False, "python": platform.python_version(),
              "node": subprocess.check_output(["node", "--version"], text=True).strip(),
              "platform": platform.platform(), "limits": asdict(Limits()),
              "artifactSha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in files},
              "sourceSha256": source_snapshot(),
              "toolDescriptor": descriptor, "toolDescriptorSha256": digest(descriptor),
              "agentCardTemplate": card, "agentCardTemplateSha256": digest(card),
              "endpointRule": "Each run substitutes its allocated loopback TLS endpoint and records the resulting card digest.",
              "scope": "Pinned reference implementation candidate; does not certify protocol conformance or close D0-01/02/03 acceptance."}
    (HERE / "candidate-manifest.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"profile": output["profile"], "freezeKind": output["freezeKind"]}))


if __name__ == "__main__":
    main()
