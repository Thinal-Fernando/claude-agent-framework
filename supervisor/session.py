"""Run a single Claude Code session and classify its outcome.

Phase 0 replaces two defects in the PowerShell implementation:

1. Status was detected by regex over the *entire* transcript, checking COMPLETE
   first. Any mention anywhere -- including "I am not ready to report
   SESSION_STATUS: COMPLETE" -- ended the mission. Status is now read from the
   final assistant message only, taking the last marker found.

2. Hard stops were invisible. ``--output-format json`` reports ``subtype`` and
   ``terminal_reason``, so budget and turn exhaustion are now distinguishable
   from a session that genuinely finished.

Verified against Claude Code 2.1.241:
    success                 -> subtype "success",                terminal_reason "completed"
    turn limit              -> subtype "error_max_turns",        terminal_reason "max_turns"
    budget limit            -> subtype "error_max_budget_usd",   terminal_reason "budget_exhausted"
Both limit cases return ``result: null``, so no status marker is available from
them; the supervisor treats them as CONTINUE and records why.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field

__all__ = [
    "SessionResult",
    "SessionError",
    "build_argv",
    "classify_payload",
    "find_claude",
    "run_session",
]

# Matches a status marker on its own line in the final assistant message.
_MARKER = re.compile(r"^\s*SESSION_STATUS:\s*(CONTINUE|COMPLETE|BLOCKED|FAILED)\s*$", re.MULTILINE)

# Hard stops that mean "the session ran out of resources", not "the work failed".
_LIMIT_SUBTYPES = {"error_max_turns", "error_max_budget_usd"}


class SessionError(RuntimeError):
    """Raised when a session cannot be started at all."""


@dataclass
class SessionResult:
    session_id: str
    session_number: int
    started_at: str
    finished_at: str
    status: str
    exit_code: int | None = None
    subtype: str | None = None
    terminal_reason: str | None = None
    num_turns: int | None = None
    total_cost_usd: float | None = None
    model: str | None = None
    max_turns: int | None = None
    max_budget_usd: float | None = None
    permission_mode: str | None = None
    limit_hit: bool = False
    error: str | None = None
    raw_path: str | None = None
    stderr_excerpt: str | None = None
    result_text: str | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()


def find_claude() -> str:
    """Locate the Claude Code executable, or raise a useful error."""
    found = shutil.which("claude")
    if not found:
        raise SessionError(
            "Could not find the 'claude' executable on PATH. "
            "Install Claude Code and make sure `claude --version` works."
        )
    return found


def _status_from_text(text: str | None) -> str:
    """Read the status marker from the final assistant message.

    Takes the *last* marker so a message that discusses the markers before
    reporting one still resolves correctly. Defaults to CONTINUE.
    """
    if not text:
        return "CONTINUE"
    matches = _MARKER.findall(text)
    if matches:
        return matches[-1]
    return "CONTINUE"


def classify_payload(payload: dict) -> dict:
    """Derive supervisor-facing fields from a Claude Code JSON result.

    Pure function, no I/O. This is the decision logic the whole loop rests on,
    kept separate so it can be tested without spending money.
    """
    subtype = payload.get("subtype")
    terminal_reason = payload.get("terminal_reason")
    result_text = payload.get("result")

    info = {
        "subtype": subtype,
        "terminal_reason": terminal_reason,
        "num_turns": payload.get("num_turns"),
        "total_cost_usd": payload.get("total_cost_usd"),
        "result_text": result_text,
        "limit_hit": False,
        "status": "FAILED",
        "error": None,
    }

    if subtype == "success":
        info["status"] = _status_from_text(result_text)
    elif subtype in _LIMIT_SUBTYPES:
        # Ran out of turns or budget. The work itself did not fail, and these
        # return result: null, so there is no status marker to read.
        info["limit_hit"] = True
        info["status"] = "CONTINUE"
        info["error"] = f"Session stopped early: {terminal_reason}"
    else:
        info["error"] = (
            f"Claude Code reported subtype {subtype!r} (terminal_reason {terminal_reason!r})"
        )
    return info


def build_argv(
    claude: str,
    *,
    model: str,
    max_turns: int,
    max_budget_usd: float,
    permission_mode: str,
    effort: str | None = None,
) -> list[str]:
    """Build the Claude Code command line for one supervised session.

    ``--max-turns`` is absent from ``claude --help`` in 2.1.241 but is
    functional; it was verified to return subtype ``error_max_turns``.
    """
    argv = [
        claude,
        "-p",
        "--output-format",
        "json",
        "--model",
        model,
        "--max-turns",
        str(max_turns),
        "--max-budget-usd",
        str(max_budget_usd),
        "--permission-mode",
        permission_mode,
    ]
    if effort:
        argv += ["--effort", effort]
    return argv


def run_session(
    *,
    project_path: pathlib.Path,
    prompt: str,
    session_number: int,
    model: str,
    max_turns: int,
    max_budget_usd: float,
    permission_mode: str,
    effort: str | None = None,
    claude_path: str | None = None,
    timeout_seconds: int | None = None,
) -> SessionResult:
    """Run one Claude Code session inside ``project_path`` and classify it."""
    project_path = pathlib.Path(project_path)
    state_dir = project_path / ".agent" / "state"
    if not state_dir.is_dir():
        raise SessionError(
            f"{project_path} does not contain .agent/state. Run the framework installer first."
        )

    sessions_dir = project_path / ".agent" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    claude = claude_path or find_claude()
    session_id = str(uuid.uuid4())
    started_at = _now()

    current_path = state_dir / "current-session.json"
    running = {
        "session_id": session_id,
        "session_number": session_number,
        "started_at": started_at,
        "finished_at": None,
        "status": "RUNNING",
        "exit_code": None,
        "model": model,
        "max_turns": max_turns,
        "max_budget_usd": max_budget_usd,
        "permission_mode": permission_mode,
    }
    current_path.write_text(json.dumps(running, indent=2), encoding="utf-8")

    argv = build_argv(
        claude,
        model=model,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        permission_mode=permission_mode,
        effort=effort,
    )

    raw_path = sessions_dir / f"session-{session_number:04d}-{session_id}.json"
    error: str | None = None
    stdout = ""
    stderr = ""
    exit_code: int | None = None

    try:
        completed = subprocess.run(
            argv,
            cwd=str(project_path),
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        exit_code = completed.returncode
    except subprocess.TimeoutExpired:
        error = f"Session exceeded timeout of {timeout_seconds}s and was terminated."
        exit_code = 124
    except OSError as exc:
        error = f"Could not start Claude Code: {exc}"
        exit_code = 1

    finished_at = _now()

    payload: dict | None = None
    if stdout.strip():
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            error = error or f"Claude Code returned output that is not valid JSON: {exc}"

    # Always persist what we got, even when unusable -- it is the only evidence.
    try:
        raw_path.write_text(
            stdout if stdout.strip() else json.dumps({"stderr": stderr, "error": error}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass

    result = SessionResult(
        session_id=session_id,
        session_number=session_number,
        started_at=started_at,
        finished_at=finished_at,
        status="FAILED",
        exit_code=exit_code,
        model=model,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        permission_mode=permission_mode,
        error=error,
        raw_path=str(raw_path),
        stderr_excerpt=(stderr.strip()[:2000] or None),
    )

    if payload is not None:
        info = classify_payload(payload)
        result.subtype = info["subtype"]
        result.terminal_reason = info["terminal_reason"]
        result.num_turns = info["num_turns"]
        result.total_cost_usd = info["total_cost_usd"]
        result.result_text = info["result_text"]
        result.limit_hit = info["limit_hit"]
        result.status = info["status"]
        result.error = result.error or info["error"]
    elif error is None:
        result.error = "Claude Code produced no output."

    final = result.to_dict()
    final.pop("result_text", None)
    current_path.write_text(json.dumps(final, indent=2), encoding="utf-8")

    return result


def _selftest() -> int:  # pragma: no cover - convenience entry point
    print(f"claude: {find_claude()}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_selftest())
