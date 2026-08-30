"""Tests for session outcome classification.

The payloads below are abridged from real Claude Code 2.1.241 runs recorded
while designing this phase, so the classifier is tested against the shapes the
CLI actually emits rather than assumed ones.
"""

import json
import os
import pathlib
import stat
import sys
import tempfile
import unittest

from supervisor.session import build_argv, classify_payload, run_session

SUCCESS = {
    "is_error": False,
    "subtype": "success",
    "terminal_reason": "completed",
    "num_turns": 10,
    "total_cost_usd": 0.1001304,
    "result": "Fixed the bug.\n\nSESSION_STATUS: CONTINUE",
}

MAX_TURNS = {
    "is_error": True,
    "subtype": "error_max_turns",
    "terminal_reason": "max_turns",
    "num_turns": 2,
    "result": None,
}

BUDGET = {
    "is_error": True,
    "subtype": "error_max_budget_usd",
    "terminal_reason": "budget_exhausted",
    "num_turns": 1,
    "total_cost_usd": 0.0238319,
    "result": None,
}


class TestClassify(unittest.TestCase):
    def test_success_reads_marker(self):
        info = classify_payload(SUCCESS)
        self.assertEqual(info["status"], "CONTINUE")
        self.assertFalse(info["limit_hit"])
        self.assertIsNone(info["error"])
        self.assertEqual(info["num_turns"], 10)
        self.assertAlmostEqual(info["total_cost_usd"], 0.1001304)

    def test_each_marker_value(self):
        for marker in ("CONTINUE", "COMPLETE", "BLOCKED", "FAILED"):
            payload = dict(SUCCESS, result=f"Work done.\n\nSESSION_STATUS: {marker}")
            self.assertEqual(classify_payload(payload)["status"], marker)

    def test_missing_marker_defaults_to_continue(self):
        payload = dict(SUCCESS, result="I did some work but forgot the marker.")
        self.assertEqual(classify_payload(payload)["status"], "CONTINUE")

    def test_null_result_does_not_crash(self):
        payload = dict(SUCCESS, result=None)
        self.assertEqual(classify_payload(payload)["status"], "CONTINUE")

    def test_marker_mentioned_in_prose_is_ignored(self):
        """Regression: the old reader regexed the whole transcript and checked
        COMPLETE first, so this sentence alone ended the mission."""
        payload = dict(
            SUCCESS,
            result=(
                "I am not ready to report SESSION_STATUS: COMPLETE yet.\n"
                "\n"
                "SESSION_STATUS: CONTINUE"
            ),
        )
        self.assertEqual(classify_payload(payload)["status"], "CONTINUE")

    def test_last_marker_wins(self):
        payload = dict(
            SUCCESS,
            result="SESSION_STATUS: CONTINUE\n\nOn reflection:\n\nSESSION_STATUS: COMPLETE",
        )
        self.assertEqual(classify_payload(payload)["status"], "COMPLETE")

    def test_max_turns_is_continue_not_failure(self):
        info = classify_payload(MAX_TURNS)
        self.assertEqual(info["status"], "CONTINUE")
        self.assertTrue(info["limit_hit"])
        self.assertIn("max_turns", info["error"])

    def test_budget_exhausted_is_continue_not_failure(self):
        info = classify_payload(BUDGET)
        self.assertEqual(info["status"], "CONTINUE")
        self.assertTrue(info["limit_hit"])
        self.assertIn("budget_exhausted", info["error"])

    def test_unknown_subtype_is_failure(self):
        info = classify_payload({"subtype": "error_during_execution", "result": None})
        self.assertEqual(info["status"], "FAILED")
        self.assertFalse(info["limit_hit"])
        self.assertIn("error_during_execution", info["error"])

    def test_empty_payload_is_failure(self):
        self.assertEqual(classify_payload({})["status"], "FAILED")


class TestBuildArgv(unittest.TestCase):
    def test_contains_required_flags(self):
        argv = build_argv(
            "claude",
            model="sonnet",
            max_turns=30,
            max_budget_usd=5.0,
            permission_mode="acceptEdits",
            effort="high",
        )
        self.assertEqual(argv[0], "claude")
        self.assertIn("-p", argv)
        self.assertEqual(argv[argv.index("--output-format") + 1], "json")
        self.assertEqual(argv[argv.index("--model") + 1], "sonnet")
        self.assertEqual(argv[argv.index("--max-turns") + 1], "30")
        self.assertEqual(argv[argv.index("--max-budget-usd") + 1], "5.0")
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "acceptEdits")
        self.assertEqual(argv[argv.index("--effort") + 1], "high")

    def test_effort_optional(self):
        argv = build_argv(
            "claude",
            model="haiku",
            max_turns=5,
            max_budget_usd=1.0,
            permission_mode="dontAsk",
            effort=None,
        )
        self.assertNotIn("--effort", argv)

    def test_prompt_not_passed_as_argument(self):
        """The prompt goes over stdin, so it cannot hit argv length limits."""
        argv = build_argv(
            "claude",
            model="sonnet",
            max_turns=1,
            max_budget_usd=1.0,
            permission_mode="default",
        )
        self.assertTrue(all(not a.startswith("You are") for a in argv))


def _write_stub(directory: pathlib.Path, payload: dict) -> str:
    """Create a fake `claude` executable that prints a fixed JSON payload."""
    (directory / "payload.json").write_text(json.dumps(payload), encoding="utf-8")
    if sys.platform == "win32":
        stub = directory / "stub_claude.cmd"
        stub.write_text('@echo off\r\ntype "%~dp0payload.json"\r\n', encoding="ascii")
    else:
        stub = directory / "stub_claude.sh"
        stub.write_text(
            '#!/bin/sh\ncat "$(dirname "$0")/payload.json"\n',
            encoding="ascii",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR)
    return str(stub)


class TestRunSessionWithStub(unittest.TestCase):
    """End-to-end through subprocess, without contacting the API."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = pathlib.Path(self.tmp.name) / "project"
        (self.project / ".agent" / "state").mkdir(parents=True)

    def _run(self, payload):
        stub = _write_stub(pathlib.Path(self.tmp.name), payload)
        return run_session(
            project_path=self.project,
            prompt="do the work",
            session_number=1,
            model="haiku",
            max_turns=5,
            max_budget_usd=1.0,
            permission_mode="acceptEdits",
            claude_path=stub,
        )

    def test_success_path(self):
        result = self._run(dict(SUCCESS, result="done\n\nSESSION_STATUS: COMPLETE"))
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.subtype, "success")

    def test_budget_path(self):
        result = self._run(BUDGET)
        self.assertEqual(result.status, "CONTINUE")
        self.assertTrue(result.limit_hit)

    def test_raw_output_persisted(self):
        result = self._run(SUCCESS)
        raw = pathlib.Path(result.raw_path)
        self.assertTrue(raw.is_file())
        self.assertEqual(json.loads(raw.read_text(encoding="utf-8"))["subtype"], "success")

    def test_current_session_written_without_transcript(self):
        result = self._run(SUCCESS)
        state = json.loads(
            (self.project / ".agent" / "state" / "current-session.json").read_text(encoding="utf-8")
        )
        self.assertEqual(state["status"], result.status)
        self.assertEqual(state["permission_mode"], "acceptEdits")
        # The full assistant message is deliberately kept out of state.
        self.assertNotIn("result_text", state)

    def test_sessions_directory_created(self):
        self._run(SUCCESS)
        self.assertTrue((self.project / ".agent" / "sessions").is_dir())

    def test_missing_state_directory_is_an_error(self):
        from supervisor.session import SessionError

        bare = pathlib.Path(self.tmp.name) / "bare"
        bare.mkdir()
        with self.assertRaises(SessionError):
            run_session(
                project_path=bare,
                prompt="x",
                session_number=1,
                model="haiku",
                max_turns=1,
                max_budget_usd=1.0,
                permission_mode="default",
                claude_path="claude",
            )


class TestMalformedOutput(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = pathlib.Path(self.tmp.name) / "project"
        (self.project / ".agent" / "state").mkdir(parents=True)

    def test_non_json_output_is_failed_not_crash(self):
        directory = pathlib.Path(self.tmp.name)
        if sys.platform == "win32":
            stub = directory / "bad.cmd"
            stub.write_text("@echo off\r\necho not json at all\r\n", encoding="ascii")
        else:
            stub = directory / "bad.sh"
            stub.write_text("#!/bin/sh\necho not json at all\n", encoding="ascii")
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR)

        result = run_session(
            project_path=self.project,
            prompt="x",
            session_number=1,
            model="haiku",
            max_turns=1,
            max_budget_usd=1.0,
            permission_mode="default",
            claude_path=str(stub),
        )
        self.assertEqual(result.status, "FAILED")
        self.assertIn("not valid JSON", result.error)
        # The unusable output is still kept as evidence.
        self.assertTrue(pathlib.Path(result.raw_path).is_file())


if __name__ == "__main__":
    unittest.main()
