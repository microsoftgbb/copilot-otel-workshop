# 07. GitHub operations

**Goal:** roll out OTel across a Copilot estate, govern what it collects, and run the pipeline like any production service.

## Decisions to make before you enable anything

| Decision | Options | Recommendation |
|---|---|---|
| **Content capture** | Off, on, or on only in selected environments | **Off**, and set `lockCaptureContent: true` in managed settings. Content capture exports system prompts and tool output (module 03) and makes traces about 40x larger |
| **User identity** | Keep, hash or drop `enduser.pseudo.id`; allow or forbid VS Code `captureIdentity` | Keep the pseudonymous id for distinct-user counts. Leave identity capture off unless HR, legal and the data owner have approved a purpose |
| **Environment-revealing attributes** | Keep or strip skill, agent and MCP server names | Strip at the collector unless you actively use them (module 04, Lab 2) |
| **Who can read the backend** | Everyone, engineers, or ops only | Treat it as sensitive: it describes how your people work |
| **Retention** | Short live view versus a durable archive | A live view of days, plus an archive with a stated retention period |
| **Where it lives** | Per team or central | A central collector, with environment tags set by the collector |

## Rollout plan

1. **Pilot** on one team with the lab stack: run the labs, and use `analyze.py inventory` and `leaks` to learn exactly what your Copilot version emits.
2. **Central collector:** deploy with the auth overlay (bearer token, TLS in front, dashboard login). Add the redact overlay. Send to your real backend with a second exporter.
3. **Enforce with managed settings:** push a `telemetry` block so every supported client reports, with content capture off and locked.
4. **Operate:** monitor the pipeline, re-audit after Copilot upgrades, and review access and retention on a schedule.

## Enforcing with managed settings *(documented, not deployed here)*

Per the [reference](https://docs.github.com/en/copilot/reference/enterprise-administrators/enterprise-managed-settings), the `telemetry` property is supported for the Copilot CLI and VS Code. The [2026-09-22 changelog](https://github.blog/changelog/2026-09-22-opentelemetry-in-the-github-copilot-app/) adds the Copilot app. Check the current reference for which clients honour which keys.

| Key | Purpose |
|---|---|
| `enabled` | Turn export on or off |
| `endpoint` | Your OTLP collector URL |
| `protocol` | `http/json` or `http/protobuf` |
| `captureContent` | Include prompts and responses |
| `lockCaptureContent` | Stop users changing `captureContent` |
| `serviceName` | Service name label |
| `resourceAttributes` | Tags on all exported telemetry |
| `headers` | HTTP headers, for example `Authorization` |

### How the file reaches clients

The full walkthrough, with commands and a local lint, is [module 08](08-managed-settings.md). In short, there are three delivery methods:

| Method | Notes |
|---|---|
| **Server-managed** | `copilot/managed-settings.json` in a `.github-private` repository. Applies to users licensed by your enterprise or its organisations, on all clients including the cloud agent. Refreshes about hourly |
| **MDM** | Windows registry or macOS managed preferences, as string values. Applies to the device regardless of licence |
| **File-based** | A `managed-settings.json` on the device. Applies regardless of licence; the CLI rejects files that are symlinks or not root-owned and unwritable by others |

When sources conflict, earlier wins: MDM, then server-managed, then file-based, then user settings.

Per-team specialisation (`{ "overridable": ... }`) exists, but **`telemetry` is not in the documented list of overridable keys**, so it cannot be varied per team. Plan for one enterprise-wide destination.

### Precedence and traps

| Fact *(documented)* | Consequence |
|---|---|
| A managed telemetry value **overrides user settings** in VS Code | Developers cannot turn off a managed endpoint through settings |
| In the Copilot Chat extension, **OTel environment variables can still override managed values** | Remove conflicting `OTEL_*` and `COPILOT_OTEL_*` variables from managed devices, or enforcement can be bypassed |
| Managed identity capture and resource attributes override `COPILOT_OTEL_CAPTURE_IDENTITY` and `OTEL_RESOURCE_ATTRIBUTES` | Set them centrally if you need them |
| If managed OTel that enables export arrives after Copilot Chat starts, VS Code tries once per editor session to restart the extension hosts | Warn users: it can interrupt other extensions; otherwise they must reload the window |
| Managed telemetry covers both the Copilot Chat extension and the agent host process | One policy for both |

Other limits to plan around:

- It is **one static file for a fleet**. You can tag environment or team, but not an individual agent or person.
- The token in `headers` is delivered to every managed client, and the getting-started guide recommends enterprise-visible access to the repository that hosts the file. Treat any bearer token there as widely readable: use a write-only ingest token you can rotate, or network controls or mTLS at the collector ([module 08](08-managed-settings.md)).
- Precedence for the **CLI** and the **app** versus environment variables was not tested here. Verify, then record it in [VERIFICATION.md](../VERIFICATION.md).

## Size it *(observed, Copilot CLI 1.0.95)*

| Observation | Number |
|---|---|
| Trace data for a 2-call CLI session, content off | about 26 KB |
| Same session, content on | about 1.0 MB |
| Metric data per CLI session | about 14 to 19 KB |
| Trace data for an SDK-hosted session | about 98 KB (about 100 `session.timing.*` spans) |
| `mcp.server.lifecycle` span events per short session | about 33 |

Plan on tens of KB per ordinary session with capture off, multiplied by sessions per day. Measure on your own mix: MCP-heavy or long agent runs will be larger. The lab config rotates the archive at 100 MB, 14 days and 20 files, which caps disk but also **caps history**; raise it if you need a longer record.

## Run the pipeline

| Concern | What to do |
|---|---|
| **Collector down** | Alert on the container and on the collector's health-check endpoint (port 13133 inside the container; publish it if you probe from outside) |
| **Silent data loss** | The collector logs `Exporting failed. Rejecting data` when an exporter cannot write (seen during testing when the archive directory was not writable). Alert on exporter errors in the collector logs or its own metrics |
| **Absence of data** | Alert when an expected service sends nothing for N hours. "No data" is the failure that does not page itself |
| **Cost spikes** | Alert on daily AI credits against a rolling baseline |
| **MCP trouble** | Watch `github.copilot.mcp.server.connection.count` by `outcome`. Inspect the real outcome values on your version before choosing a threshold |
| **Failing shell commands** | Use `process.exit.code`, not the `success` flag |
| **Upgrades** | After each Copilot CLI or VS Code upgrade, re-run `analyze.py inventory` and `leaks`. Signal names and attributes have already changed between builds |
| **Credentials** | Rotate the ingest token on a schedule; it is shared by every client |
| **Incident: content got captured** | Stop capture at the source, purge the affected archive and backend data, and rotate any secrets that may have appeared in prompts or tool output |

## How OTel fits with GitHub's own metrics

| | OTel (this workshop) | Copilot usage metrics API and dashboards |
|---|---|---|
| Answers | How agents behave and what they consume, per session, with traces | Adoption and activity across the org, plus PR lifecycle impact |
| Granularity | Every model call and tool call | Daily and 28-day aggregates by feature, IDE, model, language, user, repository |
| Needs | Clients configured to export | Telemetry enabled in IDEs; server-side signals fill some gaps |
| Seats and licences | No | Use the Copilot user management API |
| Covers GitHub.com chat, mobile | Not documented | No (the docs exclude them) |
| You own the data | Yes, in your backend | Held by GitHub; exportable |

Use the **usage metrics** for "who is adopting Copilot, and does it change PR throughput", and **OTel** for "what is my agent doing, how much does it cost, and why did that run fail". They are not interchangeable and their totals will not match.

## Governance checklist

- [ ] Purpose, audience and retention written down and approved
- [ ] Content capture off and locked
- [ ] Decision recorded on `enduser.pseudo.id` and identity capture
- [ ] Collector redacts environment-revealing attributes, or the exposure is accepted
- [ ] TLS in front of the collector; ingest token rotated on a schedule
- [ ] Conflicting OTel environment variables removed from managed devices
- [ ] Backend access limited to named groups
- [ ] Alerts for collector down, exporter errors, silent services and credit spikes
- [ ] `analyze.py leaks` run after every Copilot upgrade
- [ ] A documented way for developers to see what is collected about them

## Check yourself

1. You set `captureContent: false` and `lockCaptureContent: true` in managed settings. A developer exports `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` and uses VS Code. What do the docs suggest could happen, and what is your backstop?
2. The archive disk is full of 1 MB traces. First suspect?
3. A dashboard shows zero sessions from the platform team since Tuesday. Is nothing happening?

<details><summary>Answers</summary>

1. In the Copilot Chat extension, OTel environment variables can still override managed values. Remove such variables from managed devices, and use the collector redact overlay as a backstop, since it deletes the content attributes regardless of what clients send.
2. Content capture is on somewhere (the system prompt and tool schemas ride on every model call).
3. Not necessarily. Check the collector, the token and the clients' endpoint before concluding nobody is using it. This is why you alert on absence of data.
</details>

## Where to go next

Run this workshop with each persona and have them bring one real question the data should answer. Record anything that differs from these modules in [VERIFICATION.md](../VERIFICATION.md).
