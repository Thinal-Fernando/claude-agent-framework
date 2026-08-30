"""Supervisor configuration loading and validation.

Reads ``supervisor/config.yaml`` through :mod:`supervisor.yamlmini`, applies
defaults, and validates values before the supervisor spends any money. Failing
here is much cheaper than failing after a session has started.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

from .yamlmini import YamlError, parse_file

__all__ = ["Config", "ConfigError", "load_config"]

# Accepted by the current Claude Code CLI. Validated up front because a bad
# value is only reported by the CLI after the process has launched.
MODELS = {"sonnet", "opus", "haiku", "fable"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
PERMISSION_MODES = {
    "default",
    "manual",
    "acceptEdits",
    "plan",
    "auto",
    "dontAsk",
    "bypassPermissions",
}

_MISSING = object()


class ConfigError(ValueError):
    """Raised when the supervisor configuration is missing or invalid."""


@dataclass
class Config:
    """Validated supervisor configuration."""

    path: pathlib.Path
    data: dict = field(repr=False)

    # session
    max_sessions: int = 20
    max_turns: int = 30
    max_budget_usd: float = 5.0
    model: str = "sonnet"
    effort: str = "high"
    permission_mode: str = "acceptEdits"

    # runtime
    restart_delay_seconds: int = 3
    verbose: bool = True

    def get(self, dotted: str, default=_MISSING):
        """Look up a nested key by dotted path, e.g. ``session.model``."""
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                if default is _MISSING:
                    raise ConfigError(f"{self.path}: missing required key '{dotted}'")
                return default
            node = node[part]
        return node


def _require(value, dotted: str, kind, path: pathlib.Path):
    if value is None:
        raise ConfigError(f"{path}: '{dotted}' is required")
    if kind is float and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, bool) and kind is not bool:
        raise ConfigError(f"{path}: '{dotted}' must be {kind.__name__}, got a boolean")
    if not isinstance(value, kind):
        raise ConfigError(
            f"{path}: '{dotted}' must be {kind.__name__}, got {type(value).__name__} ({value!r})"
        )
    return value


def _positive(value, dotted: str, path: pathlib.Path):
    if value <= 0:
        raise ConfigError(f"{path}: '{dotted}' must be greater than zero, got {value!r}")
    return value


def _one_of(value, allowed: set, dotted: str, path: pathlib.Path):
    if value not in allowed:
        options = ", ".join(sorted(allowed))
        raise ConfigError(f"{path}: '{dotted}' must be one of [{options}], got {value!r}")
    return value


def load_config(path) -> Config:
    """Load and validate the supervisor configuration file."""
    p = pathlib.Path(path)
    if not p.is_file():
        raise ConfigError(f"supervisor configuration not found: {p}")

    try:
        data = parse_file(p)
    except YamlError as exc:
        raise ConfigError(str(exc)) from exc

    cfg = Config(path=p, data=data)

    cfg.max_sessions = _positive(
        _require(cfg.get("session.max_sessions", None), "session.max_sessions", int, p),
        "session.max_sessions",
        p,
    )
    cfg.max_turns = _positive(
        _require(cfg.get("session.max_turns", None), "session.max_turns", int, p),
        "session.max_turns",
        p,
    )
    cfg.max_budget_usd = _positive(
        _require(cfg.get("session.max_budget_usd", None), "session.max_budget_usd", float, p),
        "session.max_budget_usd",
        p,
    )
    cfg.model = _one_of(
        _require(cfg.get("session.model", None), "session.model", str, p),
        MODELS,
        "session.model",
        p,
    )
    cfg.effort = _one_of(
        _require(cfg.get("session.effort", cfg.effort), "session.effort", str, p),
        EFFORTS,
        "session.effort",
        p,
    )
    cfg.permission_mode = _one_of(
        _require(
            cfg.get("session.permission_mode", cfg.permission_mode),
            "session.permission_mode",
            str,
            p,
        ),
        PERMISSION_MODES,
        "session.permission_mode",
        p,
    )

    cfg.restart_delay_seconds = _require(
        cfg.get("runtime.restart_delay_seconds", cfg.restart_delay_seconds),
        "runtime.restart_delay_seconds",
        int,
        p,
    )
    if cfg.restart_delay_seconds < 0:
        raise ConfigError(f"{p}: 'runtime.restart_delay_seconds' must not be negative")

    cfg.verbose = _require(cfg.get("runtime.verbose", cfg.verbose), "runtime.verbose", bool, p)

    return cfg
