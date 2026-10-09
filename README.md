# OpenTelemetry for GitHub Copilot: a hands-on workshop

Learn how to turn on OpenTelemetry (OTel) for GitHub Copilot, what it does and does not record, and how to collect, search and visualise it. Built for anyone who uses or runs Copilot: individual engineers, engineering managers, and the teams that administer GitHub and Copilot.

Everything runs on your machine with Docker. The labs use the free [Aspire Dashboard](https://aspire.dev/dashboard/standalone/) behind an [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/), and nothing is sent to GitHub or any third party.

> This is community learning material, not official product documentation. Signal names and behaviour change between Copilot releases. Statements are tagged as **observed** (reproduced here, with a version) or **documented** (from official docs, not reproduced). See [VERIFICATION.md](VERIFICATION.md), and please help keep it current.

## What you will learn

- How telemetry flows from Copilot to a dashboard, and who emits what
- How to enable it on the **Copilot CLI**, **Copilot SDK** apps, **VS Code** and the **Copilot app**
- Exactly what is collected, including what still leaves your machine when content capture is off
- What it cannot tell you (quality, outcomes, licences, money)
- How to run a collector: tag, redact, archive and fan out
- How to answer real questions as an engineer, an engineering manager, and a GitHub operations owner

## Agenda

| # | Module | Time | You leave able to |
|---|---|---|---|
| 01 | [How OTel works with Copilot](modules/01-how-it-works.md) | 20 min | Draw the path from a prompt to a dashboard |
| 02 | [Enable it](modules/02-enable.md) (lab) | 40 min | Turn it on for every Copilot surface and debug "I see nothing" |
| 03 | [What it tracks, and what it does not](modules/03-what-it-tracks.md) (lab) | 40 min | Predict a signal's contents, and prove it from the data |
| 04 | [Collect it](modules/04-collect.md) (lab) | 30 min | Run a collector, redact, archive and forward |
| 05 | [Engineers](modules/05-engineers.md) (lab) | 30 min | Diagnose a slow, failing or costly agent run |
| 06 | [Engineering managers](modules/06-managers.md) | 20 min | Ask answerable questions and avoid misleading metrics |
| 07 | [GitHub operations](modules/07-operations.md) | 30 min | Roll out, govern and size a deployment |
| 08 | [Managing OTel with managed settings](modules/08-managed-settings.md) (lab) | 30 min | Enforce telemetry enterprise-wide: write, deliver, prioritise and verify the `telemetry` block |

Everyone does 01 to 04. Then pick a track (05, 06 or 07). Administrators who will enforce OTel also do 08. Allow about 3.5 hours for everything, or 90 minutes for one track.

## Which Copilot surfaces are covered

| Surface | How it emits | Reproduced in this repo? |
|---|---|---|
| **Copilot CLI** | Built into the CLI runtime | **Yes**, CLI 1.0.95: every claim in modules 03 to 05 |
| **Copilot SDK apps** | Same runtime, spawned by the SDK | **Yes**, a Node app on `@github/copilot-sdk` |
| **VS Code Copilot Chat** | Its own emitter in the extension | No. Documented settings and behaviour only |
| **Copilot app** | Enterprise managed settings | No. Documented only |

Where a lab would need VS Code or the app, the module says so and gives you the steps to try it and a place to record what you find.

## Quick start

Requirements: Docker, Python 3.8+, and for the live labs the Copilot CLI signed in (the labs spend a few AI credits; about 12 for the traffic script).

```bash
cd lab
docker compose up -d                  # dashboard http://localhost:18888, OTLP on :4318
scripts/traffic.sh                    # three scenarios generate telemetry (uses a few AI credits)
# then open http://localhost:18888 and explore Traces and Metrics
```

No credits or no Copilot CLI? Every analysis lab also works on a sanitized recording included in the repo:

```bash
python3 lab/scripts/analyze.py sessions lab/samples/archive.sample.jsonl
```

If ports 4317, 4318 or 18888 are taken, copy `lab/.env.example` to `lab/.env` and change `LAB_*_PORT`.

## One-page cheat sheet

| I want to... | Do this |
|---|---|
| Turn on OTel for the CLI | `COPILOT_OTEL_ENABLED=true` and/or `OTEL_EXPORTER_OTLP_ENDPOINT=http://host:4318` |
| Write to a file instead | `COPILOT_OTEL_FILE_EXPORTER_PATH=/path/out.jsonl` (its own format, not OTLP) |
| Name the service, add tags | `OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES="team=x,env=y"` |
| Authenticate to a collector | `OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer <token>"` |
| Capture prompts and tool output | `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` (off by default; read module 03 first) |
| Turn it on in an SDK app | `new CopilotClient({ telemetry: { otlpEndpoint } })` |
| Turn it on in VS Code | `github.copilot.chat.otel.enabled` and `github.copilot.chat.otel.otlpEndpoint` |
| Enforce it across an enterprise | `telemetry` block in `managed-settings.json` ([module 08](modules/08-managed-settings.md)) |
| Lint a managed-settings telemetry block | `python3 lab/scripts/managed_settings.py validate file.json` |
| Read data with no backend | `python3 lab/scripts/analyze.py sessions archive.jsonl` |

## Repository layout

| Path | What |
|---|---|
| [modules/](modules) | The workshop, in order |
| [lab/compose.yaml](lab/compose.yaml) | Collector plus Aspire Dashboard, with a JSONL archive |
| [lab/overlays/](lab/overlays) | Collector overlays: `redact`, `fanout`, `auth` |
| [lab/env/copilot-otel.sh](lab/env/copilot-otel.sh) | Point a shell's Copilot sessions at the collector; undo with `copilot_otel_off` |
| [lab/scripts/](lab/scripts) | `traffic.sh`, `analyze.py`, `sanitize.py`, `managed_settings.py` |
| [lab/managed-settings/](lab/managed-settings) | An example `telemetry` block for managed settings |
| [lab/sdk/](lab/sdk) | A minimal Copilot SDK app that exports telemetry |
| [lab/samples/](lab/samples) | A sanitized recording of real sessions, so labs work offline |
| [lab/tests/](lab/tests) | Unit tests and a stack smoke test |

## Facilitator notes

- Run `scripts/traffic.sh` yourself first and keep the archive. If a live lab fails, attendees can use your file, or the bundled sample.
- Module 03's "what leaves your machine" exercise is the one people remember. Do not skip it.
- The labs use Aspire, but nothing in the signals is Aspire-specific. Any OTLP backend works; module 04 shows where to point it.
- Never run the labs with content capture on against a shared backend.

## Contributing

This is a living workshop. The most valuable contributions are verification results for the surfaces not yet reproduced (VS Code, the Copilot app) and updates after Copilot releases. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Sources

- [OpenTelemetry for agent monitoring](https://docs.github.com/en/copilot/concepts/enterprise/opentelemetry)
- [OpenTelemetry instrumentation for Copilot SDK](https://docs.github.com/en/copilot/how-tos/copilot-sdk/observability/opentelemetry)
- [Copilot CLI reference: OpenTelemetry monitoring](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#opentelemetry-monitoring)
- [VS Code: monitor agent usage with OpenTelemetry](https://code.visualstudio.com/docs/agents/guides/monitoring-agents)
- [Enterprise managed settings reference](https://docs.github.com/en/copilot/reference/enterprise-administrators/enterprise-managed-settings)
- [Getting started with enterprise managed settings](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-enterprise/use-managed-settings/get-started)
- [Changelog: OpenTelemetry in the GitHub Copilot app (2026-09-22)](https://github.blog/changelog/2026-09-22-opentelemetry-in-the-github-copilot-app/)
- [Copilot usage metrics](https://docs.github.com/en/copilot/concepts/billing-and-usage/copilot-usage-metrics/copilot-metrics)
- [Aspire Dashboard (standalone)](https://aspire.dev/dashboard/standalone/)
- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)

## License

[MIT](LICENSE)
