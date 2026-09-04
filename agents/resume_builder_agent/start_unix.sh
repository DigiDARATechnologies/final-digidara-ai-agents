#!/usr/bin/env sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

[ -f backend/.env ] || cp backend/.env.example backend/.env
[ -f frontend/.env ] || cp frontend/.env.example frontend/.env
[ -x backend/venv/bin/python ] || python3 -m venv backend/venv

backend/venv/bin/python -m pip install -r backend/requirements.txt
(cd frontend && npm install)

(cd backend && ../backend/venv/bin/python run.py) &
BACKEND_PID=$!
(cd frontend && npm run dev) &
FRONTEND_PID=$!

trap 'kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true' INT TERM EXIT
wait
