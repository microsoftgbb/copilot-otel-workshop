# 06. Engineering managers

**Goal:** ask questions this data can actually answer, build a small dashboard from it, and avoid the metrics that mislead.

## What OTel is good for, and what it is not

OTel shows **how agents behave and what they consume**. It does not show **whether the work was good**. Hold that line and it is very useful.

| Question | Answerable from OTel? | Source |
|---|---|---|
| How many agent sessions ran this week, and is it growing? | Yes | Count of `invoke_agent` spans, distinct `gen_ai.conversation.id` |
| How many distinct people used agents? | Approximately | Distinct `enduser.pseudo.id`, only for instrumented clients |
| What does it cost, and which model drives it? | Yes, in AI credits | `github.copilot.nano_aiu` / 1e9, grouped by `gen_ai.request.model` |
| Which tools, skills and MCP servers get used? | Yes | `execute_tool` spans, `skill.invoked` events, `mcp.server.connection.count` |
| Are agents getting stuck or looping? | Yes | `gen_ai.invoke_agent.inference_calls`, `turn_count`, run duration |
| Do shell commands fail often? | Yes, with a caveat | `process.exit.code` on `execute_tool` spans (the `success` flag is not enough) |
| Is Copilot making us faster or improving quality? | **No** | Use delivery data: PR throughput, review time, defects |
| Are developers *accepting* suggestions? | Only in VS Code *(documented)* | `copilot_chat.edit.acceptance.*` metrics. The CLI emits none |
| Who has a seat and is not using it? | **No** | Copilot user management API |
| Adoption across the whole enterprise? | **No** (partial) | [Copilot usage metrics](https://docs.github.com/en/copilot/concepts/billing-and-usage/copilot-usage-metrics/copilot-metrics): dashboards, APIs and NDJSON export |

## A manager's dashboard

Run this on the sample data:

```bash
python3 lab/scripts/analyze.py summary lab/samples/archive.sample.jsonl
```

```
service              sessions  users*  runs  credits   avg_s  tools  shell shell_fail
copilot-lab                 3       1     3    11.79    11.7      6      3          2
copilot-lab-sdk             1       1     1    27.32     1.1      0      0          0

Credits by model (sum of chat spans):
  copilot-lab-sdk     claude-sonnet-5.5          27.32
  copilot-lab         gpt-6.1-sol                11.79
```

Build the same panels in any backend:

| Panel | Metric or span | Aggregation | Read it as |
|---|---|---|---|
| Sessions per day | `invoke_agent` spans | count, by service | Usage volume |
| Active people | `enduser.pseudo.id` | distinct count per week | Reach (undercounts) |
| Credits per day, by model | `github.copilot.nano_aiu` on `chat` spans | sum / 1e9, by `gen_ai.request.model` | Spend and its driver |
| Credits per session | credits / sessions | trend | Is work getting more expensive? |
| Run duration | `gen_ai.invoke_agent.duration` | p50 and p95 | Experience; stuck runs |
| Tool mix | `github.copilot.tool.call.count` | by `gen_ai.tool.name` | What agents actually do |
| Shell failure rate | `execute_tool` with `process.exit.code != 0` / shell calls | percentage | Friction, flaky environments |

## Use it carefully

| Trap | Why it misleads |
|---|---|
| **Ranking individuals** by sessions, credits or lines | Heavy use is not good use, and cheap runs are not good runs. People will game it or stop using the tool |
| **Lines of code** (`github.copilot.code.lines_added`) as productivity | It counts what tools wrote, not what survived review. A refactor that deletes code scores zero |
| **Comparing cost across models** | A different model can cost an order of magnitude more per call. Always group by model |
| **Treating counts as exact** | Only instrumented clients report, and export is best-effort. Use trends, not decimals |
| **Reading `success=true` as working** | Failing shell commands still report success. Use the exit code |
| **Surveillance by accident** | `enduser.pseudo.id` plus your own tags can identify someone. Agree the purpose and audience before you share per-person views |

A good rule: report at **team or service level**, look at individuals only to offer help, and say so in advance.

## A weekly review you can run in 15 minutes

1. Credits per day: any spike? Open the sessions behind it (`analyze.py sessions`) and check the model and cache use.
2. Run duration p95: a long tail usually means stuck loops or heavy prompts.
3. Shell failure rate: rising means environment trouble (dependencies, permissions) that agents keep hitting.
4. Tool mix: new MCP servers or skills appearing? Is that planned?
5. Pair this with delivery data (merge time, review load). OTel explains **behaviour**; delivery data tells you **outcome**.

## Check yourself

1. Credits doubled week on week. Name three different causes.
2. Your VP asks for "lines of AI code per developer". What do you offer instead?
3. Why can't OTel tell you who has an unused seat?

<details><summary>Answers</summary>

1. More sessions, a switch to a more expensive model, or lower cache hits (larger fresh prompts). Group by model and look at cache read and write.
2. Team-level session volume, cost per session and a delivery metric (such as time to merge), with a note that OTel does not measure quality.
3. Telemetry only exists when a session runs. A seat with no sessions emits nothing; seat data comes from the user management API.
</details>

Next: [07. GitHub operations](07-operations.md)
