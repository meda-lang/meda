"""Compatibility alias for the canonical runtime package.

Historical experiments keep this import path. Installed consumers import
meda_runtime directly; only this source-tree shim knows the repository layout.
"""
from importlib import import_module
from pathlib import Path
import sys

_SOURCE = Path(__file__).resolve().parents[2] / "packages/runtime/src"
if str(_SOURCE) not in sys.path:
    sys.path.insert(0, str(_SOURCE))
_implementation = import_module("meda_runtime.host")
sys.modules[__name__] = _implementation
