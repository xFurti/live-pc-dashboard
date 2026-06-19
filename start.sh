#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Re-exec with bash if invoked via sh (e.g. broken shebang or ./start.sh without +x).
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

find_python() {
  for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
      echo "$cmd"
      return 0
    fi
  done
  return 1
}

if ! PY="$(find_python)"; then
  echo "Python 3.10+ is required but was not found on PATH."
  echo "Install Python 3 and ensure python3 is on your PATH."
  exit 1
fi

if [ ! -x "venv/bin/python" ]; then
  echo "Creating virtual environment..."
  "$PY" -m venv venv
fi

# shellcheck source=/dev/null
. "venv/bin/activate"

pip install -r requirements.txt

echo ""
echo "Dashboard: http://127.0.0.1:8000"
echo "Press Ctrl+C to stop the server."
echo ""

exec python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
