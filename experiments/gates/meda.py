#!/usr/bin/env python3
"""Outside-in CLI and JSON-lines editing endpoint for the research profile."""
import argparse
import json
from pathlib import Path
import sys

from meda_core import Diagnostic, Evaluator, Program, PROFILE, format_source, run_tests
from edit_protocol import Host, read_utf8


def emit(value):
    print(json.dumps(value, ensure_ascii=True, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "run", "test", "fmt", "describe", "edit"))
    parser.add_argument("source")
    parser.add_argument("--operation", default="main")
    parser.add_argument("--arguments", default="{}")
    parser.add_argument("--grant")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--fuel", type=int, default=100_000)
    args = parser.parse_args()
    source = ""
    try:
        source = read_utf8(args.source)
        if args.command == "edit":
            host = Host(args.source, args.grant)
            allowed = {"describe", "begin_edit", "replace_body", "validate_edit", "commit_edit", "transaction_status"}
            for line in sys.stdin:
                try:
                    if len(line) > 256_000:
                        raise Diagnostic("RequestLimit", "Request too large.", phase="edit")
                    request = json.loads(line)
                    if set(request) != {"method", "params"} or request["method"] not in allowed:
                        raise Diagnostic("ProtocolRequest", "Invalid method or request keys.", phase="edit")
                    result = getattr(host, request["method"])(**request["params"])
                    emit({"ok": True, "result": result})
                except Diagnostic as error:
                    emit({"ok": False, "diagnostic": error.json(read_utf8(args.source), str(Path(args.source).resolve()))})
                except (TypeError, ValueError, KeyError) as error:
                    emit({"ok": False, "diagnostic": Diagnostic("ProtocolRequest", str(error), phase="edit").json()})
            return 0
        if args.command == "fmt":
            formatted = format_source(source)
            if args.check:
                emit({"formatted": formatted == source})
                return 0 if formatted == source else 1
            sys.stdout.write(formatted)
            return 0
        program = Program(source)
        if args.command == "check":
            emit({"status": "checked", "profile": PROFILE, "operations": list(program.ops)})
        elif args.command == "test":
            result = run_tests(program, fuel=args.fuel)
            emit({"tests": result})
            return 0 if all(t["status"] == "pass" for t in result) else 1
        elif args.command == "describe":
            emit(Host(args.source, args.grant).describe(args.operation))
        else:
            value = Evaluator(program, args.fuel).invoke(args.operation, json.loads(args.arguments))
            emit({"value": value, "profile": PROFILE})
        return 0
    except Diagnostic as error:
        emit({"diagnostic": error.json(source, str(Path(args.source).resolve()))})
        return 3 if error.phase == "runtime" else 2
    except (OSError, ValueError, TypeError, RecursionError) as error:
        emit({"diagnostic": Diagnostic("InfrastructureFailure", str(error), phase="infrastructure").json(source)})
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
