#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export STUDENT_INFO_DATA_DIR="$PWD/data"
export STUDENT_DB_PATH="$STUDENT_INFO_DATA_DIR/students.db"
export STUDENT_INFO_PORT="${STUDENT_INFO_PORT:-8013}"

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" portable_launcher.py
