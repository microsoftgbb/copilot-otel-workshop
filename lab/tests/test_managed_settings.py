import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import managed_settings as ms  # noqa: E402

EXAMPLE = os.path.join(HERE, "..", "managed-settings", "telemetry.example.json")


def good():
    with open(EXAMPLE) as fh:
        return json.load(fh)


class LintTests(unittest.TestCase):
    def test_shipped_example_has_no_errors_or_warnings(self):
        self.assertEqual(ms.lint(good()), ([], []))

    def test_unknown_key_is_an_error(self):
        doc = good()
        doc["telemetry"]["otlpEndpoint"] = "https://x"  # the SDK's name, not a managed-settings key
        errors, _ = ms.lint(doc)
        self.assertTrue(any("otlpEndpoint" in e for e in errors))

    def test_wrong_types_and_protocol(self):
        doc = good()
        doc["telemetry"]["enabled"] = "yes"
        doc["telemetry"]["protocol"] = "grpc"
        errors, _ = ms.lint(doc)
        self.assertTrue(any("`enabled` must be bool" in e for e in errors))
        self.assertTrue(any("protocol" in e for e in errors))

    def test_enabled_without_endpoint(self):
        doc = good()
        del doc["telemetry"]["endpoint"]
        self.assertTrue(any("no `endpoint`" in e for e in ms.lint(doc)[0]))

    def test_missing_block(self):
        self.assertEqual(ms.lint({"model": "auto"})[0], ["no `telemetry` block found"])

    def test_warns_on_content_capture_unlocked_and_plain_http(self):
        doc = good()
        doc["telemetry"].update(captureContent=True, lockCaptureContent=False, endpoint="http://otel.corp:4318")
        _, warnings = ms.lint(doc)
        joined = " ".join(warnings)
        self.assertIn("captureContent", joined)
        self.assertIn("plain http", joined)

    def test_unlocked_content_capture_is_flagged_when_capture_off(self):
        doc = good()
        doc["telemetry"]["lockCaptureContent"] = False
        self.assertTrue(any("lockCaptureContent" in w for w in ms.lint(doc)[1]))

    def test_real_looking_credential_in_headers_warns_but_placeholder_does_not(self):
        doc = good()
        self.assertEqual(ms.lint(doc)[1], [])
        doc["telemetry"]["headers"]["Authorization"] = "Bearer abcdef0123456789"
        self.assertTrue(any("real credential" in w for w in ms.lint(doc)[1]))

    def test_localhost_http_is_not_warned(self):
        doc = good()
        doc["telemetry"]["endpoint"] = "http://localhost:4318"
        self.assertFalse(any("plain http" in w for w in ms.lint(doc)[1]))


class MdmTests(unittest.TestCase):
    def test_flatten_follows_documented_string_rules(self):
        rows = dict(ms.flatten(good()))
        self.assertEqual(rows["telemetry.enabled"], "true")
        self.assertEqual(rows["telemetry.captureContent"], "false")
        self.assertEqual(rows["telemetry.endpoint"], "https://otel.example.com:4318")
        # objects are stored as JSON text inside the string
        self.assertEqual(json.loads(rows["telemetry.resourceAttributes"])["team"], "platform")
        self.assertTrue(all(isinstance(v, str) for v in rows.values()))

    def test_reg_output_escapes_quotes(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(ms.cmd_mdm(EXAMPLE, "reg"), 0)
        out = buf.getvalue()
        self.assertTrue(out.startswith("Windows Registry Editor Version 5.00"))
        self.assertIn(r"[HKEY_LOCAL_MACHINE\SOFTWARE\Policies\GitHubCopilot]", out)
        self.assertIn('"telemetry.enabled"="true"', out)
        self.assertIn(r'"telemetry.resourceAttributes"="{\"deployment.environment.name\":\"production\"', out)

    def test_refuses_to_convert_invalid_input(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"telemetry": {"bogus": 1}}, fh)
        self.addCleanup(os.unlink, fh.name)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ms.cmd_mdm(fh.name, "table"), 1)

    def test_validate_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ms.cmd_validate(EXAMPLE), 0)
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
                json.dump({"telemetry": {"bogus": 1}}, fh)
            self.addCleanup(os.unlink, fh.name)
            self.assertEqual(ms.cmd_validate(fh.name), 1)


if __name__ == "__main__":
    unittest.main()
