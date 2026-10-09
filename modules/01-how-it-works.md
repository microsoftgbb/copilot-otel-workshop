# 01. How OTel works with Copilot

**Goal:** draw the path from a prompt to a dashboard, and say which component emits which signal.

## The mental model

OpenTelemetry is a vendor-neutral way for software to describe what it did (traces), how much (metrics) and notable moments (events), and to ship that over a standard protocol (OTLP) to any compatible backend. Copilot does not send this to GitHub. **You** choose where it goes.

```
 ┌─ emitter ───────────────────────────┐   OTLP/HTTP    ┌─ collector ─┐     ┌─ backend(s) ──────────┐
 │ Copilot CLI / SDK runtime           │ ─────────────► │ receive     │ ──► │ Aspire, Jaeger,       │
 │ VS Code Copilot Chat extension      │                │ process     │ ──► │ Grafana, App Insights │
 │ Copilot app                         │                │ route       │ ──► │ file archive          │
 └─────────────────────────────────────┘                └─────────────┘     └───────────────────────┘
        off by default, zero overhead                    optional but recommended
```

A collector is optional (an emitter can talk straight to a backend that speaks OTLP) but earns its place: one stable address for everyone, where you can add tags, drop data, authenticate and fan out.

## Who emits what

| Surface | Emitter | Turned on by | Notes |
|---|---|---|---|
| **Copilot CLI** | The CLI runtime itself | Environment variables | `service.name` defaults to `github-copilot`. Instrumentation scope `github.copilot` |
| **Copilot SDK apps** | The same CLI runtime, spawned by the SDK | `telemetry` option on the client | The SDK sets environment variables on the child process. You do not instrument the SDK |
| **VS Code Copilot Chat** | The extension | `github.copilot.chat.otel.*` settings or environment variables | `service.name` is `copilot-chat` for extension spans. See below |
| **Copilot app** | The embedded runtime | Enterprise managed settings | Announced 2026-09-22 |
| **Your code** | OTel API or SDK | You | Optional. Lets your own spans join Copilot's trace |

Two facts to anchor on:

1. **The SDK is not a separate telemetry source.** `TelemetryConfig` fields map one-to-one onto environment variables for the runtime process (`otlpEndpoint` sets `OTEL_EXPORTER_OTLP_ENDPOINT`, `captureContent` sets `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`, and so on). CLI and SDK apps therefore produce the same shape of data.
2. **It is off until you opt in.** Any one of `COPILOT_OTEL_ENABLED=true`, `OTEL_EXPORTER_OTLP_ENDPOINT`, or `COPILOT_OTEL_FILE_EXPORTER_PATH` activates it in the CLI.

### VS Code is a little different *(documented)*

VS Code has its own emitter, and a single chat can involve more than one process:

| `service.name` | Source |
|---|---|
| `copilot-chat` | The extension: foreground agent, the CLI wrapper span, and Claude agent spans |
| `github-copilot` | The Copilot SDK's native spans, and Copilot CLI sessions started in a terminal |
| `claude-code` | Claude Code subprocess telemetry, when forwarded |

In the extension, a wrapper span (`invoke_agent copilotcli`) parents the SDK's native spans, so both appear in one trace. A CLI session started in the **terminal** runs in a separate process and appears as its own root trace, not linked to the extension's. Within `copilot-chat`, `gen_ai.agent.name` tells agent types apart (`GitHub Copilot Chat`, `copilotcli`, `claude`).

## The three signal types, as Copilot uses them

| Signal | What it is | Copilot example | Good for |
|---|---|---|---|
| **Trace** | A tree of timed steps (spans) for one run | `invoke_agent` → `chat` and `execute_tool` | "What happened, in what order, how long?" |
| **Metric** | A number aggregated over time | Token counts, tool call counts, durations | "How much, how often, what trend?" |
| **Event** | A point-in-time record | An MCP server connected, a skill ran | "When did X happen?" |

> **Observed gotcha:** the CLI delivers its events as **span events** (attached to a span), not as OTLP *logs*. A pipeline or a dashboard page that only shows logs will look empty for CLI data. Look at traces and metrics.

## The shape of one run

Observed from a real CLI session that read a file, created one and ran `ls`:

```
invoke_agent                                   18.2 s   <- one user prompt; carries totals
 ├─ chat <model>                                ~5 s    <- one model call
 ├─ execute_tool skill                          0.01 s
 ├─ chat <model>
 ├─ execute_tool view                           0.01 s
 ├─ chat <model>
 ├─ execute_tool apply_patch                    0.01 s
 ├─ chat <model>
 ├─ execute_tool bash                           0.05 s
 └─ chat <model>
```

Read it as a loop: the model is called, asks for a tool, the tool runs, the result goes back, repeat until the model answers. Here the model calls took nearly all of the time and the tools about 0.1 s. **For most agent work, latency and cost live in `chat` spans, not tools.**

Subagents nest: the docs state that a subagent's `invoke_agent` appears under the parent's `execute_tool` span. That was not exercised here.

## Vocabulary

| Term | Meaning |
|---|---|
| **Resource** | The thing emitting (service name, your tags). Attached to every signal |
| **Span attribute** | A key and value on one span (`gen_ai.usage.input_tokens`) |
| **Metric dimension** | A label that splits a metric (`gen_ai.tool.name`) |
| **OTLP** | The wire protocol. HTTP on 4318, gRPC on 4317 by convention. The CLI exports OTLP/HTTP only, JSON by default |
| **GenAI semantic conventions** | The shared `gen_ai.*` names, so tools understand the data without custom mapping |
| **`github.copilot.*`** | Copilot-specific names (AI credits, skills, sandbox) |
| **`copilot_chat.*`** | The original VS Code extension namespace, alongside `github.copilot.*` |

## Check yourself

1. If you set `captureContent: true` in an SDK app, which process actually changes behaviour?
2. You see no data on a logs page. Does that mean telemetry is off?
3. In VS Code you start a CLI session from the integrated terminal. Will its trace be a child of your chat's trace?

<details><summary>Answers</summary>

1. The spawned Copilot runtime child process, via an environment variable.
2. No. The CLI sends traces and metrics, with events inside spans. Look there.
3. No. Terminal CLI sessions run in a separate process and appear as independent root traces under `github-copilot`.
</details>

Next: [02. Enable it](02-enable.md)
