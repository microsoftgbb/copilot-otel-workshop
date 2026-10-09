#!/usr/bin/env python3
"""Search a collector archive (OTLP/JSON lines) without any backend. Python 3.8+, stdlib only.

  analyze.py inventory FILE   every span, span event, metric and attribute actually present
  analyze.py sessions  FILE   one row per agent session: model calls, tools, tokens, AI credits
  analyze.py summary   FILE   team view: sessions, distinct users, credits by model, shell failure rate
  analyze.py tools     FILE   tool usage, latency and non-zero shell exits
  analyze.py startup   FILE   SDK-hosted sessions: slowest start-up phases (session.timing.*)
  analyze.py leaks     FILE   audit: which content-bearing or identifying attributes were exported

The input is the OTLP/JSON archive written by the lab collector, not the CLI's own file
exporter (COPILOT_OTEL_FILE_EXPORTER_PATH), which uses a different format.
Rows are labelled "<service.name>/<lab.scenario>"; scenario falls back to service.instance.id.
"""
import collections
import json
import sys


def kv(attrs):
    return {a["key"]: next(iter(a["value"].values())) for a in attrs or []}


def read(path):
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def label(res):
    name = res.get("service.name", "?")
    scenario = res.get("lab.scenario") or res.get("service.instance.id")
    return f"{name}/{scenario}" if scenario else name


def spans(path):
    for doc in read(path):
        for rs in doc.get("resourceSpans", []):
            res = kv(rs["resource"]["attributes"])
            for ss in rs["scopeSpans"]:
                for s in ss["spans"]:
                    yield res, s, kv(s.get("attributes"))


def dur_s(s):
    return (int(s["endTimeUnixNano"]) - int(s["startTimeUnixNano"])) / 1e9


def credits(a):
    """github.copilot.nano_aiu is AI credits in billionths."""
    return int(a.get("github.copilot.nano_aiu", 0)) / 1e9


def inventory(path):
    names, attrs, events, resattrs = collections.Counter(), collections.defaultdict(set), collections.Counter(), set()
    for res, s, a in spans(path):
        op = s["name"].split(" ")[0]
        names[op] += 1
        attrs[op] |= set(a)
        resattrs |= set(res)
        for e in s.get("events", []):
            events[e["name"]] += 1
    metrics = {}
    for doc in read(path):
        for rm in doc.get("resourceMetrics", []):
            for sm in rm["scopeMetrics"]:
                for m in sm["metrics"]:
                    kind = next(k for k in ("sum", "histogram", "gauge") if k in m)
                    dims = set()
                    for p in m[kind]["dataPoints"]:
                        dims |= set(kv(p.get("attributes")))
                    metrics[m["name"]] = (kind, m.get("unit", ""), sorted(dims))
    print("RESOURCE ATTRIBUTES:", ", ".join(sorted(resattrs)))
    for op, n in names.items():
        print(f"\nSPAN {op} (x{n})\n  " + "\n  ".join(sorted(attrs[op])))
    print("\nSPAN EVENTS:", dict(events))
    print("\nMETRICS")
    for n, (k, u, d) in sorted(metrics.items()):
        print(f"  {n}  [{k} {u}]  dims={d}")


def sessions(path):
    rows = collections.defaultdict(collections.Counter)
    who = {}
    for res, s, a in spans(path):
        sid = a.get("gen_ai.conversation.id")
        if sid is None:  # session.timing.* start-up spans carry no conversation id
            continue
        op = a.get("gen_ai.operation.name")
        r = rows[sid]
        who[sid] = label(res)
        if op == "chat":
            r["model_calls"] += 1
            r["in"] += int(a.get("gen_ai.usage.input_tokens", 0))
            r["out"] += int(a.get("gen_ai.usage.output_tokens", 0))
            r["cached"] += int(a.get("gen_ai.usage.cache_read.input_tokens", 0))
        elif op == "execute_tool":
            r["tool_calls"] += 1
        elif op == "invoke_agent":
            r["credits_nano"] += int(a.get("github.copilot.nano_aiu", 0))
            r["wall_ms"] += int(dur_s(s) * 1000)
    print(f"{'service/scenario':<30}{'session':<10}{'calls':>6}{'tools':>6}{'in':>9}{'cached':>9}{'out':>7}{'credits':>9}{'secs':>7}")
    for sid, r in rows.items():
        print(f"{who[sid]:<30}{sid[:8]:<10}{r['model_calls']:>6}{r['tool_calls']:>6}{r['in']:>9}{r['cached']:>9}{r['out']:>7}"
              f"{r['credits_nano'] / 1e9:>9.2f}{r['wall_ms'] / 1000:>7.1f}")


def summary(path):
    sess, users = set(), set()
    runs, secs, cred = collections.Counter(), collections.Counter(), collections.Counter()
    by_model, shell, shell_bad, tools_n = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    for res, s, a in spans(path):
        if a.get("gen_ai.conversation.id") is None:
            continue
        h = res.get("service.name", "?")
        op = a.get("gen_ai.operation.name")
        sess.add((h, a["gen_ai.conversation.id"]))
        if op == "invoke_agent":
            runs[h] += 1
            secs[h] += dur_s(s)
            cred[h] += credits(a)
            if a.get("enduser.pseudo.id"):
                users.add((h, a["enduser.pseudo.id"]))
        elif op == "chat":
            by_model[(h, a.get("gen_ai.request.model", "?"))] += credits(a)
        elif op == "execute_tool":
            tools_n[h] += 1
            if a.get("process.executable.name"):
                shell[h] += 1
                if a.get("process.exit.code") not in (None, "0", 0):
                    shell_bad[h] += 1
    print(f"{'service':<20}{'sessions':>9}{'users*':>8}{'runs':>6}{'credits':>9}{'avg_s':>8}{'tools':>7}{'shell':>7}{'shell_fail':>11}")
    for h in sorted(runs):
        n = sum(1 for x in sess if x[0] == h)
        u = sum(1 for x in users if x[0] == h)
        print(f"{h:<20}{n:>9}{u:>8}{runs[h]:>6}{cred[h]:>9.2f}{secs[h] / runs[h]:>8.1f}{tools_n[h]:>7}{shell[h]:>7}{shell_bad[h]:>11}")
    print("\nCredits by model (sum of chat spans):")
    for (h, m), c in sorted(by_model.items(), key=lambda item: -item[1]):
        print(f"  {h:<20}{m:<24}{c:>8.2f}")
    print("\n* users = distinct enduser.pseudo.id: pseudonymous, and only as complete as your instrumented clients.")


def tools(path):
    agg = collections.defaultdict(list)
    bad = []
    for res, s, a in spans(path):
        if a.get("gen_ai.operation.name") != "execute_tool":
            continue
        name = a.get("gen_ai.tool.name", "?")
        agg[name].append(dur_s(s))
        code = a.get("process.exit.code")
        if code not in (None, "0", 0):
            bad.append((label(res), name, code))
    print(f"{'tool':<20}{'calls':>6}{'avg_s':>9}{'max_s':>9}")
    for n, d in sorted(agg.items(), key=lambda item: -len(item[1])):
        print(f"{n:<20}{len(d):>6}{sum(d) / len(d):>9.3f}{max(d):>9.3f}")
    print("\nNon-zero shell exits (the tool itself still reports success=true):")
    for who, name, code in bad or [("-", "none", "-")]:
        print(f"  {who} tool={name} exit={code}")


def startup(path):
    phases = []
    for res, s, a in spans(path):
        if s["name"].startswith("session.timing."):
            phases.append((float(a.get("github.copilot.session.timing.duration_ms", 0)),
                           a.get("github.copilot.session.timing.phase", s["name"]),
                           label(res)))
    if not phases:
        print("No session.timing.* spans in this archive (they appear for SDK-hosted sessions).")
        return
    print(f"{len(phases)} start-up phase spans. Slowest 10:")
    for ms, phase, who in sorted(phases, reverse=True)[:10]:
        print(f"  {ms:>8.0f} ms  {phase:<45} {who}")


CONTENT_KEYS = ("gen_ai.input.messages", "gen_ai.output.messages", "gen_ai.system_instructions",
                "gen_ai.tool.definitions", "gen_ai.tool.call.arguments", "gen_ai.tool.call.result",
                "github.copilot.tool.parameters.command", "github.copilot.tool.parameters.file_path")
IDENT_KEYS = ("enduser.pseudo.id", "user.name", "process.user.name", "host.name",
              "github.copilot.context.skills", "github.copilot.context.custom_agent_names",
              "github.copilot.context.mcp_server_names", "github.copilot.git.repository")


def leaks(path):
    seen = collections.defaultdict(set)
    for res, s, a in spans(path):
        for k in CONTENT_KEYS + IDENT_KEYS:
            if k in a or k in res:
                seen[k].add(label(res))
    print("CONTENT (should be empty unless capture is deliberately on):")
    print("\n".join(f"  {k}  <- {sorted(seen[k])}" for k in CONTENT_KEYS if k in seen) or "  none")
    print("\nIDENTIFYING / ENVIRONMENT-REVEALING (exported even with content capture off):")
    print("\n".join(f"  {k}  <- {sorted(seen[k])}" for k in IDENT_KEYS if k in seen) or "  none")


COMMANDS = {"inventory": inventory, "sessions": sessions, "summary": summary,
            "tools": tools, "startup": startup, "leaks": leaks}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]](sys.argv[2])
