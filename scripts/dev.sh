#!/usr/bin/env bash
# Arranca backend (uvicorn en 8000, venv de backend/.venv) y frontend (npm run dev, 5173).
# Si un puerto ya esta ocupado no arranca un duplicado y avisa.
# Uso (desde la raiz): bash scripts/dev.sh
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
BACKEND_PORT=8000
FRONTEND_PORT=5173

# Python del venv: Scripts/ en Windows (Git Bash), bin/ en Linux/macOS.
if [ -x "$BACKEND_DIR/.venv/Scripts/python.exe" ]; then
  PYTHON="$BACKEND_DIR/.venv/Scripts/python.exe"
elif [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
  PYTHON="$BACKEND_DIR/.venv/bin/python"
else
  PYTHON=""
fi

port_busy() {
  (exec 3<>"/dev/tcp/localhost/$1") >/dev/null 2>&1
}

BACKEND_PID=""
cleanup() {
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Deteniendo backend (PID $BACKEND_PID)..."
    kill "$BACKEND_PID" 2>/dev/null
  fi
}
trap cleanup EXIT INT TERM

if port_busy "$BACKEND_PORT"; then
  echo "AVISO: el puerto $BACKEND_PORT ya esta ocupado (probablemente el backend ya esta arrancado). No se inicia otro backend." >&2
elif [ -z "$PYTHON" ]; then
  echo "AVISO: no existe backend/.venv. Crealo: cd backend && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt" >&2
else
  echo "Arrancando backend en http://127.0.0.1:$BACKEND_PORT ..."
  (cd "$BACKEND_DIR" && exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT") &
  BACKEND_PID=$!
fi

if port_busy "$FRONTEND_PORT"; then
  echo "AVISO: el puerto $FRONTEND_PORT ya esta ocupado (probablemente el frontend ya esta arrancado). No se inicia otro." >&2
else
  echo "Arrancando frontend en http://localhost:$FRONTEND_PORT ..."
  (cd "$FRONTEND_DIR" && npm run dev)
fi
