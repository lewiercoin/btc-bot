#!/bin/sh

set -eu

[ -f settings.py ] || {
    echo "Run this script from the repository root." >&2
    exit 1
}

resolve_system_python() {
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi
    if command -v python >/dev/null 2>&1; then
        command -v python
        return 0
    fi
    echo "Python 3.10+ is required but was not found in PATH." >&2
    exit 1
}

SYSTEM_PYTHON=$(resolve_system_python)

if ! "$SYSTEM_PYTHON" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"; then
    DETECTED_VERSION=$("$SYSTEM_PYTHON" -c "import sys; print('.'.join(str(part) for part in sys.version_info[:3]))")
    echo "Python 3.10+ is required. Detected: $DETECTED_VERSION" >&2
    exit 1
fi

if [ ! -d .venv ]; then
    echo "Creating virtual environment in .venv"
    "$SYSTEM_PYTHON" -m venv .venv
else
    echo "Reusing existing virtual environment in .venv"
fi

VENV_PYTHON=".venv/bin/python"
[ -x "$VENV_PYTHON" ] || {
    echo "Virtual environment python not found at $VENV_PYTHON" >&2
    exit 1
}

echo "Installing dependencies from requirements.txt"
"$VENV_PYTHON" -m pip install -r requirements.txt

mkdir -p research_lab/snapshots research_lab/runs logs

echo
echo "Setup complete."
echo "Manual steps:"
echo "1. Copy .env into the repository root if this server should reuse local environment variables."
echo "2. Copy storage/btc_bot.db into storage/ so Research Lab has the source market database."
echo "3. Run: sh scripts/server/refresh_data.sh"
echo "4. Start a tmux session and launch either optimize or autoresearch wrappers from the repo root."
