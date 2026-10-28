"""Run an application with trusted configuration and parent-only credentials."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

from . import HostConfig, Limits, run_application
from .supervisor import _decode_frame


def _read_json(path):
    with Path(path).open("rb") as stream:
        data = stream.read(65_537)
    if len(data) > 65_536:
        raise ValueError("file limit")
    return _decode_frame(data)


def load_config(path):
    """Resolve explicitly named credentials; literal tokens are not CLI input."""
    data = _read_json(path)
    if type(data) is not dict:
        raise ValueError("configuration")
    if {"mcp_token", "a2a_token"} & set(data):
        raise ValueError("literal credentials are unsupported")
    required = {"mcp_token_env", "a2a_token_env", "principal", "tenant", "allowed_documents"}
    if not required <= set(data):
        raise ValueError("explicit authority configuration required")
    for field in ("principal", "tenant"):
        if type(data[field]) is not str or not data[field]:
            raise ValueError("explicit authority identity required")
    for key in ("mcp_token", "a2a_token"):
        name = data.pop(key + "_env")
        if type(name) is not str or not name or name not in os.environ or not os.environ[name]:
            raise ValueError("credential environment variable unavailable")
        data[key] = os.environ[name]
    for key in ("grants", "allowed_documents"):
        if key in data:
            values = data[key]
            if type(values) is not list or not values or not all(type(value) is str and value for value in values):
                raise ValueError("authority configuration")
            if len(set(values)) != len(values):
                raise ValueError("duplicate authority entries")
            data[key] = frozenset(values)
    if "limits" in data:
        if type(data["limits"]) is not dict:
            raise ValueError("limits")
        data["limits"] = Limits(**data["limits"])
    return HostConfig(**data)


def main(argv=None):
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError("invalid command line")

    parser = Parser(description="Run a bounded evidence/report application")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    try:
        args = parser.parse_args(argv)
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        config = load_config(args.config)
        input_value = {} if args.input is None else _read_json(args.input)
    except Exception:
        print(json.dumps({"error": "ConfigurationInvalid"}), file=sys.stderr)
        return 2
    try:
        receipt = run_application(config, command, input_value)
    except ValueError:
        print(json.dumps({"error": "ApplicationInputInvalid"}), file=sys.stderr)
        return 2
    except Exception:
        print(json.dumps({"error": "ApplicationLaunchFailure"}), file=sys.stderr)
        return 3
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))
    return 0 if receipt["result"].get("outcome") == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
