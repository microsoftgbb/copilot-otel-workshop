import contextlib
import getpass
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
SAMPLE = os.path.join(HERE, "..", "samples", "archive.sample.jsonl")
sys.path.insert(0, SCRIPTS)
import analyze  # noqa: E402
import sanitize  # noqa: E402


def run(cmd):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        analyze.COMMANDS[cmd](SAMPLE)
    return buf.getvalue()


class AnalyzeTests(unittest.TestCase):
    def test_sessions_rows_and_credit_conversion(self):
        out = run("sessions")
        self.assertIn("copilot-lab/happy", out)
        # nano_aiu / 1e9: the CLI printed "AI Credits 5.39" for this run
        happy = [line for line in out.splitlines() if "copilot-lab/happy" in line][0]
        self.assertIn("5.39", happy)
        self.assertIn(" 5 ", happy)  # five model calls

    def test_failing_shell_command_is_success_but_exit_code_one(self):
        out = run("tools")
        self.assertIn("copilot-lab/failing tool=bash exit=1", out)
        self.assertNotIn("copilot-lab/happy tool=bash exit", out)

    def test_leaks_only_flags_content_for_the_capture_scenario(self):
        content = run("leaks").split("IDENTIFYING")[0]
        self.assertIn("copilot-lab/content", content)
        self.assertNotIn("copilot-lab/failing", content)
        self.assertNotIn("copilot-lab/happy", content)

    def test_identifying_attributes_present_even_without_content_capture(self):
        ident = run("leaks").split("IDENTIFYING")[1]
        self.assertIn("enduser.pseudo.id", ident)
        self.assertIn("github.copilot.context.skills", ident)
        self.assertIn("copilot-lab/failing", ident)

    def test_startup_phases_only_for_sdk_session(self):
        self.assertIn("100 start-up phase spans", run("startup"))
        self.assertIn("copilot-lab-sdk/sdk", run("startup"))

    def test_summary_groups_by_service_and_model(self):
        out = run("summary")
        self.assertIn("copilot-lab-sdk", out)
        self.assertIn("claude-sonnet-5.5", out)

    def test_inventory_lists_core_spans_and_metrics(self):
        out = run("inventory")
        for needle in ("SPAN invoke_agent", "SPAN chat", "SPAN execute_tool",
                       "github.copilot.tool.call.count", "gen_ai.client.operation.duration"):
            self.assertIn(needle, out)


class SanitizeTests(unittest.TestCase):
    def _doc(self, **attrs):
        return {"resourceSpans": [{"resource": {"attributes": [
            {"key": "lab.scenario", "value": {"stringValue": "t"}}]},
            "scopeSpans": [{"spans": [{"name": "chat", "attributes": [
                {"key": k, "value": {"stringValue": v}} for k, v in attrs.items()]}]}]}]}

    def _write(self, doc):
        fh = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        fh.write(json.dumps(doc) + "\n")
        fh.close()
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def test_content_and_identity_are_replaced(self):
        path = self._write(self._doc(**{"gen_ai.input.messages": "secret prompt",
                                        "enduser.pseudo.id": "abc123", "gen_ai.response.id": "opaque-1"}))
        text = "\n".join(sanitize.sanitize(path, None))
        self.assertNotIn("secret prompt", text)
        self.assertNotIn("abc123", text)
        self.assertNotIn("opaque-1", text)

    def test_filters_by_scenario(self):
        path = self._write(self._doc())
        self.assertEqual(sanitize.sanitize(path, {"other"}), [])

    def test_refuses_to_write_when_username_remains(self):
        user = getpass.getuser()
        if len(user) <= 2:
            self.skipTest("username too short to test reliably")
        path = self._write(self._doc(**{"some.custom.attr": f"owned by {user}"}))
        with self.assertRaises(SystemExit):
            sanitize.check(sanitize.sanitize(path, None))

    def test_refuses_to_write_when_token_remains(self):
        path = self._write(self._doc(**{"some.custom.attr": "ghp_" + "a" * 30}))
        with self.assertRaises(SystemExit):
            sanitize.check(sanitize.sanitize(path, None))

    def test_committed_sample_contains_no_content_or_identity(self):
        with open(SAMPLE) as fh:
            text = fh.read()
        self.assertNotIn(getpass.getuser(), text)
        self.assertNotIn(os.path.expanduser("~"), text)


class EnvScriptTests(unittest.TestCase):
    """copilot_otel_off must restore the environment exactly, in every shell we support."""

    SCRIPT = os.path.join(HERE, "..", "env", "copilot-otel.sh")

    def _roundtrip(self, shell):
        prog = f"""
export OTEL_EXPORTER_OTLP_ENDPOINT=http://existing:4318 OTEL_SERVICE_NAME=mine OTEL_RESOURCE_ATTRIBUTES=team=x
unset COPILOT_OTEL_ENABLED
before=$(env | grep -E '^(OTEL_|COPILOT_OTEL|LAB_|_COTEL)' | sort)
. {self.SCRIPT}; . {self.SCRIPT}
[ "$OTEL_SERVICE_NAME" = copilot-lab ] || echo BAD_SERVICE
copilot_otel_off
after=$(env | grep -E '^(OTEL_|COPILOT_OTEL|LAB_|_COTEL)' | sort)
[ "$before" = "$after" ] && echo RESTORED || echo DIFFERENT
"""
        return subprocess.run([shell, "-c", prog], capture_output=True, text=True).stdout.strip()

    def test_restores_in_bash(self):
        self.assertEqual(self._roundtrip("bash"), "RESTORED")

    @unittest.skipUnless(subprocess.run(["which", "zsh"], capture_output=True).returncode == 0, "zsh not installed")
    def test_restores_in_zsh(self):
        self.assertEqual(self._roundtrip("zsh"), "RESTORED")


if __name__ == "__main__":
    unittest.main()
