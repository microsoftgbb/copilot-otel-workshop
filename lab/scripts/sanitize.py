#!/usr/bin/env python3
"""Make a collector archive safe to share: python3 sanitize.py IN.jsonl OUT.jsonl [--scenarios a,b,c]

- Keeps only the listed lab.scenario values (default: all).
- Replaces content-bearing attribute values with "[removed]" (keys stay, so `analyze.py leaks` still works).
- Replaces the pseudonymous user id and the skill, agent and MCP server names with placeholders.
- Replaces the provider's opaque response ids with short stand-ins (links between calls are kept).
- Aborts, writing nothing, if the output still contains your username, home directory,
  an email address or something that looks like a token.
Review the output before publishing it. This is a safety net, not a guarantee.
"""
import getpass
import json
import os
import re
import sys

CONTENT_KEYS = {"gen_ai.input.messages", "gen_ai.output.messages", "gen_ai.system_instructions",
                "gen_ai.tool.definitions", "gen_ai.tool.call.arguments", "gen_ai.tool.call.result",
                "github.copilot.tool.parameters.command", "github.copilot.tool.parameters.file_path"}
PLACEHOLDERS = {
    "enduser.pseudo.id": "00000000000000000000000000000001",
    "github.copilot.context.skills": '["example-skill-1","example-skill-2"]',
    "github.copilot.context.custom_agent_names": '["example-agent"]',
    "github.copilot.context.mcp_server_names": '["0000000000000000000000000000000000000000000000000000000000000001"]',
}
OPAQUE_ID_KEYS = {"gen_ai.response.id", "gen_ai.request.previous_response.id"}
_opaque = {}
SUSPICIOUS = [
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\b(ghp_|gho_|ghu_|ghs_|github_pat_)[A-Za-z0-9_]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{10,}"),
]


def scrub_attrs(attrs):
    for a in attrs or []:
        key = a["key"]
        if key in CONTENT_KEYS:
            a["value"] = {"stringValue": "[removed]"}
        elif key in PLACEHOLDERS:
            a["value"] = {"stringValue": PLACEHOLDERS[key]}
        elif key in OPAQUE_ID_KEYS:
            real = next(iter(a["value"].values()))
            a["value"] = {"stringValue": _opaque.setdefault(real, f"response-{len(_opaque) + 1:04d}")}


def scenario_of(rs):
    for a in rs["resource"]["attributes"]:
        if a["key"] == "lab.scenario":
            return next(iter(a["value"].values()))
    return None


def sanitize(path, keep):
    out = []
    with open(path) as fh:
        lines = fh.readlines()
    for line in lines:
        if not line.strip():
            continue
        doc = json.loads(line)
        for kind in ("resourceSpans", "resourceMetrics", "resourceLogs"):
            kept = [r for r in doc.get(kind, []) if keep is None or scenario_of(r) in keep]
            if kind in doc:
                doc[kind] = kept
        if not any(doc.get(k) for k in ("resourceSpans", "resourceMetrics", "resourceLogs")):
            continue
        for rs in doc.get("resourceSpans", []):
            scrub_attrs(rs["resource"]["attributes"])
            for ss in rs["scopeSpans"]:
                for s in ss["spans"]:
                    scrub_attrs(s.get("attributes"))
                    for e in s.get("events", []):
                        scrub_attrs(e.get("attributes"))
        out.append(json.dumps(doc, separators=(",", ":")))
    return out


def check(lines):
    text = "\n".join(lines)
    needles = {getpass.getuser(): "username", os.path.expanduser("~"): "home directory"}
    for needle, what in needles.items():
        if needle and len(needle) > 2 and needle in text:
            sys.exit(f"refusing to write: output still contains your {what}")
    for pat in SUSPICIOUS:
        m = pat.search(text)
        if m:
            sys.exit(f"refusing to write: output matches {pat.pattern[:30]}... ({m.group(0)[:20]}...)")


if __name__ == "__main__":
    args = sys.argv[1:]
    keep = None
    if "--scenarios" in args:
        i = args.index("--scenarios")
        keep = set(args[i + 1].split(","))
        del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    lines = sanitize(args[0], keep)
    check(lines)
    with open(args[1], "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} records to {args[1]}")
