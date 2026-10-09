# 04. Collect it (lab)

**Goal:** understand the collector between Copilot and your backend, and use it to tag, redact, archive and fan out data.

## The collector in one picture

An OpenTelemetry Collector is a pipeline: **receivers** take data in, **processors** change it, **exporters** send it on, and **pipelines** wire them together, one per signal.

```
Copilot ──OTLP──► receiver:otlp ─► memory_limiter ─► resource/lab ─► batch ─┬─► otlp/aspire  (live UI)
                                                                             └─► file/archive (JSONL)
```

Read [lab/collector/config.yaml](../lab/collector/config.yaml). What each part does:

| Part | Role |
|---|---|
| `receivers.otlp` | Accepts OTLP on 4317 (gRPC) and 4318 (HTTP) |
| `processors.memory_limiter` | Protects the collector from bursts |
| `processors.resource/lab` | Stamps `deployment.environment.name` from the collector host, overriding any client value |
| `processors.batch` | Groups data before export |
| `exporters.otlp/aspire` | The live dashboard |
| `exporters.file/archive` | A durable `archive.jsonl`, rotated at 100 MB, 14 days and 20 files |

## Lab 1: tag at the collector

Clients can tag themselves, but a collector tag cannot be forgotten or faked. `resource/lab` already does it for the environment:

```bash
cd lab
LAB_ENVIRONMENT=staging docker compose up -d --force-recreate otel-collector
```

Every signal now carries `deployment.environment.name=staging` regardless of what the client said. Use this for anything that must be trustworthy: environment, region, network zone.

## Lab 2: redact centrally

Module 03 showed what leaves a machine. An operator can strip it at the collector so it never reaches storage, even if someone turns content capture on.

[lab/overlays/redact.yaml](../lab/overlays/redact.yaml) deletes the content attributes plus the skill, agent and MCP server names:

```bash
cd lab
docker compose -f compose.yaml -f compose.redact.yaml up -d --force-recreate otel-collector
```

Run a content-capture session and audit the archive:

```bash
export LAB_SCENARIO=redacted LAB_CAPTURE_CONTENT=true
source lab/env/copilot-otel.sh      # export first: `VAR=x source ...` is discarded after the line
copilot -p "Run 'cat /nonexistent-file' in bash and report the error in one sentence."
copilot_otel_off
docker compose -f lab/compose.yaml cp otel-collector:/data/archive.jsonl ./archive.jsonl
python3 lab/scripts/analyze.py leaks archive.jsonl
```

**Verified result:** `copilot-lab/redacted` appears in no content line and no skill, agent or MCP line. The only attribute still listed for it is `enduser.pseudo.id`, which the overlay keeps on purpose so you can still count distinct users. Decide per organisation whether to keep, hash or delete it (module 07). The archive for that session was about 27 KB rather than 1 MB.

Caveats:

- Overlays **replace** lists, so the overlay restates the pipeline's `processors`. If you change the base config's list, change the overlay too.
- It redacts what you name. New Copilot builds may add sensitive attributes, so re-run `analyze.py leaks` after each upgrade.
- Redaction here is on the trace pipeline, because that is where the content lives. Check `inventory` if you add signals.
- The content still crossed the network to reach the collector. Use TLS, and prefer not enabling capture at the source.

## Lab 3: fan out to a second destination

Collectors let one stream feed several places. [lab/overlays/fanout.yaml](../lab/overlays/fanout.yaml) adds an exporter to the traces and metrics pipelines:

```bash
cd lab
docker compose -f compose.yaml -f compose.fanout.yaml up -d --force-recreate otel-collector
# run any Copilot session, then:
docker compose logs otel-collector | grep -E "Traces|Metrics"
```

**Verified result:** the `debug` exporter printed the traces and metrics, while the dashboard and archive kept receiving the same data, with no collector errors.

To go to a real backend, uncomment the `otlphttp/other` block and give it your endpoint and token. Any backend that speaks OTLP works, directly or through its own collector. The collector-contrib image used here also ships exporters for vendor backends (for example Azure Monitor, Splunk and Prometheus-compatible stores); check the component list for your backend and version.

## Lab 4: require a token *(also see module 07)*

```bash
cd lab
LAB_TOKEN=$(openssl rand -hex 24) LAB_DASHBOARD_TOKEN=$(openssl rand -hex 16) \
  docker compose -f compose.yaml -f compose.auth.yaml up -d
```

The collector now returns 401 to OTLP requests without `Authorization: Bearer <token>` and 200 with it (checked by `lab/tests/smoke.sh`). Clients send the token with `OTEL_EXPORTER_OTLP_HEADERS`; the env script does this from `LAB_TOKEN`. A bearer token over plain HTTP is readable on the network, so put TLS in front of any non-local collector.

## Choosing a backend

| Need | Good fit | Why |
|---|---|---|
| Learn and debug locally | **Aspire Dashboard** (used here) | One container, traces, metrics and logs, no cloud account. VS Code's docs recommend it for local development |
| Quick trace viewer | Jaeger | Accepts OTLP directly |
| LLM-focused tracing | Langfuse | Native OTLP ingestion and GenAI semantic-convention support. VS Code's docs show auth headers via `OTEL_EXPORTER_OTLP_HEADERS` |
| Already on Azure | Collector with the Azure Monitor exporter, into Application Insights | Microsoft documents a [Grafana-with-Application-Insights dashboard](https://learn.microsoft.com/en-gb/azure/managed-grafana/grafana-opentelemetry-app-insights) for Copilot agents |
| Team dashboards and alerts | Grafana with Tempo and Prometheus, or a managed Grafana | Dashboards, alerting, long retention |
| Existing vendor APM | Splunk, Datadog and similar | The GitHub changelog demonstrates Splunk Observability Cloud on Copilot app traces |
| Cheap long-term record | The JSONL archive, or object storage | Searchable offline with `analyze.py`, `jq` or a notebook |

**Aspire's limits matter.** It keeps a bounded in-memory window (set in `lab/compose.yaml`: 20k traces, 50k logs, 50k metric points) and is designed for development and short-term diagnostics. Do not treat it as your system of record.

## Check yourself

1. Why tag the environment in the collector rather than in each client?
2. You apply the redact overlay and then add a new processor to `config.yaml`. It does nothing. Why?
3. Is redacting at the collector enough to keep prompts private?

<details><summary>Answers</summary>

1. A client can omit or fake it; the collector's value is authoritative and consistent.
2. The overlay replaced the pipeline's `processors` list. Add the processor to the overlay too.
3. No. The content still crossed the network to reach the collector. Keep capture off at the source, use TLS, and treat redaction as defence in depth.
</details>

Next: [05. Engineers](05-engineers.md)
