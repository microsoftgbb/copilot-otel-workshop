# 02. Enable it (lab)

**Goal:** turn OTel on for each Copilot surface, and know how to tell when it is not working.

Start the lab stack first (see the [README](../README.md#quick-start)). Examples assume `http://localhost:4318`; substitute your port.

## Lab 1: Copilot CLI, environment variables only *(reproduced)*

```bash
export COPILOT_OTEL_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=my-laptop
copilot -p "Reply with exactly: ok"
```

Open the dashboard (http://localhost:18888) and go to **Traces**. Within a few seconds you should see `my-laptop: invoke_agent`.

| Variable | Default | Purpose |
|---|---|---|
| `COPILOT_OTEL_ENABLED` | `false` | Explicit switch. Not needed if an endpoint is set |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | none | Collector URL. Setting it also enables OTel |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/json` | `http/json` or `http/protobuf` |
| `OTEL_EXPORTER_OTLP_HEADERS` | none | Auth, e.g. `Authorization=Bearer <token>` |
| `OTEL_SERVICE_NAME` | `github-copilot` | Becomes `service.name` |
| `OTEL_RESOURCE_ATTRIBUTES` | none | Extra tags: `team=platform,env=dev` (percent-encode special characters) |
| `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` | `false` | Prompts, responses, tool arguments and results. **Read module 03 first** |
| `COPILOT_OTEL_EXPORTER_TYPE` | `otlp-http` | `otlp-http` or `file` |
| `COPILOT_OTEL_FILE_EXPORTER_PATH` | none | Write to a file; also enables OTel |
| `COPILOT_OTEL_SOURCE_NAME` | `github.copilot` | Instrumentation scope name |
| `OTEL_LOG_LEVEL` | none | Exporter diagnostics: `ERROR` ... `ALL` |

Variables only reach processes started from that shell. An app launched from a desktop icon will not see them.

### The lab shortcut

[lab/env/copilot-otel.sh](../lab/env/copilot-otel.sh) sets the above for you, and `copilot_otel_off` puts your environment back exactly as it was:

```bash
export LAB_NAME=my-laptop            # export first: `VAR=x source ...` is discarded afterwards
source lab/env/copilot-otel.sh
copilot -p "Reply with exactly: ok"
copilot_otel_off
```

## Lab 2: file exporter, no backend at all *(reproduced)*

```bash
COPILOT_OTEL_FILE_EXPORTER_PATH=/tmp/copilot-otel.jsonl copilot -p "Reply with exactly: ok"
head -c 400 /tmp/copilot-otel.jsonl
```

> **Gotcha:** the file exporter does **not** write OTLP. Each line is `{"type":"span", ...}` or `{"type":"metric", ...}` with timestamps as `[seconds, nanoseconds]` pairs. It is handy for a quick look, but OTLP tools (including this repo's `analyze.py`) will not parse it. Send to a collector when you want an OTLP archive.

## Lab 3: an app built on the Copilot SDK *(reproduced)*

The SDK adds no telemetry of its own. Its `telemetry` option sets environment variables on the spawned runtime.

```typescript
import { CopilotClient } from "@github/copilot-sdk";

const client = new CopilotClient({
  telemetry: { otlpEndpoint: "http://localhost:4318", captureContent: false },
});
```

```python
# from the SDK documentation; not run here
client = CopilotClient(telemetry={"otlp_endpoint": "http://localhost:4318"})
```

| Option (Node / Python) | Sets |
|---|---|
| `otlpEndpoint` / `otlp_endpoint` | `OTEL_EXPORTER_OTLP_ENDPOINT` |
| `otlpProtocol` / `otlp_protocol` | `OTEL_EXPORTER_OTLP_PROTOCOL` |
| `filePath` / `file_path` | `COPILOT_OTEL_FILE_EXPORTER_PATH` |
| `exporterType` / `exporter_type` | `COPILOT_OTEL_EXPORTER_TYPE` |
| `sourceName` / `source_name` | `COPILOT_OTEL_SOURCE_NAME` |
| `captureContent` / `capture_content` | `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` |

`TelemetryConfig` has no field for headers, service name or resource attributes, so set those through the client's `env` option. **`env` replaces the inherited environment**, so spread `process.env` into it first. A complete, runnable example is in [lab/sdk/example.mjs](../lab/sdk/example.mjs):

```bash
cd lab/sdk && npm install && npm start
```

Verified: it created a session, sent a prompt, and appeared as its own `copilot-lab-sdk` service with `invoke_agent` and `chat` spans.

**Observed difference:** SDK-hosted sessions also emit about 100 `session.timing.*` spans covering start-up phases (MCP catalogue, auth, model resolution, prompt assembly). One-shot `copilot -p` runs did not. They are useful for engineers (module 05) and a volume consideration for operators (module 07). They carry no conversation id.

**Advanced, usually unnecessary:** to make your own spans part of Copilot's trace, propagate W3C trace context. Node needs an `onGetTraceContext` callback; Python, Go and .NET do it automatically when their OTel API is configured.

## Lab 4: VS Code *(documented, not reproduced here)*

VS Code Copilot Chat has its own emitter. In **Settings**, search for `copilot otel`, or edit `settings.json`:

```json
{
  "github.copilot.chat.otel.enabled": true,
  "github.copilot.chat.otel.exporterType": "otlp-http",
  "github.copilot.chat.otel.otlpEndpoint": "http://localhost:4318"
}
```

| Setting | Default | Meaning |
|---|---|---|
| `github.copilot.chat.otel.enabled` | `false` | Enable OTel emission |
| `github.copilot.chat.otel.exporterType` | `otlp-http` | `otlp-http`, `otlp-grpc`, `console` or `file` |
| `github.copilot.chat.otel.otlpEndpoint` | `http://localhost:4318` | Collector endpoint |
| `github.copilot.chat.otel.captureContent` | `false` | Capture full prompts and responses |
| `github.copilot.chat.otel.captureIdentity` | `false` | Add account name, OS username and hostname (Local harness sessions) |
| `github.copilot.chat.otel.maxAttributeSizeChars` | `0` | Truncate content attributes; `0` means no limit. Set it to match your backend's limit |
| `github.copilot.chat.otel.outfile` | empty | JSON-lines output file |
| `github.copilot.chat.otel.dbSpanExporter.enabled` | `false` | Keep spans in a local SQLite database for the **Chat: Export Agent Traces DB** command. Implicitly enables OTel |

Facts that surprise people:

- **Environment variables beat settings.** If both are present, the variable wins.
- VS Code also reads `COPILOT_OTEL_ENDPOINT` (takes precedence over `OTEL_EXPORTER_OTLP_ENDPOINT`), `COPILOT_OTEL_PROTOCOL`, `COPILOT_OTEL_CAPTURE_CONTENT`, `COPILOT_OTEL_CAPTURE_IDENTITY`, `COPILOT_OTEL_MAX_ATTRIBUTE_SIZE_CHARS` and `COPILOT_OTEL_LOG_LEVEL`.
- **Auth headers can only be set by environment variable** (`OTEL_EXPORTER_OTLP_HEADERS`). There is no setting for them.
- The extension forwards `COPILOT_OTEL_ENABLED` and the endpoint to CLI sessions you start in the terminal, but the **terminal CLI only speaks `otlp-http`**, even if you chose `otlp-grpc`. A backend that serves both on one port (Aspire does) works either way.
- The **Agent Debug Log** panel shows the full trace hierarchy even with OTel off. With OTel off it captures full prompt and response content for the panel; with OTel on, `captureContent` governs both the panel and the export.

**Try it:** enable the settings above, run an agent chat, and open **Traces**. Record what you see (service names, whether the terminal CLI trace is separate) in [VERIFICATION.md](../VERIFICATION.md).

## Lab 5: Copilot app *(documented, not reproduced here)*

The [2026-09-22 changelog](https://github.blog/changelog/2026-09-22-opentelemetry-in-the-github-copilot-app/) announces OpenTelemetry configuration for the Copilot app through enterprise-managed settings, with prompt and response content excluded by default. The changelog's demo shows traces from the app in Splunk Observability Cloud's Trace Analyzer.

Open questions to settle by experiment, and record in [VERIFICATION.md](../VERIFICATION.md):

1. Does the app honour the `OTEL_*` and `COPILOT_OTEL_*` environment variables when launched from a shell?
2. What `service.name` and which spans does it emit?
3. How does it compare to the CLI's data from module 03?

## Lab 6: enterprise managed settings *(documented, not reproduced here)*

An administrator can enforce OTel for the CLI and VS Code through the `telemetry` block of `managed-settings.json`:

```json
{
  "telemetry": {
    "enabled": true,
    "endpoint": "https://otel.example.com:4318",
    "protocol": "http/protobuf",
    "captureContent": false,
    "lockCaptureContent": true,
    "serviceName": "copilot",
    "resourceAttributes": { "deployment.environment.name": "production" },
    "headers": { "Authorization": "Bearer <token>" }
  }
}
```

`lockCaptureContent` stops users turning content capture on. Delivery methods, precedence and a lint for this block are in [module 08](08-managed-settings.md).

## Troubleshooting: "I see nothing"

| Check | How |
|---|---|
| Is it enabled? | One of the activating settings or variables must be present in the process that launched Copilot |
| Is the collector reachable? | `curl -i -X POST -H 'content-type: application/json' -d '{}' http://localhost:4318/v1/logs` should return 200 |
| Wrong protocol or port? | HTTP is 4318 and gRPC is 4317. The CLI sends OTLP/HTTP, so use 4318 |
| Auth? | A 401 from the collector means a missing or wrong `OTEL_EXPORTER_OTLP_HEADERS` |
| Looking in the wrong place? | CLI data is traces and metrics. The logs page stays empty (module 01) |
| Environment variable not inherited? | Start the app from the shell where you exported it |
| Short-lived process? | Wait a few seconds and look again. Exporters batch |
| Still nothing | Set `OTEL_LOG_LEVEL=DEBUG` (or `COPILOT_OTEL_LOG_LEVEL` in VS Code) and read the exporter output |

## Check yourself

1. You set `OTEL_SERVICE_NAME=a` in your shell, then launch VS Code from the Dock. What service name appears?
2. Your SDK app needs an `Authorization` header on telemetry. Which option carries it?
3. Why can't you analyse the CLI file exporter's output with an OTLP tool?
4. VS Code settings say `otlp-grpc` and you start a CLI session in the integrated terminal. Which protocol does that session use?

<details><summary>Answers</summary>

1. The default (`copilot-chat`). The Dock launch did not inherit your shell variable.
2. The client `env` option (`OTEL_EXPORTER_OTLP_HEADERS`). `TelemetryConfig` has no headers field.
3. It is a different JSON-lines format, not OTLP.
4. `otlp-http`. The terminal CLI runtime only supports HTTP.
</details>

Next: [03. What it tracks, and what it does not](03-what-it-tracks.md)
