"""Claude Agent Framework supervisor.

The supervisor is external to Claude on purpose: it owns the session lifecycle
so the model cannot decide how long it gets to run.
"""

from __future__ import annotations

import pathlib

__all__ = ["FRAMEWORK_ROOT", "__version__", "read_version"]

FRAMEWORK_ROOT = pathlib.Path(__file__).resolve().parent.parent


def read_version(default: str = "0.0.0") -> str:
    """Read the framework version from the repository VERSION file."""
    version_file = FRAMEWORK_ROOT / "VERSION"
    try:
        text = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return default
    return text or default


__version__ = read_version()
