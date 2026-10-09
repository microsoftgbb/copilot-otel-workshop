# Verification log

This workshop teaches behaviour that changes between Copilot releases. Every non-obvious claim is tagged here so readers know how far to trust it, and so contributors know what to re-check.

**Status key**

- **Observed**: reproduced with the tooling in this repo, on the version shown.
- **Documented**: stated in official documentation, not reproduced here.
- **Open**: unknown or untested. Please help.

Environment for the observed results: Copilot CLI 1.0.95, `@github/copilot-sdk` 1.0.x (Node), Aspire Dashboard `latest`, OpenTelemetry Collector contrib 0.161.0, macOS with Docker Desktop, October 2026.

## Copilot CLI and SDK

| # | Claim | Status | Where used |
|---|---|---|---|
| C1 | Setting `OTEL_EXPORTER_OTLP_ENDPOINT` (or `COPILOT_OTEL_ENABLED`) enables export; traces and metrics arrive at an OTLP/HTTP collector | Observed | 02 |
| C2 | Span tree is `invoke_agent` → `chat` and `execute_tool`; model calls dominate wall time | Observed | 01, 05 |
| C3 | Events arrive as span events; no OTLP logs are emitted | Observed | 01, 03 |
| C4 | `COPILOT_OTEL_FILE_EXPORTER_PATH` writes a non-OTLP JSON-lines format (`type: span` / `metric`) | Observed | 02 |
| C5 | SDK `telemetry` option sets runtime env vars; an SDK app appears with `invoke_agent` and `chat` spans | Observed | 02 |
| C6 | `TelemetryConfig` has no headers, service name or resource attribute fields; use the client `env` option | Observed (SDK type definitions) | 02 |
| C7 | SDK-hosted sessions emit about 100 `session.timing.*` spans; one-shot `copilot -p` does not | Observed | 02, 05 |
| C8 | With content capture off, prompt text, file names and directory names are absent from the archive | Observed | 03 |
| C9 | With content capture off, `enduser.pseudo.id`, skill names, custom agent names and hashed MCP names are still exported | Observed | 03, 04, 07 |
| C10 | With content capture on, system prompt and tool schemas are exported on every `chat` span; traces are about 40x larger | Observed | 03, 07 |
| C11 | A failing shell command reports `success=true`; only `process.exit.code` shows failure | Observed | 03, 05, 06 |
| C12 | `github.copilot.nano_aiu` / 1e9 equals the CLI's printed "AI Credits" | Observed | 03, 05 |
| C13 | `gen_ai.client.token.usage` is not emitted; `gen_ai.client.inference.*` metrics are | Observed (absence on this version) | 03 |
| C14 | Subagent `invoke_agent` spans nest under the parent's `execute_tool` | Documented | 01 |
| C15 | `github.copilot.hook.*` span events, `session.truncation`, `session.compaction_start` exist | Documented | 03 |
| C16 | CLI exports OTLP/HTTP only (`http/json` default, `http/protobuf` optional) | Documented | 01, 02 |
| C17 | Precedence between managed settings and env vars for the **CLI** | **Open** | 07 |

## VS Code Copilot Chat

| # | Claim | Status | Where used |
|---|---|---|---|
| V1 | Settings `github.copilot.chat.otel.*` (enabled, exporterType, otlpEndpoint, captureContent, captureIdentity, maxAttributeSizeChars, outfile, dbSpanExporter.enabled) | Documented | 02 |
| V2 | Env vars take precedence over settings; extra `COPILOT_OTEL_*` variables exist | Documented | 02 |
| V3 | Auth headers only via `OTEL_EXPORTER_OTLP_HEADERS` | Documented | 02 |
| V4 | Terminal CLI sessions are separate root traces under `github-copilot` and only use `otlp-http` | Documented | 01, 02 |
| V5 | Extension spans use `service.name=copilot-chat`; wrapper `invoke_agent copilotcli` parents SDK spans | Documented | 01 |
| V6 | Agent Debug Log keeps full content when export is off | Documented | 03 |
| V7 | `copilot_chat.*` edit-acceptance and feedback metrics exist | Documented | 03, 06 |
| V8 | Managed values override user settings; env vars can still override managed values in the extension | Documented | 07 |
| V9 | Reproduce V1 to V8 in a real VS Code session and record versions | **Open** | 02 |

## Copilot app and enterprise

| # | Claim | Status | Where used |
|---|---|---|---|
| A1 | The Copilot app supports OTel through enterprise-managed settings | Documented (changelog) | 02, 07 |
| A2 | Does the app honour `OTEL_*` / `COPILOT_OTEL_*` env vars? Its `service.name` and span set? | **Open** | 02 |
| M1 | `telemetry` keys: enabled, endpoint, protocol, captureContent, lockCaptureContent, serviceName, resourceAttributes, headers | Documented | 02, 07 |
| M2 | Delivery by `.github-private` repo, MDM or local file | Documented | 07 |
| M3 | Whether `telemetry` can be specialised per team with `overridable` | **Open** | 07 |

## Collector and tooling

| # | Claim | Status | Where used |
|---|---|---|---|
| T1 | Redact overlay removes content and skill/agent/MCP names; `enduser.pseudo.id` remains by design | Observed | 04 |
| T2 | Fan-out overlay delivers to a second exporter while the first keeps receiving | Observed | 04 |
| T3 | Auth overlay returns 401 without and 200 with the bearer token | Observed (`lab/tests/smoke.sh`) | 04 |
| T4 | Collector tag overrides client `deployment.environment.name` | Observed | 04 |
| T5 | `env/copilot-otel.sh` restores the prior environment in bash and zsh | Observed (`lab/tests`) | 02 |

## How to update this file

When you re-run a claim, change its status, and add the Copilot version and date in your pull request. See [CONTRIBUTING.md](CONTRIBUTING.md).
