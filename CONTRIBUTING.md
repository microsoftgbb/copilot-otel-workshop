# Contributing

This workshop is meant to stay current as Copilot changes. Thank you for helping.

## Highest-value contributions

1. **Verify an open claim.** [VERIFICATION.md](VERIFICATION.md) lists what is documented but not reproduced (VS Code, the Copilot app, managed-settings precedence). Reproduce it, update the status with the version and date, and fix any module text that was wrong.
2. **Re-run after a Copilot release.** Run `lab/scripts/traffic.sh`, then `analyze.py inventory` and `leaks`, and compare with module 03. Signal names have already changed between builds.
3. **Add another surface or backend lab**, with the same discipline: say what you reproduced.

## Ground rules

- **Tag claims** as observed or documented, and say which version.
- **Never commit real telemetry.** It can contain prompts, tool output, installed skill names, hostnames, usernames and ids. Run anything you want to share through `lab/scripts/sanitize.py`, then read the result.
- **No secrets** in examples; use placeholders.
- Keep instructions runnable. If a command is shown, it should have been run.

## Checks

```bash
python3 -W error -m unittest discover -s lab/tests -p "*.py"    # unit tests and link check, no Docker needed
lab/tests/smoke.sh                                              # stack, redact and auth overlays (needs Docker)
```

CI runs both.
