#!/usr/bin/env bash
# Thin launcher for the Claude Agent Framework supervisor.
#
# All real logic lives in the Python package so behaviour matches across
# platforms. This script only locates an interpreter and hands off.
#
# Usage:
#   ./start.sh --project /path/to/project
#   ./start.sh --project /path/to/project --max-sessions 3

set -euo pipefail

FRAMEWORK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

find_python() {
    for candidate in python3 python py; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then
                printf '%s\n' "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

if ! PYTHON="$(find_python)"; then
    echo "Python 3 is required but was not found on PATH. Install Python 3.9 or newer." >&2
    exit 1
fi

cd "$FRAMEWORK_ROOT"
exec "$PYTHON" -m supervisor "$@"
