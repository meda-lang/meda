"""Small checked direct-call Meda profile over the existing D0 binding contract.

Application control flow uses the real Meda parser, checker, and evaluator. This
module supplies fixed binding types, monomorphic effect checks, and a private
reference boundary; it is not the full proposed module or effect system.
"""
from __future__ import annotations

import json
import math
from experiments.gates import meda_core as core

PROFILE = "meda-direct-screen/1"
EFFECTS = frozenset({"ReadEvidence", "SubmitTask", "ObserveTask", "ProvideInput", "CancelTask"})
SIGNATURES = {
    "host.readEvidence": ({"documentId": "Text"}, "EvidenceResult", "ReadEvidence"),
    "host.submit": ({"evidence": "Evidence", "selection": "Selection"}, "TaskResult", "SubmitTask"),
    "host.observe": ({"ref": "TaskRef"}, "TaskResult", "ObserveTask"),
    "host.provideInput": ({"ref": "TaskRef", "includeIds": "List<Text>"}, "TaskResult", "ProvideInput"),
    "host.cancel": ({"ref": "TaskRef"}, "TaskResult", "CancelTask"),
}
PRELUDE = '''
record Fact { id: Text, value: Text }
record Evidence { documentId: Text, revision: Int, facts: List<Fact> }
record Report { documentId: Text, revision: Int, selected: List<Fact> }
record HostError { code: Text, remoteOutcome: Text, fatal: Bool }
enum Selection { Omitted, Included { ids: List<Text> } }
enum EvidenceResult { Value { value: Evidence }, Error { error: HostError } }
enum TaskState { Submitted, Working, InputRequired, AuthRequired, Completed, Failed, Canceled, Rejected }
enum Artifact { Missing, Invalid, Value { report: Report } }
record Task { ref: TaskRef, state: TaskState, artifact: Artifact }
enum TaskResult { Value { task: Task }, DirectReply, Error { error: HostError } }
'''
ERROR_CODES = frozenset({"AuthorityDenied", "BindingChanged", "BudgetDenied", "Timeout",
    "ProtocolRejected", "ResponseLimit", "UnsupportedRemoteState", "TransportFailure",
    "RootTerminated", "InvalidReference", "CleanupFailure", "TaskNotCancelable"})
REMOTE_OUTCOMES = frozenset({"NotStarted", "Completed", "Unknown"})
TASK_STATES = frozenset({"Submitted", "Working", "InputRequired", "AuthRequired",
                         "Completed", "Failed", "Canceled", "Rejected"})


def variant(case, **fields):
    return {"case": case, "fields": fields}


class Program(core.Program):
    """Checked source using the fixed screen API, preserving original offsets."""

    def __init__(self, source):
        self.source = source
        self.p = core.Parser(source, allowed_effects=EFFECTS).parse()
        prelude = core.Parser(PRELUDE).parse()
        reserved = set(prelude.records) | set(prelude.enums) | {"TaskRef", "host"}
        declarations = set(self.p.records) | set(self.p.enums) | set(self.p.ops) | set(self.p.constants) | set(self.p.imports)
        if declarations & reserved:
            raise core.Diagnostic("ReservedBinding", "Cannot redefine fixed binding names: " + ", ".join(sorted(declarations & reserved)))
        self.p.records = dict(prelude.records, **self.p.records)
        self.p.enums = dict(prelude.enums, **self.p.enums)
        self.ops, self.records, self.enums = self.p.ops, self.p.records, self.p.enums
        self.dependencies, self.contract_roots = {}, {}
        self.check()

    def valid_type(self, ty):
        if ty == "TaskRef":
            return
        return super().valid_type(ty)

    def bind(self, env, name, ty, mutable, pos):
        if name == "host":
            raise core.Diagnostic("ReservedBinding", "The host binding namespace cannot be shadowed.", pos)
        return super().bind(env, name, ty, mutable, pos)

    def _effect_calls(self, nodes, allowed, owner):
        for node in core.walk(nodes):
            if node.kind != "call":
                continue
            full = core.path(node.args[0]) or ""
            operation = self.op_name(full)
            required = ({SIGNATURES[full][2]} if full in SIGNATURES else
                        set(self.ops[operation].effects) if operation in self.ops else set())
            if not required <= set(allowed):
                raise core.Diagnostic("EffectViolation", f"{owner} does not permit {', '.join(sorted(required - set(allowed)))}.", node.pos)

    def check(self):
        # Every call edge checks declared bounds. This also checks transitive
        # effects: a helper cannot hide effects from its callers or contracts.
        for op in self.ops.values():
            self._effect_calls(op.body, op.effects, op.name)
            self._effect_calls(op.contracts, (), op.name + " contract")
        for name, body in self.p.tests.items():
            self._effect_calls(body, (), "test " + name)
        super().check()

    def contains_ref(self, ty, seen=None):
        if ty == "TaskRef":
            return True
        if ty.startswith("List<"):
            return self.contains_ref(ty[5:-1], seen)
        seen = set() if seen is None else seen
        if ty in seen:
            return False
        seen = seen | {ty}
        fields = list(self.records.get(ty, {}).values())
        fields += [field for case in self.enums.get(ty, {}).values() for field in case.values()]
        return any(self.contains_ref(field, seen) for field in fields)

    def type_expr(self, node, env, expected=None, assertion=False):
        if node.kind == "call":
            full = core.path(node.args[0])
            if full in SIGNATURES:
                if assertion:
                    raise core.Diagnostic("EffectViolation", "Assertions and contracts must remain pure.", node.pos)
                params, output, _ = SIGNATURES[full]
                self.check_fields(node.args[1], params, env, assertion, node.pos)
                return output
            # An effectful user operation is also forbidden in an assertion,
            # even when the surrounding body's declared bound permits it.
            op = self.ops.get(self.op_name(full or ""))
            if assertion and op is not None and op.effects:
                raise core.Diagnostic("EffectViolation", "Assertions and contracts must remain pure.", node.pos)
        if node.kind == "binary" and node.args[0] in ("==", "!="):
            ty = self.type_expr(node.args[1], env, assertion=assertion)
            if self.contains_ref(ty):
                raise core.Diagnostic("OpaqueReference", "Task references have no equality or representation observer.", node.pos)
        return super().type_expr(node, env, expected, assertion)


class _TaskRef:
    """An inert application value. Authority exists only in a binding's table."""
    __slots__ = ()


def _text(value, *, nonempty=False):
    return (type(value) is str and len(value) <= 256 and
            (not nonempty or bool(value)) and not any(0xD800 <= ord(c) <= 0xDFFF for c in value))


def _fact(value):
    return (type(value) is dict and set(value) == {"id", "value"} and
            _text(value["id"], nonempty=True) and _text(value["value"]))


def _wire_int(value):
    # Protobuf Struct represents JSON numbers as doubles. The binding preserves
    # an integral JSON value as Meda Int; Python's int/float distinction must not
    # turn the SDK's 1.0 into an invalid report while TypeScript accepts it.
    if type(value) is int and abs(value) <= 1_000_000:
        return value
    if type(value) is float and math.isfinite(value) and value.is_integer() and abs(value) <= 1_000_000:
        return int(value)
    return None


def _report(value):
    return (type(value) is dict and set(value) == {"documentId", "revision", "selected"} and
            _text(value["documentId"]) and _wire_int(value["revision"]) is not None and
            type(value["selected"]) is list and
            len(value["selected"]) <= 32 and all(_fact(item) for item in value["selected"]))


def _error(value):
    if (type(value) is not dict or value.get("kind") != "Error" or
            type(value.get("code")) is not str or value["code"] not in ERROR_CODES or
            type(value.get("remoteOutcome")) is not str or value["remoteOutcome"] not in REMOTE_OUTCOMES or
            ("fatal" in value and type(value["fatal"]) is not bool)):
        return None
    return {"code": value["code"], "remoteOutcome": value["remoteOutcome"], "fatal": value.get("fatal", False)}


def _binding_error(code="ProtocolRejected", remote="Unknown", fatal=False):
    return variant("Error", error={"code": code, "remoteOutcome": remote, "fatal": fatal})


class Bindings:
    """Trusted bridge: raw host tokens never enter interpreted source values."""
    def __init__(self, exchange):
        self.exchange, self.active = exchange, True
        self._tokens, self._issued = {}, {}

    def owns(self, value):
        return self.active and type(value) is _TaskRef and value in self._tokens

    def close(self):
        self.active = False
        self._tokens.clear()
        self._issued.clear()

    def _task(self, raw):
        error = _error(raw)
        if error is not None:
            return variant("Error", error=error)
        if type(raw) is not dict:
            return _binding_error()
        if raw.get("kind") == "DirectReply":
            return variant("DirectReply")
        token, state = raw.get("ref"), raw.get("state")
        if (raw.get("kind") != "Task" or type(token) is not str or not token or len(token) > 1024 or
                type(state) is not str or state not in TASK_STATES):
            return _binding_error()
        ref = self._issued.get(token)
        if ref is None:
            ref = _TaskRef()
            self._issued[token] = ref
            self._tokens[ref] = token
        if "artifact" not in raw:
            artifact = variant("Missing")
        elif _report(raw["artifact"]):
            report = raw["artifact"]
            artifact = variant("Value", report={"documentId": report["documentId"], "revision": _wire_int(report["revision"]),
                                                "selected": [dict(fact) for fact in report["selected"]]})
        else:
            artifact = variant("Invalid")
        return variant("Value", task={"ref": ref, "state": variant(state), "artifact": artifact})

    def call(self, name, args):
        if not self.active:
            return _binding_error("InvalidReference", "NotStarted") if name in {"observe", "provideInput", "cancel"} else _binding_error("RootTerminated", "NotStarted", True)
        if name in {"observe", "provideInput", "cancel"}:
            if not self.owns(args["ref"]):
                return _binding_error("InvalidReference", "NotStarted")
            wire = {"ref": self._tokens[args["ref"]]}
            if name == "provideInput":
                wire["includeIds"] = args["includeIds"]
        elif name == "submit":
            wire = {"evidence": args["evidence"]}
            if args["selection"]["case"] == "Included":
                wire["includeIds"] = args["selection"]["fields"]["ids"]
        else:
            wire = args
        raw = self.exchange(name, wire)
        if name != "readEvidence":
            return self._task(raw)
        error = _error(raw)
        if error is not None:
            return variant("Error", error=error)
        value = raw.get("value") if type(raw) is dict and raw.get("kind") == "Evidence" else None
        if (type(value) is not dict or set(value) != {"documentId", "revision", "facts"} or
                value.get("documentId") != args["documentId"] or not _text(value.get("documentId"), nonempty=True) or
                type(value.get("revision")) is not int or value["revision"] != 1 or
                type(value.get("facts")) is not list or len(value["facts"]) > 32 or
                not all(_fact(item) for item in value["facts"]) or
                len({item["id"] for item in value["facts"]}) != len(value["facts"])):
            return _binding_error()
        return variant("Value", value={"documentId": value["documentId"], "revision": value["revision"],
                                       "facts": [dict(item) for item in value["facts"]]})


class Evaluator(core.Evaluator):
    def __init__(self, program, exchange, fuel=100_000):
        self.bindings = Bindings(exchange)
        super().__init__(program, fuel=fuel)

    def check_value(self, value, ty):
        if ty == "TaskRef":
            if not self.bindings.owns(value):
                raise core.Diagnostic("InvalidReference", "TaskRef is not owned by this active binding.", phase="input")
            return
        return super().check_value(value, ty)

    def expr(self, node, env):
        if node.kind == "call" and core.path(node.args[0]) in SIGNATURES:
            self.tick(node.pos)
            full = core.path(node.args[0])
            args = {label: self.expr(expr, env) for label, expr in node.args[1].items()}
            params, output, _ = SIGNATURES[full]
            for label, ty in params.items():
                self.check_value(args[label], ty)
            result = self.bindings.call(full.split(".")[1], args)
            self.check_value(result, output)
            return result
        return super().expr(node, env)

    def close(self):
        self.bindings.close()


def export_value(value, *, max_bytes=65_536):
    """Copy bounded JSON data; reject authority even inside nested containers."""
    def copy(item, depth=0):
        if depth > 16:
            raise core.Diagnostic("ExportLimit", "Export exceeds 16 container levels.", phase="runtime")
        if type(item) is _TaskRef:
            raise core.Diagnostic("OpaqueReference", "Task references cannot be exported.", phase="runtime")
        if item is None or type(item) in (str, int, bool):
            return item
        if type(item) is list:
            return [copy(child, depth + 1) for child in item]
        if type(item) is dict and all(type(key) is str for key in item):
            return {key: copy(child, depth + 1) for key, child in item.items()}
        raise core.Diagnostic("ExportType", "Only bounded JSON data may be exported.", phase="runtime")
    result = copy(value)
    try:
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeError, TypeError):
        raise core.Diagnostic("ExportType", "Value cannot be encoded as JSON.", phase="runtime") from None
    if len(encoded) > max_bytes:
        raise core.Diagnostic("ExportLimit", "Export exceeds the bridge frame limit.", phase="runtime")
    return result
