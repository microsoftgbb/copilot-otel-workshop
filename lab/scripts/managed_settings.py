#!/usr/bin/env python3
"""Check and convert the `telemetry` block of a Copilot managed-settings.json. Python 3.8+, stdlib only.

  managed_settings.py validate FILE            lint the telemetry block (exit 1 on errors)
  managed_settings.py mdm FILE [--format reg]  show the telemetry settings as native MDM string values

The accepted keys come from the published reference (see VERIFICATION.md, M1). This is a
local lint, NOT the real validator: GitHub validates server-managed files itself and shows
problems under AI controls > Agents. Other keys in the file are not checked.
"""
import json
import sys

TELEMETRY_KEYS = {
    "enabled": bool,
    "endpoint": str,
    "protocol": str,
    "captureContent": bool,
    "lockCaptureContent": bool,
    "serviceName": str,
    "resourceAttributes": dict,
    "headers": dict,
}
PROTOCOLS = {"http/json", "http/protobuf"}
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")
REG_KEY = r"HKEY_LOCAL_MACHINE\SOFTWARE\Policies\GitHubCopilot"


def load(path):
    with open(path) as fh:
        return json.load(fh)


def lint(doc):
    """Return (errors, warnings) for the telemetry block."""
    errors, warnings = [], []
    tel = doc.get("telemetry")
    if tel is None:
        return ["no `telemetry` block found"], []
    if not isinstance(tel, dict):
        return ["`telemetry` must be an object"], []

    for key, value in tel.items():
        want = TELEMETRY_KEYS.get(key)
        if want is None:
            errors.append(f"unknown telemetry key `{key}` (supported: {', '.join(sorted(TELEMETRY_KEYS))})")
        elif not isinstance(value, want):
            errors.append(f"`{key}` must be {want.__name__}, got {type(value).__name__}")

    if tel.get("protocol") is not None and tel["protocol"] not in PROTOCOLS:
        errors.append(f"`protocol` must be one of {sorted(PROTOCOLS)}")
    endpoint = tel.get("endpoint")
    if tel.get("enabled") is True and not endpoint:
        errors.append("`enabled` is true but no `endpoint` is set")
    if isinstance(endpoint, str):
        if not endpoint.startswith(("http://", "https://")):
            errors.append("`endpoint` must start with http:// or https://")
        elif endpoint.startswith("http://") and not any(h in endpoint for h in LOCAL_HOSTS):
            warnings.append("`endpoint` is plain http:// on a non-local host: data and any bearer token are readable on the network")

    if tel.get("captureContent") is True:
        warnings.append("`captureContent` is true: prompts, tool output and system prompts will be exported (module 03)")
    if tel.get("captureContent") is not True and tel.get("lockCaptureContent") is not True:
        warnings.append("`lockCaptureContent` is not true: users may be able to turn content capture on")
    if isinstance(tel.get("resourceAttributes"), dict):
        for k, v in tel["resourceAttributes"].items():
            if not isinstance(v, str):
                warnings.append(f"resourceAttributes.{k} is not a string; OTel resource attributes are usually strings")
    headers = tel.get("headers")
    if isinstance(headers, dict):
        for name, value in headers.items():
            looks_placeholder = isinstance(value, str) and ("REPLACE" in value or "<" in value)
            if not looks_placeholder:
                warnings.append(
                    f"header `{name}` holds what looks like a real credential. A repo-hosted managed-settings file can be "
                    "readable by enterprise members and is delivered to every client (module 08)")
    return errors, warnings


def flatten(doc):
    """Native MDM representation: dot-separated keys, every value a string.
    Booleans, arrays and objects are stored as JSON text (per the deployment docs)."""
    rows = []
    for key, value in doc["telemetry"].items():
        if isinstance(value, bool):
            text = "true" if value else "false"
        elif isinstance(value, (dict, list)):
            text = json.dumps(value, separators=(",", ":"))
        else:
            text = str(value)
        rows.append((f"telemetry.{key}", text))
    return rows


def reg_escape(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def cmd_validate(path):
    errors, warnings = lint(load(path))
    for e in errors:
        print(f"ERROR   {e}")
    for w in warnings:
        print(f"WARNING {w}")
    if not errors and not warnings:
        print("OK")
    elif not errors:
        print("OK (with warnings)")
    return 1 if errors else 0


def cmd_mdm(path, fmt):
    doc = load(path)
    errors, _ = lint(doc)
    if errors:
        print("Refusing to convert; fix these first:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    rows = flatten(doc)
    if fmt == "reg":
        print("Windows Registry Editor Version 5.00\n")
        print(f"[{REG_KEY}]")
        for key, text in rows:
            print(f'"{key}"="{reg_escape(text)}"')
    else:
        print(f"{'key':<34}value (string)")
        for key, text in rows:
            print(f"{key:<34}{text}")
        print(f"\nWindows: REG_SZ under {REG_KEY}\nmacOS:   forced managed preferences, domain com.github.copilot")
    return 0


def main(argv):
    if len(argv) >= 3 and argv[1] == "validate":
        return cmd_validate(argv[2])
    if len(argv) >= 3 and argv[1] == "mdm":
        fmt = argv[argv.index("--format") + 1] if "--format" in argv else "table"
        return cmd_mdm(argv[2], fmt)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
