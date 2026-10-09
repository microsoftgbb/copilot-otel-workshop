# 03. What it tracks, and what it does not (lab)

**Goal:** predict what a signal will contain before you look, and prove it from the data. This module prevents bad dashboards and privacy surprises.

"Observed" results come from Copilot CLI 1.0.95 sessions sent through this repo's collector. Signal names change between builds, so re-run Lab 1 on your version. VS Code and app behaviour here is **documented**, not reproduced.

## Lab 1: inventory your own data

```bash
lab/scripts/traffic.sh
docker compose -f lab/compose.yaml cp otel-collector:/data/archive.jsonl ./archive.jsonl   # copy the archive out
python3 lab/scripts/analyze.py inventory archive.jsonl
```

No credits? Use `lab/samples/archive.sample.jsonl` in place of `archive.jsonl` for every command in this module. The sample is a sanitized recording of real sessions (see [lab/samples](../lab/samples)).

The rest of the labs use that copy. Re-copy to refresh it. If you prefer a live file, set `LAB_DATA_DIR=./data` in `lab/.env`. Never delete the live file while the collector runs; it keeps writing to the removed file. Restart the collector instead.

## What the CLI and SDK track *(observed)*

### Spans

| Span | One per | Notable attributes |
|---|---|---|
| `invoke_agent` | User prompt (and each subagent) | `gen_ai.usage.input_tokens`, `output_tokens`, `github.copilot.nano_aiu`, `github.copilot.cost`, `github.copilot.turn_count`, `gen_ai.conversation.id`, `enduser.pseudo.id`, `github.copilot.agent.type` |
| `chat <model>` | Model call | `gen_ai.request.model`, `gen_ai.response.model`, token counts including `cache_read`, `cache_write` and `reasoning.output_tokens`, `gen_ai.response.time_to_first_chunk`, `github.copilot.nano_aiu`, `github.copilot.server_duration`, `gen_ai.request.reasoning.level`, `gen_ai.response.finish_reasons` |
| `execute_tool <name>` | Tool call | `gen_ai.tool.name`, `gen_ai.tool.type`, `gen_ai.tool.call.id`, `gen_ai.skill.name`; for shell tools `process.executable.name` and `process.exit.code` |
| `session.timing.*` | Start-up phase (SDK-hosted sessions) | `github.copilot.session.timing.phase`, `duration_ms`, `start_offset_ms` |

### Span events (the CLI's "events")

`github.copilot.mcp.server.lifecycle` (about 33 per short session, so it is chatty), `github.copilot.user.message`, `github.copilot.session.usage_info`, `github.copilot.skill.invoked`, `github.copilot.sandbox.enforcement_state`. Documented but not exercised: `github.copilot.hook.start/end/error`, `session.truncation`, `session.compaction_start`.

### Metrics

| Metric | Type | Dimensions |
|---|---|---|
| `gen_ai.client.inference.usage.input_tokens`, `output_tokens`, `cache_read.input_tokens`, `cache_write.input_tokens`, `reasoning.output_tokens` | Sum | operation, provider, request model, response model |
| `gen_ai.client.inference.operation.input_tokens`, `output_tokens` | Histogram | same |
| `gen_ai.client.operation.duration`, `time_to_first_chunk`, `time_per_output_chunk` | Histogram (s) | operation, provider, model |
| `gen_ai.invoke_agent.duration`, `inference_calls`, `tool_calls` | Histogram | none |
| `gen_ai.execute_tool.duration` | Histogram (s) | tool name, tool type |
| `github.copilot.tool.call.count` | Sum | tool name, `success` |
| `github.copilot.tool.call.duration` | Histogram (s) | tool name |
| `github.copilot.agent.turn.count` | Histogram | operation |
| `github.copilot.code.lines_added` | Sum | provider, model |
| `github.copilot.mcp.server.connection.count` | Sum | `outcome` |
| `github.copilot.sandbox.operation.count` | Sum | control, decision, enforcement point, outcome, platform |

Resource attributes on everything include `service.name` and `service.version`, plus whatever you add with `OTEL_RESOURCE_ATTRIBUTES`.

## What VS Code adds *(documented, not reproduced)*

| Addition | Detail |
|---|---|
| `copilot_chat.*` namespace | Original extension names. Several are emitted alongside `github.copilot.*` equivalents. Prefer `github.copilot.*` for new dashboards |
| Editor outcome metrics | `copilot_chat.edit.acceptance.count`, `chat_edit.outcome.count`, `lines_of_code.count`, edit survival scores, `user.feedback.count`, `user.action.count`: whether people accept agent edits. The CLI emits none of these |
| Git context | `github.copilot.git.repository`, `.branch`, `.commit_sha`, and `github.copilot.github.org` on `invoke_agent` spans when in a Git repo |
| `execute_hook` spans | One per hook execution, with decision (`pass`, `block`, `non_blocking_error`) and duration |
| Identity | With `captureIdentity`: `user.name` on agent spans, and `process.user.name` and `host.name` on the resource |
| Tool detail | `github.copilot.tool.parameters.*`, including command and file path only when content capture is on |

## Docs vs observed *(CLI 1.0.95)*

| The docs list | What was seen |
|---|---|
| `gen_ai.client.token.usage` histogram | Not present. Token usage arrived as the `gen_ai.client.inference.*` metrics above |
| `github.copilot.code.lines_removed` | Not seen. The sessions only added lines, so it may appear only when lines are removed |
| `github.copilot.hook.*` span events | Not seen. No hooks ran in those sessions |
| Events as a third signal | The CLI sends them as span events, never as OTLP logs |
| (not in the CLI table) | `gen_ai.execute_tool.duration`, `session.timing.*`, `github.copilot.sandbox.*` and `mcp.server.lifecycle` did appear |

Lesson: build dashboards from `analyze.py inventory` on **your** version, not from a doc table.

## Lab 2: tool success is not command success

```bash
python3 lab/scripts/analyze.py tools archive.jsonl
```

```
Non-zero shell exits (the tool itself still reports success=true):
  copilot-lab/failing tool=bash exit=1
  copilot-lab/content tool=bash exit=1
```

In the `failing` scenario, `cat /nonexistent-file` exits with code 1, yet `github.copilot.tool.call.count{success=true}` still counts it. "Success" means the tool ran and returned to the model. The failure is visible only in the span attribute `process.exit.code`. An alert on `success=false` will miss failing shell commands.

## Lab 3: what leaves your machine

```bash
python3 lab/scripts/analyze.py leaks archive.jsonl
```

Compare the `failing` scenario (content capture off) with `content` (on):

| | Content OFF | Content ON |
|---|---|---|
| Prompts and replies | Never exported. Searching the archive for the prompt text, file names and directory names found nothing | Full `gen_ai.input.messages` and `gen_ai.output.messages` |
| Tool arguments and results | Not exported | `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`, and the shell command in `github.copilot.tool.parameters.command` |
| **System prompt and tool schemas** | Not exported | **Exported in full on every `chat` span** (`gen_ai.system_instructions`, `gen_ai.tool.definitions`) |
| Trace data size | about 26 KB for a 2-call session | about 1.0 MB for the same session: roughly 40x |

Now the part people miss. Even with content capture **off**, these are exported:

| Attribute | Why it matters |
|---|---|
| `enduser.pseudo.id` | A stable pseudonymous user id. Lets you count distinct users, and also link one person's sessions together |
| `github.copilot.context.skills` | The plaintext **names of every installed skill** (50 in the machine used for these runs). Reveals internal tooling, and sometimes customers, by name |
| `github.copilot.context.custom_agent_names` | Names of custom agents |
| `github.copilot.context.mcp_server_names` | MCP server names, hashed (SHA-256): not readable, but stable and linkable |

Metadata is not the same as harmless. Module 04 shows how to strip these centrally.

> **VS Code detail *(documented)*:** the Agent Debug Log panel keeps full prompt and response content when OTel export is **off**. It is local to your editor, but it means "OTel off" does not mean "no content captured anywhere".

## What it does not track

| Not in the data | Detail |
|---|---|
| Whether the answer was good | No quality, correctness or outcome signal in the CLI data. Nothing about whether a change was merged or reverted |
| Money | `github.copilot.cost` is a billing **multiplier**, "not a monetary value". `nano_aiu` is AI credits in billionths (divide by 1e9). Convert to currency using your own contract |
| People, by default | Only the pseudonymous `enduser.pseudo.id`. Hostname and OS user need VS Code identity capture, or your own tags |
| Repository | The CLI emitted no repository attributes in these runs (the test repo had no remote). VS Code documents `github.copilot.git.*`; verify on your clients |
| Licences and seats | Not in OTel. Use the Copilot user management API |
| Surfaces without a configurable client | OTel is documented for the CLI, SDK, VS Code and the Copilot app. Copilot Chat on github.com and GitHub Mobile are not covered, and the [usage metrics](https://docs.github.com/en/copilot/concepts/billing-and-usage/copilot-usage-metrics/copilot-metrics) docs also exclude them |
| Guaranteed delivery | Exporters batch and send best-effort. Treat counts as very close, not as an audit ledger |
| Content, unless you opt in | See Lab 3 |

## Reading AI credits

`github.copilot.nano_aiu` / 1,000,000,000 = AI credits. `analyze.py sessions` does this, and the result matched the CLI's own "AI Credits" summary line in every run.

Within one run, cost follows caching: in one session the first model call wrote 8,047 cache tokens and cost 2.55 credits, while the next call read 59,322 cached tokens and cost 0.64. Across runs, cost also depends on the **model**: an SDK app that ended up on a different model cost 27 credits for a single call. Always group cost by `gen_ai.request.model`.

## Check yourself

1. An alert fires when `tool.call.count{success="false"}` rises. Will it catch `npm test` failing?
2. Content capture is off. Can someone reading your backend learn which internal skills your engineers use?
3. A trace is 40x bigger than expected. First suspect?
4. In VS Code you turn OTel off. Is prompt content captured nowhere?

<details><summary>Answers</summary>

1. No. A failing command still reports `success=true`; check `process.exit.code`.
2. Yes, from `github.copilot.context.skills`, unless you strip it.
3. Content capture is on (the system prompt and tool schemas ride on every model call).
4. No. The Agent Debug Log panel still captures full content locally when export is off.
</details>

Next: [04. Collect it](04-collect.md)
