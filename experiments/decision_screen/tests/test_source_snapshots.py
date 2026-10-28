"""Fresh experiment receipts must freeze the implementation behind the shims."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.decision_screen import run
from experiments.interop_d0 import acceptance_run, freeze


ROOT = Path(__file__).resolve().parents[3]


class SourceSnapshotTests(unittest.TestCase):
    def snapshots(self):
        return (
            (run.source_snapshot, ""),
            (freeze.source_snapshot, ""),
            (acceptance_run.source_hashes, "../../"),
        )

    def test_canonical_runtime_and_compatibility_sources_are_frozen(self):
        implementation = sorted((ROOT / "packages/runtime/src/meda_runtime").rglob("*.py"))
        self.assertIn(ROOT / "packages/runtime/src/meda_runtime/host.py", implementation)
        self.assertIn(ROOT / "packages/runtime/src/meda_runtime/supervisor.py", implementation)
        for snapshot, prefix in self.snapshots():
            with self.subTest(snapshot=snapshot.__module__):
                hashes = snapshot()
                for path in [ROOT / "packages/runtime/pyproject.toml", *implementation]:
                    self.assertEqual(hashes[prefix + str(path.relative_to(ROOT))],
                                     hashlib.sha256(path.read_bytes()).hexdigest())
                legacy = "host.py" if prefix else "experiments/interop_d0/host.py"
                self.assertIn(legacy, hashes)

    def test_runtime_only_change_invalidates_each_snapshot(self):
        target = ROOT / "packages/runtime/src/meda_runtime/transport.py"
        read_bytes = Path.read_bytes

        def changed_bytes(path):
            original = read_bytes(path)
            return original + b"\n# simulated implementation change\n" if path == target else original

        for snapshot, prefix in self.snapshots():
            with self.subTest(snapshot=snapshot.__module__):
                before = snapshot()
                with patch.object(Path, "read_bytes", changed_bytes):
                    after = snapshot()
                self.assertEqual(before.keys(), after.keys())
                self.assertEqual([key for key in before if before[key] != after[key]],
                                 [prefix + str(target.relative_to(ROOT))])

    def test_runtime_inventory_excludes_generated_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = ["packages/runtime/pyproject.toml",
                        "packages/runtime/src/meda_runtime/host.py",
                        "packages/runtime/src/meda_runtime/nested/codec.py"]
            generated = ["packages/runtime/build/lib/meda_runtime/host.py",
                         "packages/runtime/src/meda_runtime/__pycache__/host.pyc",
                         "packages/runtime/src/meda_runtime.egg-info/PKG-INFO"]
            for name in expected + generated:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture")
            self.assertEqual({str(path.relative_to(root)) for path in freeze.runtime_source_paths(root)},
                             set(expected))


if __name__ == "__main__":
    unittest.main()
