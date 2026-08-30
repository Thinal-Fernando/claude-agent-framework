"""Command line entry point for the supervisor.

    python -m supervisor --project C:\\path\\to\\project

Exit codes:
    0  mission reported COMPLETE
    1  supervisor or configuration error
    2  stopped without completing (session cap, stop file, or CONTINUE)
    3  mission reported BLOCKED
    4  mission reported FAILED
"""

from __future__ import annotations

import argparse
import sys

from . import FRAMEWORK_ROOT, __version__
from .config import ConfigError, load_config
from .loop import ProjectError, run_loop
from .session import SessionError

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INCOMPLETE = 2
EXIT_BLOCKED = 3
EXIT_FAILED = 4

_STATUS_EXIT = {
    "COMPLETE": EXIT_OK,
    "BLOCKED": EXIT_BLOCKED,
    "FAILED": EXIT_FAILED,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="supervisor",
        description="Run supervised, long-running Claude Code sessions against a project.",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Path to the target project (must be a Git repo with the framework installed).",
    )
    parser.add_argument(
        "--config",
        default=str(FRAMEWORK_ROOT / "supervisor" / "config.yaml"),
        help="Path to the supervisor configuration file.",
    )
    parser.add_argument(
        "--prompt",
        default=str(FRAMEWORK_ROOT / "supervisor" / "prompts" / "session.md"),
        help="Path to the session prompt file.",
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=None,
        help="Override the configured maximum session count.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.max_sessions is not None and args.max_sessions <= 0:
        print("--max-sessions must be greater than zero", file=sys.stderr)
        return EXIT_ERROR

    try:
        config = load_config(args.config)
        outcome = run_loop(
            project_path=args.project,
            prompt_path=args.prompt,
            config=config,
            max_sessions_override=args.max_sessions,
        )
    except (ConfigError, ProjectError, SessionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        print("\nInterrupted. State on disk is preserved; rerun to resume.", file=sys.stderr)
        return EXIT_INCOMPLETE

    return _STATUS_EXIT.get(outcome.final_status, EXIT_INCOMPLETE)


if __name__ == "__main__":
    raise SystemExit(main())
