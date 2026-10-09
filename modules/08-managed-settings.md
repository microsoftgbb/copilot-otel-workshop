# 08. Managing OTel with enterprise managed settings (lab)

**Goal:** enforce Copilot OpenTelemetry across an enterprise using managed settings: write the `telemetry` block, deliver it three different ways, know what wins when sources conflict, and verify that it works.

This module is **documented, not reproduced**. Reproducing it needs a GitHub enterprise and administrator rights, which this repo's authors did not use. Everything below comes from the official pages listed at the end, plus a local validator in this repo. Record what you find in [VERIFICATION.md](../VERIFICATION.md).

## What managed settings are

A central way to define Copilot client behaviour that users cannot override locally. OTel is one setting among many (`model`, `permissions.*`, `sandbox`, `allowedMcpServers` and more). Supported clients are the Copilot CLI, VS Code, the Copilot app, the Copilot cloud agent and JetBrains IDEs, **but not every client supports every key**. For `telemetry`, the reference says it is supported for **Copilot CLI and VS Code**, and the [2026-09-22 changelog](https://github.blog/changelog/2026-09-22-opentelemetry-in-the-github-copilot-app/) adds the Copilot app. Check the current reference before promising coverage for another client.

## The `telemetry` block

```json
{
  "telemetry": {
    "enabled": true,
    "endpoint": "https://otel.example.com:4318",
    "protocol": "http/protobuf",
    "captureContent": false,
    "lockCaptureContent": true,
    "serviceName": "copilot",
    "resourceAttributes": { "deployment.environment.name": "production", "team": "platform" },
    "headers": { "Authorization": "Bearer REPLACE_WITH_INGEST_TOKEN" }
  }
}
```

| Key | Type | Meaning |
|---|---|---|
| `enabled` | boolean | Turn export on or off |
| `endpoint` | string | Your OTLP collector URL |
| `protocol` | string | `http/json` or `http/protobuf` |
| `captureContent` | boolean | Include prompt and response content |
| `lockCaptureContent` | boolean | Stop users changing `captureContent` |
| `serviceName` | string | `service.name` |
| `resourceAttributes` | object | Tags on all exported telemetry |
| `headers` | object | HTTP headers, for example `Authorization` |

Notice what is **not** here: the SDK's `otlpEndpoint`, the environment variable names, or per-agent identity. The file is static and fleet-wide.

## Lab 1: lint your block

This repo ships a local lint so mistakes surface before rollout. It is **not** GitHub's validator (that runs server-side, Lab 3), and it only checks the `telemetry` block:

```bash
python3 lab/scripts/managed_settings.py validate lab/managed-settings/telemetry.example.json
```

Now break it on purpose. Copy the file, then try the SDK-style key `otlpEndpoint`, `"protocol": "grpc"`, `"enabled": "yes"`, or put a real-looking token in `headers`, and read the messages. Exit code 1 means errors; warnings (plain `http://`, content capture on, capture not locked, a credential in the file) exit 0 but deserve a decision.

## Lab 2: choose a delivery method

| Method | Applies to | Good for | Watch for |
|---|---|---|---|
| **Server-managed** (`.github-private` repo) | Users who receive a Copilot licence from your enterprise or its organisations, on all clients including the cloud agent | Review workflow, audit history, **team overrides** | Does not apply to users licensed elsewhere. In the CLI, if the fetch fails and nothing is cached, the policy is unavailable for that session |
| **MDM** | Any user on the device, whoever licenses them | IT-owned, non-negotiable policy; device-group targeting | macOS and Windows only; **values must be strings** |
| **File-based** | Any user on the device | Linux, containers, Codespaces, and where the others are unavailable | The CLI rejects unsafe files (below) |

You can combine them, for example MDM for hard security policy and server-managed for settings that change often. That makes it harder to know which value a user gets, so read the precedence section first.

### Server-managed, step by step

From [Getting started with enterprise-managed settings](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-enterprise/use-managed-settings/get-started):

1. Create a `.github-private` repository in a designated organisation, and select it as your enterprise's source of client governance ([instructions](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-enterprise/manage-agents/create-github-private-repo)).
2. Create `copilot/managed-settings.json` with your `telemetry` block and commit it to the **default branch**.
3. Restrict who can edit that file to administrators and AI managers.
4. Wait for refresh: supported clients pick the settings up **within about an hour**. Restarting the client or signing in again refreshes immediately.

Settings apply to every user who receives a Copilot licence from your enterprise, **whether or not they can see the repository**.

> **Do not put a real secret in this file.** The guide recommends internal visibility for the repository so enterprise members can read the governance settings, and the file is delivered to every managed client. A bearer token in `headers` should therefore be treated as readable by all of them. Options: a write-only ingest token you accept is discoverable and can rotate; network controls or mTLS at your collector instead of a token; or a more restricted repository (settings still apply to users who cannot see it, per the guide). This is an inference from the guide's visibility advice, so confirm it against your own repository settings.

### File-based

Place `managed-settings.json` here:

| OS | Location |
|---|---|
| macOS | `/Library/Application Support/GitHubCopilot/managed-settings.json` |
| Windows | `%ProgramFiles%\GitHubCopilot\managed-settings.json` |
| Linux | `/etc/github-copilot/managed-settings.json` |

For the **CLI on macOS and Linux** the file must be a regular file owned by `root`, not group-writable or world-writable, and **not a symbolic link**, or the CLI rejects it. Users must restart clients to load a change. Machines that never receive the file are not restricted.

### MDM

MDM does not deploy a JSON file. It deploys individual settings as operating-system string values:

| OS | Location |
|---|---|
| Windows | `REG_SZ` values under `HKEY_LOCAL_MACHINE\SOFTWARE\Policies\GitHubCopilot` |
| macOS | Forced managed preferences for the `com.github.copilot` domain |
| Linux | Not supported. Use file-based |

Nested settings use dot-separated keys, and booleans, arrays and objects are stored as JSON text inside a string. Let the tool do the conversion:

```bash
python3 lab/scripts/managed_settings.py mdm lab/managed-settings/telemetry.example.json
python3 lab/scripts/managed_settings.py mdm lab/managed-settings/telemetry.example.json --format reg > telemetry.reg
```

```
key                               value (string)
telemetry.enabled                 true
telemetry.endpoint                https://otel.example.com:4318
telemetry.resourceAttributes      {"deployment.environment.name":"production","team":"platform"}
```

The tool applies the documented string rules to `telemetry`. **Whether MDM expects `telemetry.resourceAttributes` as JSON text or further flattened is not shown for this key in the docs**, so test on one device first. Clients check MDM policy hourly and need no restart; in VS Code an administrator can force a check with the `Developer: Sync Account Policy` command.

## Precedence: who wins

When several sources are present, earlier beats later *(documented)*:

1. MDM-managed
2. Server-managed
3. File-based
4. User-level settings

`sandbox` and `permissions.*` are the exceptions: they are composed in the most restrictive direction across methods. `telemetry` is not an exception, so for it the order above applies.

Two OTel-specific traps from the VS Code documentation:

- **In the Copilot Chat extension, OTel environment variables can still override managed values.** Remove stray `OTEL_*` and `COPILOT_OTEL_*` variables from managed devices, or enforcement can be bypassed.
- Managed identity capture and managed resource attributes override `COPILOT_OTEL_CAPTURE_IDENTITY` and `OTEL_RESOURCE_ATTRIBUTES`.

Whether the CLI and the Copilot app treat environment variables the same way is **Open**.

## What you cannot do: team overrides for telemetry

Server-managed settings support per-team specialisation with `{ "overridable": VALUE }`, a `copilot/teams/` folder and `copilot/team-mappings.json` ([overriding settings for teams](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-enterprise/use-managed-settings/override-settings-for-teams)). But the documented list of overridable keys is `model`, `autoTier`, `permissions.*`, `allowedMcpServers`, `deniedMcpServers`, `extraKnownMarketplaces`, `strictKnownMarketplaces` and `sandbox`.

**`telemetry` is not on it.** So you cannot send one team's telemetry to a different collector, or let one team opt out, through team overrides. Plan one enterprise-wide destination and separate teams afterwards using `resourceAttributes` and collector-side routing. If you need a different destination for a subset of users, the documented alternative is a different delivery method (for example file-based or MDM on those machines), whose precedence you must then check.

## Lab 3: validate and verify

**Server-side validation.** GitHub validates `copilot/managed-settings.json`, `copilot/team-mappings.json` and referenced team files automatically. Review issues at your enterprise, **AI controls**, **Agents** tab, "Copilot settings validation". If nothing is wrong the section does not appear, and if validation is temporarily unavailable your existing settings keep applying.

**On a client.** After the refresh window:

1. Start a Copilot session on a managed machine with no OTel environment variables set.
2. In your backend, look for the `service.name` you configured and the `resourceAttributes` you set. This repo's collector adds `deployment.environment.name` itself (module 04), which lets you tell collector-added tags from client-added ones.
3. Confirm content is **absent** (`python3 lab/scripts/analyze.py leaks archive.jsonl`) and that your redact overlay is still doing its job.
4. Try to defeat it as a user: set `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` and see whether content appears. Record the result per client in [VERIFICATION.md](../VERIFICATION.md) (C17, A2).
5. If a user sees nothing, check that Copilot is licensed through your enterprise (for server-managed) and, if they have licences from several billing entities, that your enterprise is selected under "Usage billed to" in their personal Copilot settings.

**Test safely.** The guide's own first example is a harmless `{ "model": "auto" }`. Prove the delivery path with a low-risk key before enabling `telemetry`, and pilot on a small team.

## Pitfalls

| Pitfall | Why it bites | Fix |
|---|---|---|
| Used the SDK's key names (`otlpEndpoint`) | Not managed-settings keys; silently ineffective or rejected | Use the table above; lint with `managed_settings.py` |
| Committed to a branch other than the default | Server-managed settings read the default branch | Commit to default |
| Expected immediate effect | Clients refresh about hourly | Restart the client to force it |
| Rolled out only to licensed users via server-managed, but need contractors | Server-managed covers users licensed by your enterprise only | Add MDM or file-based on those machines |
| `captureContent: false` without `lockCaptureContent: true` | Users may be able to turn it on | Set both |
| Real bearer token in the repo file | Readable by enterprise members, sent to all clients | Write-only rotating token, or network/mTLS controls |
| Stray environment variables on managed devices | Can override managed values in the extension | Remove them |
| File-based on Linux/macOS with a symlink or wrong owner | The CLI rejects the file | Regular file, owned by root, not group/world-writable |
| Relied on server-managed for a restriction that must always hold | CLI has no policy if the fetch fails and nothing is cached | Use MDM or file-based for must-hold restrictions |
| Wanted a per-team collector | `telemetry` is not team-overridable | One endpoint; separate by attributes |

## Check yourself

1. You set `captureContent: false` in the server-managed file only. A user exports the capture environment variable in VS Code. What do the docs suggest, and what are your two defences?
2. Contractors on personal Copilot licences use your standard laptop image. Does your `.github-private` file cover them?
3. Why is putting `Authorization: Bearer <real token>` in `headers` risky?
4. A team lead asks to send their team's traces to a separate backend. What does the documentation say about doing it with team overrides?

<details><summary>Answers</summary>

1. In the Copilot Chat extension, environment variables can still override managed values. Set `lockCaptureContent: true`, remove OTel variables from managed devices, and keep the collector redact overlay as a backstop.
2. Not through server-managed settings, which only apply to users licensed by your enterprise. Use MDM or file-based on the image, which apply regardless of licence.
3. The file is delivered to every managed client, and the guide recommends enterprise-visible repository access, so treat the token as readable by many people. Use a write-only rotating token or network controls.
4. `telemetry` is not in the documented overridable keys, so it cannot be specialised per team that way.
</details>

## Sources

- [Getting started with enterprise-managed settings](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-enterprise/use-managed-settings/get-started)
- [Choosing how to deploy enterprise-managed settings to users](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-enterprise/use-managed-settings/deploy-managed-settings)
- [Overriding enterprise-managed settings for teams](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-enterprise/use-managed-settings/override-settings-for-teams)
- [Enterprise managed settings reference](https://docs.github.com/en/copilot/reference/enterprise-administrators/enterprise-managed-settings)
- [VS Code: manage OTel configuration for your organization](https://code.visualstudio.com/docs/agents/guides/monitoring-agents)

Back to [07. GitHub operations](07-operations.md)
