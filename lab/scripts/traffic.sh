#!/usr/bin/env bash
# Generate three small, deliberately different Copilot CLI sessions so every
# exercise has data to look at. Each run spends a few AI credits.
#
#   lab/scripts/traffic.sh
#   LAB_ENDPOINT=http://localhost:14318 lab/scripts/traffic.sh
#
# happy    normal work: read a file, create a file, run a command
# failing  a shell command that exits non-zero
# content  the same failure, with content capture ON (compare with "failing")
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
command -v copilot >/dev/null || { echo "copilot CLI not found on PATH" >&2; exit 1; }
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
git -C "$work" init -q
echo "hello" > "$work/a.txt"

run() { # <scenario> <capture-content> <prompt>
  (
    cd "$work"
    export LAB_NAME=copilot-lab LAB_SCENARIO="$1" LAB_CAPTURE_CONTENT="$2"
    # shellcheck source=/dev/null
    . "$root/env/copilot-otel.sh"
    echo "== $1 (capture content: $2)"
    copilot -p "$3" --allow-all-tools 2>&1 | tail -4
  )
}

run happy   false "Read a.txt, create b.txt containing the word world, then run 'ls' in bash. Be brief."
run failing false "Run 'cat /nonexistent-file' in bash and report the error in one sentence."
run content true  "Run 'cat /nonexistent-file' in bash and report the error in one sentence."

echo
echo "Done. Telemetry is flushed within a few seconds. In the dashboard, look for the"
echo "service copilot-lab, and the lab.scenario values happy, failing and content."
