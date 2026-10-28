"""Public entry point for a supervised evidence/report application process."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
from collections.abc import Sequence

from .host import Host, HostConfig
from .supervisor import MAX_LINE, _channel_scan, _contains_secret, _run_process, _scrub


def _json_input(value, depth=0):
    if depth > 16:
        raise ValueError("Application input exceeds the JSON depth limit")
    if type(value) is str:
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("Application input contains invalid Unicode")
        return
    if value is None or type(value) in (bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_input(item, depth + 1)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in (*value.keys(), *value.values()):
            _json_input(item, depth + 1)
        return
    raise ValueError("Application input must be finite JSON data")


def _command(command, cwd):
    if isinstance(command, (str, bytes)) or not isinstance(command, Sequence) or not command:
        raise ValueError("command must be a nonempty argument sequence")
    if any(type(arg) is not str or not arg or "\0" in arg for arg in command):
        raise ValueError("command arguments must be nonempty strings without NUL")
    command = list(command)
    if os.sep in command[0]:
        executable = Path(command[0])
        if not executable.is_absolute():
            executable = cwd / executable
        command[0] = str(executable.resolve())
    else:
        executable = shutil.which(command[0])
        if executable is None:
            raise ValueError("Application executable was not found")
        command[0] = executable
    if not Path(command[0]).is_file() or not os.access(command[0], os.X_OK):
        raise ValueError("Application executable is not executable")
    return command


def run_application(config: HostConfig, command: Sequence[str], input_value, *, cwd=None):
    """Run one application and return its final publication plus safe observations.

    The caller is trusted to select the executable, approved peers, grants and
    credentials. The child receives only finite JSON input and typed host results;
    it does not inherit credential variables or a Python import path. Linux RSS
    and wall-time supervision are containment aids, not an OS security sandbox.

    This public profile supports evidence revision 1. A successful application
    proposal becomes final only after worker exit and shared host cleanup.
    An application proposal containing a credential/reference sentinel is
    conservatively rejected before publication. Untrusted diagnostic channels
    are redacted; runtime-owned keys and outcomes retain their defined meaning.
    Scans observe sentinel occurrences, not proof of their causal origin.
    Prelaunch errors raise ValueError; failed process startup raises RuntimeError.
    Neither exception includes credential values or child command arguments.
    """
    if not isinstance(config, HostConfig):
        raise ValueError("config must be a HostConfig")
    if config.expected_revision != 1:
        raise ValueError("The public evidence/report profile requires revision 1")
    credentials = tuple(dict.fromkeys((config.mcp_token, config.a2a_token)))
    try:
        cwd = Path.cwd() if cwd is None else Path(cwd).resolve()
        if not cwd.is_dir():
            raise ValueError("Application working directory is unavailable")
        command = _command(command, cwd)
    except (OSError, TypeError, RuntimeError):
        raise ValueError("Application command or working directory is unavailable") from None
    _json_input(input_value)
    try:
        frame = json.dumps({"kind": "start", "input": input_value}, separators=(",", ":"),
                           allow_nan=False).encode() + b"\n"
    except (ValueError, UnicodeError, OverflowError):
        raise ValueError("Application input cannot be encoded as JSON") from None
    if len(frame) > MAX_LINE:
        raise ValueError("Application input exceeds the frame limit")
    # Credential delivery is never delegated to the worker's argv/input channels.
    if _contains_secret([command, input_value], credentials):
        raise ValueError("Credentials cannot be included in application arguments or input")
    private = {}
    try:
        host = Host(config)
    except Exception:
        raise ValueError("Runtime configuration could not be initialized") from None
    try:
        _run_process(host, input_value, command, cwd=cwd,
                     credential_sentinels=credentials, private_receipts=private,
                     _reject_output_secrets=True)
    except Exception:
        host.abort("RootTerminated")
        host.finish({"outcome": "RootTerminated", "fatal": True})
        raise RuntimeError("Application process could not be started or supervised") from None
    channels = dict(private["channels"])
    channels["ordinaryHostTrace"] = [json.dumps(row, ensure_ascii=False) for row in host.trace]
    scan = _channel_scan(channels, credentials, private["references"], private["complete"])
    # Accepted application data already passed the output policy. Runtime-owned
    # keys, enums and trace metadata are not derived from secret values, and must
    # not be rewritten when a credential happens to equal a control word.
    receipt = private["receipt"]
    for name in ("applicationFinish", "stderr", "unexpectedStdout"):
        receipt["worker"][name] = _scrub(receipt["worker"][name], [*credentials, *private["references"]])
    receipt["observedChannelScan"] = scan
    untrusted = [row for row in scan["channels"] if row["name"] != "ordinaryHostTrace"]
    receipt["credentialLeakDetected"] = any(row["credentialMatches"] for row in untrusted)
    receipt["referenceLeakDetected"] = any(row["referenceMatches"] for row in untrusted)
    receipt["profile"] = "meda-evidence-runtime/1"
    return receipt
