#!/usr/bin/env bash
# Stack smoke test, free to run (no Copilot, no credits): posts synthetic OTLP and checks
# the collector archives it, the redact overlay strips sensitive attributes, and the auth
# overlay rejects unauthenticated clients.   Usage: lab/tests/smoke.sh   (needs docker)
set -euo pipefail
cd "$(dirname "$0")/.."

export COMPOSE_PROJECT_NAME=copilot-otel-smoke
export LAB_OTLP_GRPC_PORT=${LAB_OTLP_GRPC_PORT:-25317} LAB_OTLP_HTTP_PORT=${LAB_OTLP_HTTP_PORT:-25318} LAB_UI_PORT=${LAB_UI_PORT:-25888}
tmp=$(mktemp -d)
F=(-f compose.yaml)
pass() { echo "PASS $*"; }
fail() { echo "FAIL $*"; docker compose "${F[@]}" logs --tail 30 otel-collector || true; exit 1; }
wait_for() { for _ in $(seq 1 40); do eval "$1" && return 0; sleep 1; done; return 1; }
cleanup() { docker compose -f compose.yaml -f compose.auth.yaml down -v >/dev/null 2>&1 || true; rm -rf "$tmp" 2>/dev/null || true; }
trap cleanup EXIT

url="http://localhost:${LAB_OTLP_HTTP_PORT}"
trace() { # <marker> -> OTLP/JSON with sensitive attributes
cat <<J
{"resourceSpans":[{"resource":{"attributes":[{"key":"service.name","value":{"stringValue":"smoke"}},{"key":"deployment.environment.name","value":{"stringValue":"client-says-prod"}}]},
"scopeSpans":[{"scope":{"name":"smoke"},"spans":[{"traceId":"0af7651916cd43dd8448eb211c80319c","spanId":"b7ad6b7169203331",
"name":"chat test-model","kind":3,"startTimeUnixNano":"1700000000000000000","endTimeUnixNano":"1700000001000000000",
"attributes":[{"key":"marker","value":{"stringValue":"$1"}},
{"key":"gen_ai.input.messages","value":{"stringValue":"SECRET-PROMPT-$1"}},
{"key":"github.copilot.context.skills","value":{"stringValue":"[\"secret-skill-$1\"]"}}]}]}]}]}
J
}
post() { curl -s -o /dev/null -w '%{http_code}' -X POST -H 'content-type: application/json' "${@:2}" -d "$1" "$url/v1/traces"; }
# Copy the archive out of the named volume. The collector owns the file (uid 10001), so a
# host bind mount behaves differently on Linux and Docker Desktop; `cp` works everywhere.
archived() { docker compose "${F[@]}" cp otel-collector:/data/archive.jsonl "$tmp/archive.jsonl" >/dev/null 2>&1 && grep -qs "$1" "$tmp/archive.jsonl"; }
archived_fixed() { docker compose "${F[@]}" cp otel-collector:/data/archive.jsonl "$tmp/archive.jsonl" >/dev/null 2>&1 && grep -qsF "$1" "$tmp/archive.jsonl"; }

echo "== base stack"
docker compose "${F[@]}" up -d >/dev/null
wait_for "curl -fs -o /dev/null localhost:${LAB_UI_PORT}" || fail "dashboard UI not reachable"; pass "dashboard UI reachable"
wait_for "[ \"\$(post '{\"resourceSpans\":[]}')\" = 200 ]" || fail "collector OTLP not accepting"; pass "collector accepting OTLP"
wait_for "post \"\$(trace base)\" >/dev/null; sleep 1; archived marker.*base" || fail "span not archived"; pass "span reached the archive"
archived "SECRET-PROMPT-base" && pass "without redaction, content is archived (expected: this is what the overlay prevents)" || fail "baseline should contain content"
archived_fixed '"stringValue":"client-says-prod"' && fail "client-supplied environment tag survived"
archived_fixed '{"key":"deployment.environment.name","value":{"stringValue":"lab"}}' || fail "collector environment tag missing"
pass "collector environment tag overrides the client's"

echo "== redact overlay"
F=(-f compose.yaml -f compose.redact.yaml)
docker compose "${F[@]}" up -d --force-recreate otel-collector >/dev/null
wait_for "[ \"\$(post '{\"resourceSpans\":[]}')\" = 200 ]" || fail "collector not back after redact overlay"
wait_for "post \"\$(trace redact)\" >/dev/null; sleep 1; archived marker.*redact" || fail "redacted span not archived"
archived "SECRET-PROMPT-redact" && fail "prompt content survived redaction"; pass "prompt content stripped"
archived "secret-skill-redact" && fail "skill names survived redaction"; pass "skill names stripped"

echo "== auth overlay"
F=(-f compose.yaml -f compose.auth.yaml)
export LAB_TOKEN=smoke-token LAB_DASHBOARD_TOKEN=smoke-ui
docker compose "${F[@]}" up -d --force-recreate >/dev/null
wait_for "[ \"\$(post '{}')\" = 401 ]" || fail "unauthenticated OTLP not rejected"; pass "unauthenticated OTLP rejected (401)"
[ "$(post '{"resourceSpans":[]}' -H "Authorization: Bearer $LAB_TOKEN")" = 200 ] || fail "authenticated OTLP rejected"
pass "authenticated OTLP accepted (200)"
echo "ALL PASSED"
