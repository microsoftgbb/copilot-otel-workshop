# 05. Engineers (lab)

**Goal:** diagnose a slow, failing or expensive agent run, and compare runs.

Use the data from `traffic.sh` (or `lab/samples/archive.sample.jsonl`). For every question below there are two ways in: the **Aspire dashboard** for browsing, and **`analyze.py`** for repeatable answers you can paste into a ticket.

## Aspire dashboard map

Open http://localhost:18888 (or your `LAB_UI_PORT`).

| Page | Use it for |
|---|---|
| **Traces** | One row per trace, named `<service>: <operation>`. Click a row for the waterfall |
| **Metrics** | Pick a resource, then **Select instrument** |
| **Structured** | OTLP logs. Empty for Copilot CLI data (module 01) |

A trace can be opened directly at `/traces/detail/<traceId>`. The `lab.scenario` tag from the env script becomes part of the resource, so `happy`, `failing` and `content` are easy to tell apart.

## Question 1: where did the time go?

Open the `happy` trace. The waterfall is the five-model-call loop from module 01:

```
invoke_agent           18.2 s
  chat <model>          ~5 s    <- the model dominates
  execute_tool skill    7 ms
  chat <model>
  execute_tool view     9 ms
  ...
  execute_tool bash     52 ms
```

Read it like a profiler: wide bars are chat spans, tool bars are slivers. The common mistake is to optimise a tool when the time is in model calls (reasoning level, prompt size, number of round trips). Confirm with the numbers:

```bash
python3 lab/scripts/analyze.py sessions lab/samples/archive.sample.jsonl
```

```
service/scenario              session    calls tools       in   cached    out  credits   secs
copilot-lab/happy             cf64d7b7       5     4   300343   291237    203     5.39   18.2
copilot-lab/failing           265127bd       2     1   118722   110600     61     3.20   10.3
copilot-lab/content           9e057692       2     1   118722   110600     61     3.20    6.6
copilot-lab-sdk/sdk           edf85e96       1     0   109256        0      7    27.32    1.1
```

Five model calls for four tools is the normal one-call-per-step loop. A run with dozens of calls and few tools is thrashing. Compare `gen_ai.invoke_agent.inference_calls` with `tool_calls` in the Metrics page for the same signal.

## Question 2: what did it cost, and why?

`credits` is `github.copilot.nano_aiu` / 1e9 and matches the CLI's own "AI Credits" line. To explain a surprising number, open the `chat` spans and compare:

| Attribute | Reads as |
|---|---|
| `gen_ai.usage.input_tokens` | Prompt size sent |
| `gen_ai.usage.cache_read.input_tokens` | Part served from cache (cheap) |
| `gen_ai.usage.cache_write.input_tokens` | Part newly cached (costs more once) |
| `gen_ai.request.model` | **Cost depends heavily on it**: group by this before comparing runs |
| `gen_ai.request.reasoning.level` | More reasoning means more output tokens and time |

Look at the table above: the SDK run cost 27 credits for one call, against about 3 for each of the CLI's two-call runs. The sample's `summary` shows why:

```bash
python3 lab/scripts/analyze.py summary lab/samples/archive.sample.jsonl
```

```
Credits by model (sum of chat spans):
  copilot-lab-sdk     claude-sonnet-5.5          27.32
  copilot-lab         gpt-6.1-sol                11.79
```

Different models, so not comparable. Never compare cost across models without grouping.

## Question 3: why did my agent fail?

```bash
python3 lab/scripts/analyze.py tools lab/samples/archive.sample.jsonl
```

```
Non-zero shell exits (the tool itself still reports success=true):
  copilot-lab/failing tool=bash exit=1
  copilot-lab/content tool=bash exit=1
```

Remember: tool "success" means the tool ran, not that the command worked. Search for `process.exit.code != 0` on `execute_tool` spans. In the dashboard, open the trace, select the `execute_tool bash` span, and read `process.exit.code` and `process.executable.name`. With content capture on you would also see the command and its output, which is the fastest way to debug, and the reason capture belongs only in environments you control.

## Question 4: why is start-up slow? (SDK apps)

```bash
python3 lab/scripts/analyze.py startup lab/samples/archive.sample.jsonl
```

For the SDK example (milliseconds): `turn_preparation` about 1,500, `github_mcp_authentication` about 770, `mcp_catalog` about 500, `model_resolution` about 200. If an SDK app starts slowly, these phases tell you whether it is MCP, auth or prompt assembly. The model request itself shows up in the later `model_*` phases.

In the dashboard these appear as separate traces (`session.provisioning`, `session.mcp_startup_wait`), not under `invoke_agent`.

## Question 5: which setup behaves differently?

Resource attributes make comparisons one filter away:

- Dashboard: **Metrics**, choose a resource, compare `github.copilot.tool.call.count` and `gen_ai.invoke_agent.duration`.
- Archive: `sessions` prints one row per session with its service and scenario; sort or group in a spreadsheet.

Good habits: a stable `OTEL_SERVICE_NAME` per application or role, and tags such as `team` and `deployment.environment.name` through `OTEL_RESOURCE_ATTRIBUTES`. Never tag with a per-session value; the session is already `gen_ai.conversation.id`.

## Exercises

1. In `happy`, which model call was slowest, and what was its time to first chunk (`gen_ai.response.time_to_first_chunk`)?
2. Find every span where `process.exit.code` is not `0`. Which scenarios produced them?
3. Run `traffic.sh` twice. Is the second `happy` cheaper? Compare `cache_read` and `cache_write`.
4. Using only the dashboard, find the `failing` trace and read the exit code without enabling content capture.
5. VS Code users: run an agent chat with OTel enabled and compare its trace tree with the CLI's. What extra spans appear?

## Check yourself

1. A run takes 40 s. The `execute_tool` spans sum to 0.3 s. What should you investigate?
2. Why doesn't an SDK app's `invoke_agent` duration include the `session.timing.*` phases?

<details><summary>Answers</summary>

1. Model calls: how many, how large the prompts are, the reasoning level and the model choice.
2. They are separate traces with no conversation id, so they are not children of `invoke_agent`. Compare their timestamps with the prompt's trace to see how they overlap.
</details>

Next: [06. Engineering managers](06-managers.md)
