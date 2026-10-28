"""Actual checked Meda source worker over the same JSONL bridge as TypeScript.

This module decodes input/frames and exports a result. Application sequencing
and domain validation live exclusively in workflow.meda.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.decision_screen.language import Program, Evaluator, export_value

MAX_FRAME = 65_536


def variant(case, **fields):
    return {"case": case, "fields": fields}


def ids(value):
    return (type(value) is list and len(value) <= 32 and
            all(type(item) is str and 0 < len(item) <= 256 and
                not any(0xD800 <= ord(c) <= 0xDFFF for c in item) for item in value) and
            len(set(value)) == len(value))


def decode_input(value):
    if type(value) is not dict or set(value) - {
        "documentId", "includeIds", "requestClarification", "suppliedInput", "cancelAfterSubmit"
    }:
        raise ValueError("input")
    document = value.get("documentId", "evidence-42")
    selected = value.get("includeIds", ["f1", "f2"])
    supplied = value.get("suppliedInput")
    if (type(document) is not str or not 0 < len(document) <= 256 or
            not ids(selected) or ("suppliedInput" in value and not ids(supplied)) or
            any(key in value and type(value[key]) is not bool
                for key in ("requestClarification", "cancelAfterSubmit"))):
        raise ValueError("input")
    return {"documentId": document, "includeIds": selected,
            "requestClarification": value.get("requestClarification", False),
            "cancelAfterSubmit": value.get("cancelAfterSubmit", False),
            "suppliedInput": variant("Omitted") if supplied is None else variant("Included", ids=supplied)}


def read_frame():
    line = sys.stdin.buffer.readline(MAX_FRAME + 1)
    if not line.endswith(b"\n") or len(line) > MAX_FRAME:
        raise ValueError("frame")
    return json.loads(line)


def emit(value):
    frame = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    if len(frame.encode()) + 1 > MAX_FRAME:
        raise ValueError("frame")
    print(frame, flush=True)


def publication(value):
    fields = value["fields"]
    if value["case"] == "Success":
        return {"outcome": "Success", "report": fields["report"]}
    if value["case"] == "Stopped":
        return {"outcome": fields["outcome"]}
    if value["case"] == "Error":
        error = fields["error"]
        return {"outcome": error["code"], "remoteOutcome": error["remoteOutcome"], "fatal": error["fatal"]}
    raise ValueError("application result")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path(__file__).with_name("workflow.meda"))
    args = parser.parse_args()
    request_id = 0

    def exchange(operation, arguments):
        nonlocal request_id
        request_id += 1
        emit({"kind": "call", "id": request_id, "operation": operation, "arguments": arguments})
        response = read_frame()
        if (type(response) is not dict or response.get("kind") != "response" or
                type(response.get("id")) is not int or response["id"] != request_id or "value" not in response):
            raise ValueError("response")
        return response["value"]

    evaluator = None
    try:
        source = args.source.read_text()
        if len(source.encode()) > 128_000:
            raise ValueError("source")
        program = Program(source)
        start = read_frame()
        if type(start) is not dict or start.get("kind") != "start":
            raise ValueError("start")
        input_value = decode_input(start.get("input"))
        evaluator = Evaluator(program, exchange=exchange)
        result = evaluator.invoke("runWorkflow", {"input": input_value})
        result = publication(export_value(result))
        evaluator.close()
        emit({"kind": "finish", "result": result})
        return 0
    except Exception as error:
        if evaluator is not None:
            evaluator.close()
        print(json.dumps({"diagnostic": getattr(error, "code", type(error).__name__)}), file=sys.stderr)
        emit({"kind": "finish", "result": {"outcome": "ProtocolRejected", "fatal": True,
              "remoteOutcome": "Unknown" if request_id else "NotStarted"}})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
