"""Tests for supervisor configuration loading and validation."""

import pathlib
import tempfile
import unittest

from supervisor import FRAMEWORK_ROOT
from supervisor.config import ConfigError, load_config

VALID = """
framework:
  version: "0.4.0"

session:
  max_sessions: 5
  max_turns: 30
  max_budget_usd: 5.00
  model: "sonnet"
  effort: "high"
  permission_mode: "acceptEdits"

runtime:
  restart_delay_seconds: 3
  verbose: true
"""


class ConfigTestCase(unittest.TestCase):
    def load(self, text):
        tmp = pathlib.Path(self.tmpdir.name) / "config.yaml"
        tmp.write_text(text, encoding="utf-8")
        return load_config(tmp)

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)


class TestValid(ConfigTestCase):
    def test_loads_values(self):
        cfg = self.load(VALID)
        self.assertEqual(cfg.max_sessions, 5)
        self.assertEqual(cfg.max_turns, 30)
        self.assertEqual(cfg.max_budget_usd, 5.0)
        self.assertEqual(cfg.model, "sonnet")
        self.assertEqual(cfg.effort, "high")
        self.assertEqual(cfg.permission_mode, "acceptEdits")
        self.assertEqual(cfg.restart_delay_seconds, 3)
        self.assertIs(cfg.verbose, True)

    def test_integer_budget_coerced_to_float(self):
        cfg = self.load(VALID.replace("max_budget_usd: 5.00", "max_budget_usd: 5"))
        self.assertIsInstance(cfg.max_budget_usd, float)
        self.assertEqual(cfg.max_budget_usd, 5.0)

    def test_dotted_get(self):
        cfg = self.load(VALID)
        self.assertEqual(cfg.get("framework.version"), "0.4.0")
        self.assertEqual(cfg.get("nope.missing", "fallback"), "fallback")
        with self.assertRaises(ConfigError):
            cfg.get("nope.missing")

    def test_shipped_config_is_valid(self):
        """The config committed to the repo must actually load."""
        cfg = load_config(FRAMEWORK_ROOT / "supervisor" / "config.yaml")
        self.assertGreater(cfg.max_sessions, 0)
        self.assertIn(cfg.model, {"sonnet", "opus", "haiku", "fable"})


class TestInvalid(ConfigTestCase):
    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_config(pathlib.Path(self.tmpdir.name) / "absent.yaml")

    def test_missing_required_key(self):
        with self.assertRaises(ConfigError) as ctx:
            self.load(VALID.replace("  max_turns: 30\n", ""))
        self.assertIn("max_turns", str(ctx.exception))

    def test_unknown_model_rejected(self):
        with self.assertRaises(ConfigError) as ctx:
            self.load(VALID.replace('model: "sonnet"', 'model: "gpt-4"'))
        self.assertIn("session.model", str(ctx.exception))

    def test_unknown_effort_rejected(self):
        with self.assertRaises(ConfigError):
            self.load(VALID.replace('effort: "high"', 'effort: "turbo"'))

    def test_unknown_permission_mode_rejected(self):
        with self.assertRaises(ConfigError):
            self.load(VALID.replace('permission_mode: "acceptEdits"', 'permission_mode: "yolo"'))

    def test_zero_sessions_rejected(self):
        with self.assertRaises(ConfigError):
            self.load(VALID.replace("max_sessions: 5", "max_sessions: 0"))

    def test_negative_delay_rejected(self):
        with self.assertRaises(ConfigError):
            self.load(VALID.replace("restart_delay_seconds: 3", "restart_delay_seconds: -1"))

    def test_wrong_type_rejected(self):
        with self.assertRaises(ConfigError) as ctx:
            self.load(VALID.replace("max_turns: 30", 'max_turns: "thirty"'))
        self.assertIn("max_turns", str(ctx.exception))

    def test_boolean_not_accepted_as_int(self):
        with self.assertRaises(ConfigError):
            self.load(VALID.replace("max_turns: 30", "max_turns: true"))


if __name__ == "__main__":
    unittest.main()
