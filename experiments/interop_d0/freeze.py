"""Record the exact local implementation/dependency/fixture candidate."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from .host import Limits, digest
from .sdk_peers import build_agent_card, build_tool_descriptor

HERE = Path(__file__).resolve().parent


def main():
    files = ["acceptance.json", "requirements.lock", "package-lock.json",
             "dependency-provenance.json", "specification-sources.json"]
    descriptor = build_tool_descriptor()
    card = build_agent_card("https://127.0.0.1:443/a2a")
    output = {"profile": "meda-interop-d0/1", "freezeKind": "development_candidate",
              "acceptanceClosed": False, "python": platform.python_version(),
              "node": subprocess.check_output(["node", "--version"], text=True).strip(),
              "platform": platform.platform(), "limits": asdict(Limits()),
              "artifactSha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in files},
              "toolDescriptor": descriptor, "toolDescriptorSha256": digest(descriptor),
              "agentCardTemplate": card, "agentCardTemplateSha256": digest(card),
              "endpointRule": "Each run substitutes its allocated loopback TLS endpoint and records the resulting card digest.",
              "scope": "Pinned reference implementation candidate; does not certify protocol conformance or close D0-01/02/03 acceptance."}
    (HERE / "candidate-manifest.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"profile": output["profile"], "freezeKind": output["freezeKind"]}))


if __name__ == "__main__":
    main()
