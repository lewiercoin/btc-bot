#!/bin/sh

set -eu

[ -f settings.py ] || {
    echo "Run this script from the repository root." >&2
    exit 1
}

resolve_uvicorn() {
    if [ -x .venv/bin/uvicorn ]; then
        printf '%s\n' ".venv/bin/uvicorn"
        return 0
    fi
    echo "uvicorn not found in .venv. Run sh scripts/server/setup.sh first." >&2
    exit 1
}

load_env_if_present() {
    if [ -f .env ]; then
        set -a
        . ./.env
        set +a
    else
        echo "Warning: .env not found in repo root." >&2
    fi
}

mkdir -p logs
load_env_if_present
UVICORN_BIN=$(resolve_uvicorn)

echo "Starting dashboard on 127.0.0.1:8080"
echo "Access via SSH tunnel: ssh -L 8080:127.0.0.1:8080 btc-bot@<server-ip> -N"

exec "$UVICORN_BIN" dashboard.server:app --host 127.0.0.1 --port 8080
