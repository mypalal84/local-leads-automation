#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHON_BIN="/Users/alexcahn/Scripts/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "No Python interpreter found." >&2
    exit 1
  fi
fi

"$PYTHON_BIN" "$SCRIPT_DIR/health_check.py"
