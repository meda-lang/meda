"""Bounded Python control for the pure maintenance screening tasks.

Uses Python's real parser/runtime and the same acceptance values. No third-party
static checker is installed: report that asymmetry, never infer language superiority.
The AST allowlist narrows accidental effects; it is not a hostile-code sandbox.
"""
import ast
import json
from pathlib import Path
import subprocess
import sys

from meda_core import Diagnostic

ALLOWED = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
           ast.Assign, ast.AnnAssign, ast.AugAssign, ast.If, ast.For, ast.While,
           ast.Break, ast.Continue, ast.Pass, ast.Expr, ast.Assert,
           ast.Name, ast.Load, ast.Store, ast.Constant, ast.List, ast.Tuple, ast.Dict,
           ast.Subscript, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Call,
           ast.keyword, ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod,
           ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq,
           ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)
BUILTINS = {"len": len, "range": range, "sum": sum, "abs": abs,
            "min": min, "max": max, "int": int, "str": str, "bool": bool, "list": list}


def checked_tree(source):
    tree = ast.parse(source)
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    if len(names) != len(tree.body):
        raise Diagnostic("EditScope", "Control source contains only distinct functions.")
    for n in ast.walk(tree):
        if not isinstance(n, ALLOWED):
            raise Diagnostic("UnsupportedFeature", "Control AST node: " + type(n).__name__)
        if isinstance(n, ast.FunctionDef) and (n.decorator_list or n.args.posonlyargs or n.args.args or n.args.vararg or n.args.kwarg or n.args.defaults or any(x is not None for x in n.args.kw_defaults)):
            raise Diagnostic("EditScope", "Control functions require keyword-only explicit arguments.")
        if isinstance(n, ast.Name) and n.id.startswith("__"):
            raise Diagnostic("EditScope", "Reserved Python control name.")
        if isinstance(n, ast.Call) and (not isinstance(n.func, ast.Name) or n.func.id not in names | BUILTINS.keys()):
            raise Diagnostic("EditScope", "Only declared functions and pure control builtins may be called.")
    compile(tree, "<python-control>", "exec")
    return tree


def replace_body(source, symbol, body):
    tree = checked_tree(source)
    op = next((n for n in tree.body if n.name == symbol), None)
    if op is None:
        raise Diagnostic("EditScope", "Unknown control target.")
    lines = source.splitlines(keepends=True)
    prefix = "".join(lines[:op.body[0].lineno - 1])
    suffix = "".join(lines[op.end_lineno:])
    candidate = prefix + body.rstrip() + "\n" + suffix
    parsed = checked_tree(candidate)
    updated = next((n for n in parsed.body if n.name == symbol), None)
    old_mask, new_mask = ast.parse(source), ast.parse(candidate)
    for tr in (old_mask, new_mask):
        for fn in tr.body:
            if fn.name == symbol:
                fn.body = [ast.Pass()]
    if updated is None or ast.dump(old_mask, include_attributes=False) != ast.dump(new_mask, include_attributes=False):
        raise Diagnostic("EditScope", "Control edit changed an interface or another declaration.")
    return candidate


def evaluate(source, operation, arguments):
    command = [sys.executable, str(Path(__file__).resolve()), "--worker"]
    try:
        p = subprocess.run(command, input=json.dumps({"source":source,"operation":operation,"arguments":arguments}),
                           text=True, capture_output=True, timeout=2)
    except subprocess.TimeoutExpired:
        raise Diagnostic("WorkerTimeout", "Python control exceeded its worker deadline.", phase="runtime") from None
    if p.returncode != 0:
        raise Diagnostic("ControlFailure", "Python control worker failed.", phase="runtime")
    r = json.loads(p.stdout)
    if "error" in r:
        raise Diagnostic(r["error"], r["message"], phase="runtime")
    return r["value"]


def worker():
    # Defense in depth for this trusted harness. Kernel/container isolation is
    # required before exposing the worker to untrusted third parties.
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    request = json.loads(sys.stdin.read(256_000))
    try:
        tree = checked_tree(request["source"])
        scope = {"__builtins__": BUILTINS}
        exec(compile(tree, "<python-control>", "exec"), scope)
        value = scope[request["operation"]](**request["arguments"])
        print(json.dumps({"value":value}))
    except Exception as error:
        print(json.dumps({"error":type(error).__name__,"message":str(error)}))


if __name__ == "__main__":
    worker()
