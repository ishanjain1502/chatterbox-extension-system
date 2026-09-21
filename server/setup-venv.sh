#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"

if command -v py >/dev/null 2>&1; then
  PYTHON=(py -3.11)
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON=(python3.11)
else
  echo "CPython 3.11 is required. Install it with:"
  echo "  winget install Python.Python.3.11"
  echo "Then re-run: ./setup-venv.sh"
  exit 1
fi

if ! "${PYTHON[@]}" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)'; then
  echo "Selected interpreter is not CPython 3.11."
  echo "Avoid MSYS/Git Bash python; use the Windows py launcher or python3.11 from python.org."
  exit 1
fi

"${PYTHON[@]}" -m venv "$VENV"
"$VENV/Scripts/python.exe" -m pip install --upgrade pip
"$VENV/Scripts/python.exe" -m pip install -r "$ROOT/requirements.txt"

echo "Virtual environment ready at $VENV"
echo "Activate with: source \"$VENV/Scripts/activate\""
