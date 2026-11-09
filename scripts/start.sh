#!/usr/bin/env bash
# Start PathwayFlux Forge (backend + frontend)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Backend
if [[ ! -d "$ROOT/backend/.venv" ]]; then
  python3 -m venv "$ROOT/backend/.venv"
  "$ROOT/backend/.venv/bin/pip" install -q -r "$ROOT/backend/requirements.txt"
fi

# Frontend deps
if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  (cd "$ROOT/frontend" && npm install)
fi

export PYTHONPATH="$ROOT/backend"
"$ROOT/backend/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8741 &
BACK_PID=$!

cleanup() {
  kill "$BACK_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Wait for backend
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8741/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 0.3
done

echo "Backend:  http://127.0.0.1:8741"
echo "Frontend: http://127.0.0.1:5173"
cd "$ROOT/frontend" && npm run dev -- --host 127.0.0.1 --port 5173
