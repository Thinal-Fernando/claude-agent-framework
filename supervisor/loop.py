"""The multi-session supervisor loop.

Preserves the Phase 3 lifecycle -- run sessions until Claude reports a terminal
status or the session cap is reached -- on top of the corrected session runner.

The supervisor, not the model, owns the lifecycle. Everything it needs to make
that decision comes from :class:`supervisor.session.SessionResult`.
"""

from __future__ import annotations

import pathlib
import time
from dataclasses import dataclass, field

from .config import Config
from .session import SessionError, SessionResult, find_claude, run_session

__all__ = ["LoopOutcome", "ProjectError", "run_loop", "validate_project"]

TERMINAL_STATUSES = {"COMPLETE", "BLOCKED", "FAILED"}


class ProjectError(RuntimeError):
    """Raised when the target project is not a usable framework installation."""


@dataclass
class LoopOutcome:
    sessions_run: int = 0
    total_cost_usd: float = 0.0
    final_status: str = "UNKNOWN"
    stop_reason: str = ""
    results: list[SessionResult] = field(default_factory=list)


def validate_project(project_path) -> pathlib.Path:
    """Check the target project is a git repo with the framework installed."""
    p = pathlib.Path(project_path).expanduser().resolve()
    if not p.is_dir():
        raise ProjectError(f"Project path does not exist: {p}")
    if not (p / ".git").exists():
        raise ProjectError(f"Target project is not a Git repository: {p}")
    if not (p / ".claude").is_dir():
        raise ProjectError(f"{p} does not contain .claude. Run the installer first.")
    if not (p / ".agent" / "state").is_dir():
        raise ProjectError(f"{p} does not contain .agent/state. Run the installer first.")
    return p


def _fmt_usd(value: float | None) -> str:
    return "unknown" if value is None else f"${value:.4f}"


def run_loop(
    *,
    project_path,
    prompt_path,
    config: Config,
    max_sessions_override: int | None = None,
    echo=print,
) -> LoopOutcome:
    """Run supervised sessions until a terminal status or a limit is reached."""
    project = validate_project(project_path)
    prompt_file = pathlib.Path(prompt_path)
    if not prompt_file.is_file():
        raise ProjectError(f"Session prompt not found: {prompt_file}")
    prompt = prompt_file.read_text(encoding="utf-8")

    claude = find_claude()
    max_sessions = max_sessions_override or config.max_sessions

    echo("")
    echo("=" * 60)
    echo(" Claude Agent Framework Supervisor")
    echo("=" * 60)
    echo(f"  Project      : {project}")
    echo(f"  Claude       : {claude}")
    echo(f"  Max sessions : {max_sessions}")
    echo(f"  Max turns    : {config.max_turns}")
    echo(f"  Max budget   : ${config.max_budget_usd:.2f} per session")
    echo(f"  Model        : {config.model}")
    echo(f"  Effort       : {config.effort}")
    echo(f"  Permission   : {config.permission_mode}")
    echo("")

    outcome = LoopOutcome()
    stop_file = project / ".agent" / "STOP"

    for session_number in range(1, max_sessions + 1):
        if stop_file.exists():
            outcome.stop_reason = f"Stop file present: {stop_file}"
            echo(f"\n{outcome.stop_reason}")
            break

        echo("-" * 60)
        echo(f" Session {session_number} / {max_sessions}")
        echo("-" * 60)

        try:
            result = run_session(
                project_path=project,
                prompt=prompt,
                session_number=session_number,
                model=config.model,
                max_turns=config.max_turns,
                max_budget_usd=config.max_budget_usd,
                permission_mode=config.permission_mode,
                effort=config.effort,
                claude_path=claude,
            )
        except SessionError as exc:
            outcome.final_status = "FAILED"
            outcome.stop_reason = str(exc)
            echo(f"  Could not start session: {exc}")
            break

        outcome.sessions_run += 1
        outcome.results.append(result)
        if result.total_cost_usd:
            outcome.total_cost_usd += result.total_cost_usd
        outcome.final_status = result.status

        echo(f"  Status       : {result.status}")
        echo(f"  Subtype      : {result.subtype}")
        echo(f"  Turns        : {result.num_turns}")
        echo(f"  Cost         : {_fmt_usd(result.total_cost_usd)}")
        echo(f"  Cumulative   : {_fmt_usd(outcome.total_cost_usd)}")
        if result.limit_hit:
            echo(f"  Note         : stopped early ({result.terminal_reason})")
        if result.error:
            echo(f"  Error        : {result.error}")
        if result.stderr_excerpt:
            first = result.stderr_excerpt.splitlines()[0]
            echo(f"  stderr       : {first}")
        echo("")

        if result.status in TERMINAL_STATUSES:
            outcome.stop_reason = f"Session reported {result.status}."
            echo(outcome.stop_reason)
            break

        if session_number == max_sessions:
            outcome.stop_reason = "Maximum session count reached."
            echo(outcome.stop_reason)
            break

        if config.restart_delay_seconds:
            echo(f"Continuing. Waiting {config.restart_delay_seconds}s...\n")
            time.sleep(config.restart_delay_seconds)

    echo("")
    echo("=" * 60)
    echo(" Supervisor stopped.")
    echo(f"  Sessions run : {outcome.sessions_run}")
    echo(f"  Total cost   : {_fmt_usd(outcome.total_cost_usd)}")
    echo(f"  Final status : {outcome.final_status}")
    if outcome.stop_reason:
        echo(f"  Reason       : {outcome.stop_reason}")
    echo("=" * 60)
    echo("")

    return outcome
