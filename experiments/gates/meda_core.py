"""Executable pure Meda research profile; no eval, host effects, or provider calls.

This is an acceptance interpreter, not the planned Rust production compiler.
Unsupported edition features are rejected, never silently given Python semantics.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re

PROFILE = "meda-pure-b0/1"
MAX_SOURCE = 128_000
PRIMITIVES = {"Int", "Bool", "Text", "Unit"}
RESERVED = set("operation public module import as record enum effects require ensure let var if else while for in match return break continue assert discard true false unit result self examples test with and or implies".split()) | PRIMITIVES


class Diagnostic(Exception):
    def __init__(self, code, message, pos=0, phase="check"):
        super().__init__(message)
        self.code, self.message, self.pos, self.phase = code, message, pos, phase

    def json(self, source="", uri="memory:program"):
        prefix = source[:self.pos]
        line = prefix.count("\n")
        column = len(prefix.rsplit("\n", 1)[-1].encode("utf-16-le")) // 2
        return {"code": self.code, "message": self.message, "phase": self.phase,
                "severity": "error", "sourceUri": uri,
                "span": {"startByte": len(prefix.encode()), "endByte": len(prefix.encode())},
                "editor": {"line": line, "character": column},
                "revision": digest(source), "profile": PROFILE}


def digest(value):
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(value.encode()).hexdigest()


@dataclasses.dataclass
class Token:
    text: str
    pos: int
    end: int
    kind: str


@dataclasses.dataclass
class Node:
    kind: str
    args: object
    pos: int


@dataclasses.dataclass
class Operation:
    name: str
    params: dict
    output: str
    contracts: list
    body: list
    start: int
    body_start: int
    body_end: int


def lex(source):
    if len(source.encode()) > MAX_SOURCE:
        raise Diagnostic("SourceLimit", "Source exceeds research profile limit.", phase="parse")
    if "\r" in source.replace("\r\n", ""):
        raise Diagnostic("InvalidNewline", "Use LF or CRLF.", phase="parse")
    # Offsets refer to the original source, including CRLF and Unicode comments.
    pattern = re.compile(r'(?P<space>[ \t]+)|(?P<comment>//[^\r\n]*)|(?P<nl>\r?\n)|(?P<string>"(?:[^"\\\r\n]|\\[^\r\n])*")|(?P<int>[0-9](?:[0-9_]*[0-9])?)|(?P<id>[A-Za-z_][A-Za-z_0-9]*)|(?P<op>->|=>|==|!=|<=|>=|[{}()\[\],.:+*/%<>=!\-])')
    tokens, pos = [], 0
    while pos < len(source):
        m = pattern.match(source, pos)
        if not m:
            raise Diagnostic("InvalidToken", "Unexpected or unsupported token.", pos, "parse")
        kind, text = m.lastgroup, m.group()
        if kind not in ("space", "comment"):
            tokens.append(Token("\n" if kind == "nl" else text, pos, m.end(), kind))
        pos = m.end()
    tokens.append(Token("<eof>", len(source), len(source), "eof"))
    return tokens


class Parser:
    def __init__(self, source):
        self.source, self.tokens, self.i = source, lex(source), 0
        self.ops, self.records, self.enums, self.constants, self.tests, self.imports = {}, {}, {}, {}, {}, {}
        self.module = "main"

    @property
    def tok(self):
        return self.tokens[self.i]

    def take(self, text=None):
        t = self.tok
        if text is not None and t.text != text:
            raise Diagnostic("Syntax", f"Expected {text}, found {t.text}.", t.pos, "parse")
        self.i += 1
        return t

    def maybe(self, text):
        if self.tok.text == text:
            return self.take()
        return None

    def nl(self):
        while self.maybe("\n"):
            pass

    def end(self):
        if self.tok.text not in ("\n", "}", "<eof>"):
            raise Diagnostic("StatementBoundary", "Expected a newline or closing block.", self.tok.pos, "parse")
        self.nl()

    def name(self):
        t = self.take()
        if t.kind != "id" or t.text in RESERVED or t.text.startswith("__meda"):
            raise Diagnostic("ReservedName", "Expected a non-reserved identifier.", t.pos, "parse")
        return t.text

    def typ(self):
        t = self.take()
        if t.kind != "id":
            raise Diagnostic("Syntax", "Expected a type.", t.pos, "parse")
        if self.maybe("<"):
            inner = self.typ()
            self.take(">")
            return t.text + "<" + inner + ">"
        return t.text

    def fields(self, closing, types=False):
        fields = {}
        self.nl()
        while self.tok.text != closing:
            label = self.name()
            if label in fields:
                raise Diagnostic("DuplicateLabel", f"Duplicate label {label}.", self.tok.pos, "parse")
            self.take(":")
            self.nl()
            fields[label] = self.typ() if types else self.expr(multiline=True)
            self.nl()
            if not self.maybe(","):
                break
            self.nl()
        self.take(closing)
        return fields

    def parse(self):
        self.nl()
        if self.maybe("module"):
            self.module = self.name()
            self.end()
        seen = set()
        while self.tok.text != "<eof>":
            self.maybe("public")
            t = self.take()
            if t.text == "import":
                self.take("std")
                self.take(".")
                part = self.name()
                if part not in ("list", "text"):
                    raise Diagnostic("UnsupportedFeature", "Only std.list and std.text are implemented.", t.pos)
                self.take("as")
                alias = self.name()
                if alias in seen:
                    raise Diagnostic("DuplicateName", alias, t.pos)
                seen.add(alias)
                self.imports[alias] = part
            elif t.text == "record":
                name = self.name()
                self.nl()
                self.take("{")
                self.records[name] = self.fields("}", True)
            elif t.text == "enum":
                name = self.name()
                self.nl()
                self.take("{")
                self.nl()
                cases = {}
                while self.tok.text != "}":
                    case = self.name()
                    if case in cases:
                        raise Diagnostic("DuplicateName", case, self.tok.pos)
                    cases[case] = self.fields("}", True) if self.maybe("{") else {}
                    self.nl()
                    if not self.maybe(","):
                        break
                    self.nl()
                self.take("}")
                self.enums[name] = cases
            elif t.text == "operation":
                name = self.name()
                self.take("(")
                params = self.fields(")", True)
                self.nl()
                self.take("->")
                output = self.typ()
                self.nl()
                self.take("effects")
                self.take("[")
                if self.tok.text != "]":
                    raise Diagnostic("UnsupportedEffect", "This executable profile is pure.", self.tok.pos)
                self.take("]")
                self.nl()
                contracts = []
                while self.tok.text in ("require", "ensure"):
                    kind = self.take().text
                    contracts.append((kind, self.expr()))
                    self.take("\n")
                    self.nl()
                body_start = self.tok.pos
                body = self.block()
                self.ops[name] = Operation(name, params, output, contracts, body, t.pos, body_start, self.tokens[self.i-1].end)
            elif t.text == "let":
                name = self.name()
                self.take(":")
                ty = self.typ()
                self.take("=")
                self.constants[name] = (ty, self.expr())
            elif t.text == "test":
                title = self.take()
                if title.kind != "string":
                    raise Diagnostic("Syntax", "Test name must be quoted.", title.pos, "parse")
                name = decode_text(title)
                self.tests[name] = self.block()
            else:
                raise Diagnostic("UnsupportedFeature", f"Unsupported declaration {t.text}.", t.pos, "parse")
            if t.text != "import":
                if name in seen or name in self.imports:
                    raise Diagnostic("DuplicateName", name, t.pos)
                seen.add(name)
            self.end()
        return self

    def block(self):
        self.nl()
        self.take("{")
        self.nl()
        statements = []
        while self.tok.text not in ("}", "<eof>"):
            statements.append(self.statement())
            self.end()
        self.take("}")
        return statements

    def statement(self):
        t = self.tok
        if t.text in ("let", "var"):
            self.take()
            name = self.name()
            ty = self.typ() if self.maybe(":") else None
            self.take("=")
            return Node("bind", (name, ty, t.text == "var", self.expr()), t.pos)
        if t.text == "return":
            self.take()
            expr = Node("literal", (None, "Unit"), t.pos) if self.tok.text in ("\n", "}") else self.expr()
            return Node("return", expr, t.pos)
        if t.text in ("assert", "discard"):
            self.take()
            return Node(t.text, self.expr(), t.pos)
        if t.text in ("break", "continue"):
            return Node(self.take().text, None, t.pos)
        if t.text in ("if", "while"):
            self.take()
            cond = self.expr(head=True)
            body = self.block()
            other = []
            if t.text == "if":
                save = self.i
                self.nl()
                if self.maybe("else"):
                    other = [self.statement()] if self.tok.text == "if" else self.block()
                else:
                    self.i = save
            return Node(t.text, (cond, body, other), t.pos)
        if t.text == "for":
            self.take()
            name = self.name()
            self.take("in")
            items = self.expr(head=True)
            return Node("for", (name, items, self.block()), t.pos)
        if t.text == "match":
            self.take()
            value = self.expr(head=True)
            self.take("{")
            self.nl()
            arms = []
            while self.tok.text != "}":
                case = self.take().text
                if self.maybe("."):
                    case += "." + self.name()
                bindings = {}
                if self.maybe("("):
                    self.nl()
                    while self.tok.text != ")":
                        label = self.name()
                        self.take(":")
                        binding = self.name()
                        if label in bindings:
                            raise Diagnostic("DuplicateLabel", label, self.tok.pos)
                        bindings[label] = binding
                        if not self.maybe(","):
                            break
                        self.nl()
                    self.take(")")
                self.take("=>")
                arms.append((case, bindings, self.block()))
                self.nl()
            self.take("}")
            return Node("match", (value, arms), t.pos)
        if t.kind == "id" and self.tokens[self.i+1].text == "=":
            name = self.name()
            self.take("=")
            return Node("assign", (name, self.expr()), t.pos)
        return Node("expr", self.expr(), t.pos)

    PRECEDENCE = {"implies": 1, "or": 2, "and": 3, "==": 4, "!=": 4,
                  "<": 5, "<=": 5, ">": 5, ">=": 5, "+": 6, "-": 6,
                  "*": 7, "/": 7, "%": 7}

    def expr(self, minimum=0, multiline=False, head=False):
        if multiline:
            self.nl()
        t = self.take()
        if t.text in ("-", "!"):
            node = Node("unary", (t.text, self.expr(8, multiline, head)), t.pos)
        elif t.kind == "int":
            if "__" in t.text or t.text.endswith("_"):
                raise Diagnostic("InvalidInteger", "Underscores must separate digits.", t.pos, "parse")
            node = Node("literal", (int(t.text.replace("_", "")), "Int"), t.pos)
        elif t.kind == "string":
            node = Node("literal", (decode_text(t), "Text"), t.pos)
        elif t.text in ("true", "false", "unit"):
            node = Node("literal", ({"true": True, "false": False, "unit": None}[t.text], "Unit" if t.text == "unit" else "Bool"), t.pos)
        elif t.text == "(":
            node = self.expr(multiline=True)
            self.nl()
            self.take(")")
        elif t.text == "[":
            values = []
            self.nl()
            while self.tok.text != "]":
                values.append(self.expr(multiline=True))
                self.nl()
                if not self.maybe(","):
                    break
                self.nl()
            self.take("]")
            node = Node("list", values, t.pos)
        elif t.kind == "id" and (t.text not in RESERVED or t.text in ("result", "self")):
            node = Node("name", t.text, t.pos)
        else:
            raise Diagnostic("Syntax", f"Expected expression, found {t.text}.", t.pos, "parse")
        while True:
            if multiline:
                self.nl()
            op = self.tok.text
            if op == ".":
                self.take()
                node = Node("field", (node, self.name()), node.pos)
            elif op == "(":
                self.take()
                node = Node("call", (node, self.fields(")")), node.pos)
            elif op == "{" and node.kind == "name" and not head:
                self.take()
                node = Node("record", (node.args, self.fields("}")), node.pos)
            elif op == "with":
                self.take()
                self.take("{")
                node = Node("update", (node, self.fields("}")), node.pos)
            elif op in self.PRECEDENCE and self.PRECEDENCE[op] >= minimum:
                self.take()
                precedence = self.PRECEDENCE[op]
                if precedence in (4, 5) and node.kind == "binary" and self.PRECEDENCE[node.args[0]] in (4, 5):
                    raise Diagnostic("ChainedComparison", "Comparisons cannot chain.", node.pos, "parse")
                right = self.expr(precedence + (0 if op == "implies" else 1), multiline, head)
                node = Node("binary", (op, node, right), node.pos)
            else:
                break
        return node


def decode_text(token):
    text, result, index = token.text[1:-1], [], 0
    escapes = {'"': '"', "\\": "\\", "n": "\n", "r": "\r", "t": "\t"}
    try:
        while index < len(text):
            char = text[index]
            index += 1
            if char == "\\":
                escape = text[index]
                index += 1
                if escape in escapes:
                    char = escapes[escape]
                elif escape == "u" and text[index:index+1] == "{":
                    end = text.index("}", index)
                    spelling = text[index+1:end]
                    if not re.fullmatch(r"[0-9A-Fa-f]{1,6}", spelling):
                        raise ValueError("invalid scalar spelling")
                    scalar = int(spelling, 16)
                    if scalar > 0x10FFFF or 0xD800 <= scalar <= 0xDFFF:
                        raise ValueError("not a scalar")
                    char, index = chr(scalar), end + 1
                else:
                    raise ValueError("invalid escape")
            elif ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF:
                raise ValueError("invalid unescaped character")
            result.append(char)
        return "".join(result)
    except (ValueError, IndexError):
        raise Diagnostic("InvalidText", "Invalid text escape or Unicode scalar.", token.pos, "parse") from None


def walk(value):
    if isinstance(value, Node):
        yield value
        yield from walk(value.args)
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from walk(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk(item)


def path(node):
    if node.kind == "name":
        return node.args
    if node.kind == "field":
        base = path(node.args[0])
        return base + "." + node.args[1] if base else None
    return None


def require_equal(actual, expected, pos=0):
    if actual != expected:
        raise Diagnostic("TypeMismatch", f"Expected {expected}, found {actual}.", pos)


class Program:
    def __init__(self, source):
        self.source = source
        self.p = Parser(source).parse()
        self.ops, self.records, self.enums = self.p.ops, self.p.records, self.p.enums
        self.dependencies, self.contract_roots = {}, {}
        self.check()

    def valid_type(self, ty):
        if ty.startswith("List<") and ty.endswith(">"):
            return self.valid_type(ty[5:-1])
        if ty not in PRIMITIVES | self.records.keys() | self.enums.keys():
            raise Diagnostic("UnknownType", f"Unknown or unsupported type {ty}.")

    def builtin_name(self, name):
        bits = name.split(".")
        if len(bits) == 2 and bits[0] in self.p.imports:
            return self.p.imports[bits[0]] + "." + bits[1]
        return name if name == "range" else None

    def op_name(self, name):
        return name[5:] if name.startswith("self.") else name

    def check(self):
        env = {}
        for fields in self.records.values():
            for ty in fields.values():
                self.valid_type(ty)
        for cases in self.enums.values():
            for fields in cases.values():
                for ty in fields.values():
                    self.valid_type(ty)
        # Direct recursive records have no finite construction; list/enum indirection is allowed.
        def finite(name, stack):
            if name in stack:
                raise Diagnostic("InfiniteRecord", "Direct record cycle.")
            for ty in self.records.get(name, {}).values():
                if ty in self.records:
                    finite(ty, stack | {name})
        for name in self.records:
            finite(name, set())
        for name, (ty, expr) in self.p.constants.items():
            self.valid_type(ty)
            if any(n.kind in ("call", "name") for n in walk(expr)):
                raise Diagnostic("ConstantInitializer", "This profile requires literal constant expressions.", expr.pos)
            require_equal(self.type_expr(expr, env, ty), ty, expr.pos)
            env[name] = (ty, False, "global")
        self.globals = env
        for op in self.ops.values():
            for ty in list(op.params.values()) + [op.output]:
                self.valid_type(ty)
            local = dict(env)
            for name, ty in op.params.items():
                self.bind(local, name, ty, False, op.start)
            for kind, expr in op.contracts:
                contract_env = dict(local)
                if kind == "ensure":
                    contract_env["result"] = (op.output, False)
                require_equal(self.type_expr(expr, contract_env, assertion=True), "Bool", expr.pos)
            if not self.check_block(op.body, local, op.output):
                raise Diagnostic("MissingReturn", f"Operation {op.name} may fall through.", op.start)
            self.dependencies[op.name] = self.refs([op.body, op.contracts])
            for index, (_, expr) in enumerate(op.contracts):
                self.contract_roots[f"{op.name}:contract:{index}"] = self.refs(expr)
        for name, body in self.p.tests.items():
            self.check_block(body, dict(env), "Unit", test=True)
        for root, refs in self.contract_roots.items():
            for ref in refs:
                self.check_safe(ref, [], root)

    def bind(self, env, name, ty, mutable, pos):
        # Constants are module declarations; locals may share their names.
        if name in self.p.imports or (name in env and len(env[name]) != 3):
            raise Diagnostic("ShadowedBinding", f"Local binding {name} already exists.", pos)
        env[name] = (ty, mutable)

    def refs(self, value):
        refs = set()
        for n in walk(value):
            if n.kind == "call":
                name = self.op_name(path(n.args[0]) or "")
                if name in self.ops:
                    refs.add(name)
            if n.kind == "name" and n.args in self.p.constants:
                refs.add("constant:" + n.args)
            if n.kind == "field":
                full = path(n)
                if full and full.startswith("self.") and full[5:] in self.p.constants:
                    refs.add("constant:" + full[5:])
        return refs

    def check_safe(self, name, stack, root):
        if name.startswith("constant:"):
            return
        if name in stack:
            raise Diagnostic("ContractUnsafe", f"Contract {root} has a recursive dependency: {' -> '.join(stack+[name])}.")
        op = self.ops[name]
        if any(n.kind == "while" for n in walk([op.body, op.contracts])):
            raise Diagnostic("ContractUnsafe", f"Contract {root} depends on unbounded while in {name}.", op.start)
        for child in self.dependencies.get(name, set()):
            self.check_safe(child, stack + [name], root)

    def type_expr(self, node, env, expected=None, assertion=False):
        k, a, pos = node.kind, node.args, node.pos
        recur = lambda x, ty=None: self.type_expr(x, env, ty, assertion)
        if k == "literal":
            return a[1]
        if k == "name":
            if a in env:
                return env[a][0]
            raise Diagnostic("UnknownName", f"Unknown value {a}.", pos)
        if k == "list":
            inner = expected[5:-1] if expected and expected.startswith("List<") else None
            if not a and inner is None:
                raise Diagnostic("AmbiguousType", "Empty list needs an element type.", pos)
            for item in a:
                actual = recur(item, inner)
                if inner is None:
                    inner = actual
                require_equal(actual, inner, item.pos)
            return f"List<{inner}>"
        if k == "unary":
            ty = "Bool" if a[0] == "!" else "Int"
            require_equal(recur(a[1]), ty, pos)
            return ty
        if k == "binary":
            op, left, right = a
            if op == "implies" and not assertion:
                raise Diagnostic("ImpliesContext", "implies is restricted to contracts/assertions.", pos)
            lt = recur(left)
            rt = recur(right, lt)
            require_equal(rt, lt, pos)
            if op in ("and", "or", "implies"):
                require_equal(lt, "Bool", pos)
                return "Bool"
            if op in ("==", "!="):
                return "Bool"
            if op in ("<", "<=", ">", ">="):
                if lt not in ("Int", "Text"):
                    raise Diagnostic("TypeMismatch", "Ordering requires Int or Text.", pos)
                return "Bool"
            if lt != "Int" and not (lt == "Text" and op == "+"):
                raise Diagnostic("TypeMismatch", "Arithmetic requires Int; text supports + only.", pos)
            return lt
        if k == "record":
            name, fields = a
            if name not in self.records:
                raise Diagnostic("UnknownType", name, pos)
            self.check_fields(fields, self.records[name], env, assertion, pos)
            return name
        if k == "update":
            name = recur(a[0])
            if name not in self.records:
                raise Diagnostic("TypeMismatch", "Record update requires a record.", pos)
            for label, expr in a[1].items():
                if label not in self.records[name]:
                    raise Diagnostic("UnknownField", label, pos)
                require_equal(recur(expr, self.records[name][label]), self.records[name][label], pos)
            return name
        if k == "field":
            full = path(node)
            if full and full.startswith("self.") and full[5:] in self.p.constants:
                return self.p.constants[full[5:]][0]
            if full and "." in full:
                name, case = full.split(".", 1)
                if name in self.enums and name not in env:
                    if case not in self.enums[name] or self.enums[name][case]:
                        raise Diagnostic("InvalidCase", full, pos)
                    return name
            ty = recur(a[0])
            if ty not in self.records or a[1] not in self.records[ty]:
                raise Diagnostic("UnknownField", a[1], pos)
            return self.records[ty][a[1]]
        if k == "call":
            full, args = path(a[0]), a[1]
            if full is None:
                raise Diagnostic("UnsupportedFeature", "Indirect calls are a later profile.", pos)
            first = full.split(".")[0]
            if first in env and first not in self.p.constants:
                raise Diagnostic("NotCallable", first, pos)
            name = self.op_name(full)
            if name in self.ops:
                op = self.ops[name]
                self.check_fields(args, op.params, env, assertion, pos)
                return op.output
            if "." in full:
                en, case = full.split(".", 1)
                if en in self.enums:
                    if case not in self.enums[en]:
                        raise Diagnostic("InvalidCase", full, pos)
                    self.check_fields(args, self.enums[en][case], env, assertion, pos)
                    return en
            builtin = self.builtin_name(full)
            if builtin == "range":
                self.check_fields(args, {"start": "Int", "end": "Int", "step": "Int"}, env, assertion, pos)
                return "Range"
            if builtin == "text.length":
                self.check_fields(args, {"value": "Text"}, env, assertion, pos)
                return "Int"
            if builtin in ("list.length", "list.append"):
                labels = {"items"} if builtin == "list.length" else {"items", "value"}
                if set(args) != labels:
                    raise Diagnostic("ArgumentLabels", f"Expected {sorted(labels)}.", pos)
                ty = recur(args["items"], expected if expected and expected.startswith("List<") else None)
                if not ty.startswith("List<"):
                    raise Diagnostic("TypeMismatch", "Expected List.", pos)
                if builtin == "list.append":
                    require_equal(recur(args["value"], ty[5:-1]), ty[5:-1], pos)
                    return ty
                return "Int"
            raise Diagnostic("UnknownOperation", full, pos)
        raise Diagnostic("UnsupportedFeature", k, pos)

    def check_fields(self, args, params, env, assertion, pos):
        if set(args) != set(params):
            raise Diagnostic("ArgumentLabels", f"Expected labels {sorted(params)}, found {sorted(args)}.", pos)
        for label, expr in args.items():
            require_equal(self.type_expr(expr, env, params[label], assertion), params[label], expr.pos)

    def check_block(self, body, env, output, loop=False, test=False):
        terminal = False
        for s in body:
            k, a, pos = s.kind, s.args, s.pos
            expr = lambda x, ty=None, assertion=False: self.type_expr(x, env, ty, assertion)
            if terminal:
                raise Diagnostic("Unreachable", "Statement follows a terminal statement.", pos)
            if k == "bind":
                name, ty, mut, value = a
                if ty:
                    self.valid_type(ty)
                actual = expr(value, ty)
                if ty:
                    require_equal(actual, ty, pos)
                self.bind(env, name, actual, mut, pos)
            elif k == "assign":
                name, value = a
                if name not in env or not env[name][1]:
                    raise Diagnostic("ImmutableBinding", name, pos)
                require_equal(expr(value, env[name][0]), env[name][0], pos)
            elif k == "return":
                require_equal(expr(a, output), output, pos)
                terminal = True
            elif k == "assert":
                require_equal(expr(a, assertion=True), "Bool", pos)
            elif k in ("expr", "discard"):
                expr(a)
            elif k in ("if", "while"):
                cond, branch, other = a
                require_equal(expr(cond), "Bool", pos)
                left = self.check_block(branch, dict(env), output, loop or k == "while", test)
                right = self.check_block(other, dict(env), output, loop, test)
                terminal = k == "if" and left and right
            elif k == "for":
                name, items, branch = a
                ty = expr(items)
                if ty != "Range" and not ty.startswith("List<"):
                    raise Diagnostic("TypeMismatch", "for requires List or Range.", pos)
                nested = dict(env)
                self.bind(nested, name, "Int" if ty == "Range" else ty[5:-1], False, pos)
                self.check_block(branch, nested, output, True, test)
            elif k in ("break", "continue"):
                if not loop:
                    raise Diagnostic("LoopControl", "No enclosing loop.", pos)
                terminal = True
            elif k == "match":
                value, arms = a
                ty = expr(value)
                covered, all_terminal = set(), True
                for case, bindings, branch in arms:
                    if case in covered or "_" in covered:
                        raise Diagnostic("UnreachablePattern", case, pos)
                    nested = dict(env)
                    if case == "_":
                        fields = {}
                    elif ty == "Bool" and case in ("true", "false"):
                        fields = {}
                    elif ty in self.enums and case.startswith(ty + ".") and case[len(ty)+1:] in self.enums[ty]:
                        fields = self.enums[ty][case[len(ty)+1:]]
                    else:
                        raise Diagnostic("InvalidPattern", case, pos)
                    if set(bindings) != set(fields):
                        raise Diagnostic("ArgumentLabels", "Pattern must name all payload fields.", pos)
                    for field, name in bindings.items():
                        if name != "_":
                            self.bind(nested, name, fields[field], False, pos)
                    covered.add(case)
                    all_terminal = self.check_block(branch, nested, output, loop, test) and all_terminal
                required = {"true", "false"} if ty == "Bool" else {ty + "." + c for c in self.enums.get(ty, {})}
                if "_" not in covered and (not required or covered != required):
                    raise Diagnostic("NonExhaustiveMatch", "Missing match cases.", pos)
                terminal = all_terminal and bool(arms)
        return terminal

    def closure(self, refs):
        result, todo = set(), list(refs)
        while todo:
            name = todo.pop()
            if name not in result:
                result.add(name)
                todo.extend(self.dependencies.get(name, ()))
        return result

    def specification(self):
        snapshots = {}
        for root, refs in self.contract_roots.items():
            op_name, _, index = root.split(":")
            closure = self.closure(refs)
            pieces = {"contract": self.source_expr(self.ops[op_name].contracts[int(index)][1]),
                      "definitions": {name: self.definition(name) for name in sorted(closure)},
                      "types": [self.records, self.enums], "profile": PROFILE}
            snapshots[root] = {"digest": digest(pieces), "dependencies": sorted(closure)}
        return snapshots

    def source_expr(self, node):
        # AST serialization excludes offsets: moving code is not a semantic edit.
        def clean(x):
            if isinstance(x, Node):
                return [x.kind, clean(x.args)]
            if isinstance(x, (list, tuple)):
                return [clean(v) for v in x]
            if isinstance(x, dict):
                return {k: clean(v) for k, v in x.items()}
            return x
        return clean(node)

    def definition(self, name):
        if name.startswith("constant:"):
            ty, value = self.p.constants[name[9:]]
            return [ty, self.source_expr(value)]
        op = self.ops[name]
        return [op.params, op.output, self.source_expr(op.contracts), self.source_expr(op.body)]


class Return(Exception):
    def __init__(self, value):
        self.value = value


class LoopSignal(Exception):
    def __init__(self, kind):
        self.kind = kind


class Evaluator:
    def __init__(self, program, fuel=100_000):
        self.program, self.fuel, self.depth = program, fuel, 0
        self.globals = {}
        for name, (_, expr) in program.p.constants.items():
            self.globals[name] = self.expr(expr, {})

    def tick(self, pos=0):
        self.fuel -= 1
        if self.fuel < 0:
            raise Diagnostic("FuelExhausted", "Research evaluator fuel exhausted.", pos, "runtime")

    def bounded(self, value, pos):
        if type(value) is int and value.bit_length() > 16384:
            raise Diagnostic("ResourceLimit", "Research integer limit exceeded.", pos, "runtime")
        if isinstance(value, (str, list, dict)) and len(value) > 100_000:
            raise Diagnostic("ResourceLimit", "Research value limit exceeded.", pos, "runtime")
        return value

    def invoke(self, name, args):
        if name not in self.program.ops:
            raise Diagnostic("UnknownOperation", name)
        op = self.program.ops[name]
        if set(args) != set(op.params):
            raise Diagnostic("ArgumentLabels", "Invocation labels do not match.")
        for label, ty in op.params.items():
            self.check_value(args[label], ty)
        return self.call(name, args)

    def check_value(self, value, ty):
        if ty in PRIMITIVES:
            valid = type(value) is {"Int": int, "Bool": bool, "Text": str, "Unit": type(None)}[ty]
            if valid and ty == "Text":
                valid = not any(0xD800 <= ord(c) <= 0xDFFF for c in value)
        elif ty.startswith("List<"):
            valid = type(value) is list
            if valid:
                for item in value:
                    self.check_value(item, ty[5:-1])
        elif ty in self.program.records:
            fields = self.program.records[ty]
            valid = type(value) is dict and set(value) == set(fields)
            if valid:
                for label, field_ty in fields.items():
                    self.check_value(value[label], field_ty)
        elif ty in self.program.enums:
            valid = type(value) is dict and set(value) == {"case", "fields"} and value["case"] in self.program.enums[ty]
            if valid:
                fields = self.program.enums[ty][value["case"]]
                valid = type(value["fields"]) is dict and set(value["fields"]) == set(fields)
                if valid:
                    for label, field_ty in fields.items():
                        self.check_value(value["fields"][label], field_ty)
        else:
            valid = False
        if not valid:
            raise Diagnostic("InputType", f"Input does not match {ty}.", phase="input")
        self.bounded(value, 0)

    def call(self, name, args):
        self.tick()
        self.depth += 1
        if self.depth > 80:
            raise Diagnostic("ResourceLimit", "Research call depth exceeded.", phase="runtime")
        op = self.program.ops[name]
        env = dict(self.globals, **args)
        try:
            self.contracts(op, "require", env)
            try:
                self.block(op.body, env)
            except Return as returned:
                env = dict(self.globals, **args, result=returned.value)
                self.contracts(op, "ensure", env)
                return returned.value
            raise Diagnostic("MissingReturn", name, op.start, "runtime")
        finally:
            self.depth -= 1

    def contracts(self, op, kind, env):
        for clause, expr in op.contracts:
            if clause != kind:
                continue
            try:
                passed = self.expr(expr, env)
            except Diagnostic as fault:
                if fault.code in ("FuelExhausted", "ResourceLimit"):
                    raise
                raise Diagnostic("ContractEvaluationFault", fault.code, expr.pos, "runtime") from None
            if not passed:
                raise Diagnostic("ContractViolation", f"{kind} failed in {op.name}.", expr.pos, "runtime")

    def expr(self, n, env):
        self.tick(n.pos)
        k, a = n.kind, n.args
        ev = lambda x: self.expr(x, env)
        if k == "literal":
            value = a[0]
        elif k == "name":
            value = env[a]
        elif k == "list":
            value = [ev(x) for x in a]
        elif k == "record":
            value = {key: ev(expr) for key, expr in a[1].items()}
        elif k == "update":
            value = dict(ev(a[0]))
            value.update({key: ev(expr) for key, expr in a[1].items()})
        elif k == "field":
            full = path(n)
            if full and full.startswith("self.") and full[5:] in self.globals:
                value = self.globals[full[5:]]
            elif full and full.split(".")[0] in self.program.enums and full.split(".")[0] not in env:
                value = {"case": full.split(".")[1], "fields": {}}
            else:
                value = ev(a[0])[a[1]]
        elif k == "unary":
            value = not ev(a[1]) if a[0] == "!" else -ev(a[1])
        elif k == "binary":
            op, left, right = a
            l = ev(left)
            if op == "and":
                return l and ev(right)
            if op == "or":
                return l or ev(right)
            if op == "implies":
                return not l or ev(right)
            r = ev(right)
            if op in ("/", "%"):
                if r == 0:
                    raise Diagnostic("NumericFault", "Division by zero.", n.pos, "runtime")
                q = (abs(l) // abs(r)) * (-1 if (l < 0) != (r < 0) else 1)
                value = q if op == "/" else l - q * r
            else:
                value = {"+": lambda: l+r, "-": lambda: l-r, "*": lambda: l*r,
                         "==": lambda: l == r, "!=": lambda: l != r, "<": lambda: l < r,
                         "<=": lambda: l <= r, ">": lambda: l > r, ">=": lambda: l >= r}[op]()
        elif k == "call":
            full = path(a[0])
            args = {label: ev(expr) for label, expr in a[1].items()}
            name = self.program.op_name(full)
            if name in self.program.ops:
                value = self.call(name, args)
            elif full.split(".")[0] in self.program.enums:
                value = {"case": full.split(".")[1], "fields": args}
            else:
                builtin = self.program.builtin_name(full)
                if builtin == "range":
                    if args["step"] == 0:
                        raise Diagnostic("NumericFault", "Range step is zero.", n.pos, "runtime")
                    value = range(args["start"], args["end"], args["step"])
                elif builtin == "list.append":
                    value = args["items"] + [args["value"]]
                else:
                    value = len(args["items"] if builtin == "list.length" else args["value"])
        else:
            raise Diagnostic("UnsupportedFeature", k, n.pos, "runtime")
        return self.bounded(value, n.pos)

    def branch(self, body, env, bindings=None):
        nested = dict(env)
        nested.update(bindings or {})
        declared = {s.args[0] for s in body if s.kind == "bind"}
        try:
            self.block(body, nested)
        finally:
            # The checker has excluded local shadowing; reassignment propagates outward.
            for name in env:
                if name not in declared and (not bindings or name not in bindings):
                    env[name] = nested[name]

    def block(self, body, env):
        for s in body:
            self.tick(s.pos)
            k, a = s.kind, s.args
            if k == "bind":
                env[a[0]] = self.expr(a[3], env)
            elif k == "assign":
                env[a[0]] = self.expr(a[1], env)
            elif k == "return":
                raise Return(self.expr(a, env))
            elif k == "assert":
                if not self.expr(a, env):
                    raise Diagnostic("AssertionFailed", "Assertion is false.", s.pos, "runtime")
            elif k in ("expr", "discard"):
                self.expr(a, env)
            elif k == "if":
                self.branch(a[1] if self.expr(a[0], env) else a[2], env)
            elif k == "while":
                while self.expr(a[0], env):
                    try:
                        self.branch(a[1], env)
                    except LoopSignal as signal:
                        if signal.kind == "break":
                            break
            elif k == "for":
                for item in self.expr(a[1], env):
                    self.tick(s.pos)
                    try:
                        self.branch(a[2], env, {a[0]: item})
                    except LoopSignal as signal:
                        if signal.kind == "break":
                            break
            elif k in ("break", "continue"):
                raise LoopSignal(k)
            elif k == "match":
                value = self.expr(a[0], env)
                for case, bindings, branch in a[1]:
                    matches = case == "_" or (type(value) is bool and case == str(value).lower()) or (type(value) is dict and case.split(".")[-1] == value.get("case"))
                    if matches:
                        bound = {name: value["fields"][label] for label, name in bindings.items() if name != "_"}
                        self.branch(branch, env, bound)
                        break


def run_tests(program, required=None, fuel=100_000):
    names = list(program.p.tests)
    if not names or (required is not None and set(names) != set(required)):
        raise Diagnostic("TestDiscovery", "Required nonempty test set does not match discovery.", phase="test")
    results = []
    for name in names:
        ev = Evaluator(program, fuel)
        try:
            try:
                ev.block(program.p.tests[name], dict(ev.globals))
            except Return:
                pass
            results.append({"id": name, "status": "pass"})
        except Diagnostic as error:
            results.append({"id": name, "status": "fail", "code": error.code})
    return results


def format_source(source):
    """Profile formatter: LF, structural indentation, final newline; preserves tokens/comments.

    Full edition line wrapping/trailing commas are intentionally not implemented.
    """
    Parser(source).parse()
    tokens = lex(source)
    by_line = {}
    for t in tokens:
        by_line.setdefault(source[:t.pos].count("\n"), []).append(t)
    depth, output = 0, []
    for index, line in enumerate(source.replace("\r\n", "\n").splitlines()):
        ts = [t.text for t in by_line.get(index, []) if t.kind not in ("nl", "eof")]
        leading = 1 if ts and ts[0] in ("}", "]", ")") else 0
        text = line.strip()
        output.append("  " * max(0, depth-leading) + text if text else "")
        depth += sum(t in ("{", "[", "(") for t in ts) - sum(t in ("}", "]", ")") for t in ts)
    return "\n".join(output).rstrip() + "\n"
