# Sample data

`archive.sample.jsonl` is a recording of real Copilot sessions (CLI 1.0.95 and a Node SDK app) written by the lab collector, then passed through [`../scripts/sanitize.py`](../scripts/sanitize.py):

- content-bearing attribute values replaced with `[removed]` (the keys stay, so `analyze.py leaks` still shows the content scenario)
- the pseudonymous user id, skill names, custom agent names and MCP server names replaced with placeholders
- the provider's opaque response ids replaced with short stand-ins
- the file checked for the recorder's username, home directory, email addresses and token-like strings

Scenarios: `happy`, `failing`, `content` (capture was on when recorded), and `sdk`.

Because content was replaced after recording, this file does not show the roughly 40x size difference that real content capture causes. Run `scripts/traffic.sh` to see that yourself.
