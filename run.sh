#!/usr/bin/env bash
set -euo pipefail

# Simple runner for Slide Quiz demo
# - start: launch FastAPI backend (uvicorn) in background
# - stop:  stop the backend
# - status: show backend status
# - open: open index.html in default browser
# - run (default): start backend then open index.html

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$HERE"

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
UVICORN_BIN="$REPO_DIR/backend/.venv_run/bin/uvicorn"
APP_IMPORT="backend.app.main:app"
LOG_FILE="$REPO_DIR/backend/.venv_run/server.log"
PID_FILE="$REPO_DIR/backend/.venv_run/server.pid"

exists() { command -v "$1" >/dev/null 2>&1; }

is_listening() {
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1
}

pid_alive() {
  local pid="$1"
  [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1
}

status_backend() {
  local status="stopped"
  if [ -f "$PID_FILE" ]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if pid_alive "$pid"; then
      status="running (pid=$pid)"
    fi
  fi
  if is_listening; then
    echo "Backend: listening on $HOST:$PORT ($status)"
  else
    echo "Backend: not listening on $HOST:$PORT ($status)"
  fi
}

wait_for_health() {
  local url="http://$HOST:$PORT/api/health"
  local tries=20
  for _ in $(seq 1 $tries); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.3
  done
  return 1
}

start_backend() {
  if ! [ -x "$UVICORN_BIN" ]; then
    echo "Error: $UVICORN_BIN not found or not executable." >&2
    echo "Ensure the bundled virtualenv exists or install dependencies in one." >&2
    exit 1
  fi

  if is_listening; then
    echo "Backend already listening on $HOST:$PORT. Skipping start."
    return 0
  fi

  mkdir -p "$(dirname "$LOG_FILE")"
  : > "$LOG_FILE"

  echo "Starting backend (uvicorn) on $HOST:$PORT ..."
  (
    cd "$REPO_DIR"
    export STATIC_DIR="$REPO_DIR"
    nohup "$UVICORN_BIN" "$APP_IMPORT" --host "$HOST" --port "$PORT" \
      >>"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
  )

  if wait_for_health; then
    echo "Backend started and healthy at http://$HOST:$PORT"
  else
    echo "Warning: Backend did not become healthy in time. See log: $LOG_FILE" >&2
  fi
}

stop_backend() {
  local pid=""
  if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  fi
  if pid_alive "$pid"; then
    echo "Stopping backend (pid=$pid) ..."
    kill "$pid" || true
    sleep 0.5
    if pid_alive "$pid"; then
      echo "Sending SIGKILL to $pid"
      kill -9 "$pid" || true
    fi
    rm -f "$PID_FILE"
  else
    # Fallback: try to find a listener on the port
    if is_listening && exists lsof; then
      echo "Attempting to stop process listening on port $PORT ..."
      lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t | xargs -r kill || true
    else
      echo "Backend not running."
    fi
    rm -f "$PID_FILE"
  fi
}

open_frontend() {
  local index_html="$REPO_DIR/index.html"
  if [ ! -f "$index_html" ]; then
    echo "Error: $index_html not found" >&2
    exit 1
  fi
  echo "Opening $index_html in default browser ..."
  if exists open; then
    open "$index_html"
  elif exists xdg-open; then
    xdg-open "$index_html" >/dev/null 2>&1 &
  else
    echo "Please open $index_html manually in your browser." >&2
  fi
}

usage() {
  cat <<USAGE
Usage: $(basename "$0") [run|start|stop|status|open|tail]

Commands:
  run     Start backend then open index.html (default)
  start   Start backend in background
  stop    Stop backend
  status  Show backend status
  open    Open index.html in browser
  tail    Tail backend log ($LOG_FILE)

Env vars:
  PORT (default: 8000)   Host port for API
  HOST (default: 127.0.0.1)
  STATIC_DIR is set to repo root automatically
USAGE
}

cmd="${1:-run}"
case "$cmd" in
  run)
    start_backend
    open_frontend
    ;;
  start)
    start_backend
    ;;
  stop)
    stop_backend
    ;;
  status)
    status_backend
    ;;
  open)
    open_frontend
    ;;
  tail)
    [ -f "$LOG_FILE" ] || { echo "Log not found: $LOG_FILE"; exit 1; }
    tail -f "$LOG_FILE"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage
    exit 1
    ;;
esac

