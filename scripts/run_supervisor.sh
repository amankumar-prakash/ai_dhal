#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="$ROOT/supervisord.conf"
CTL="$ROOT/.venv/bin/supervisorctl"
DAEMON="$ROOT/.venv/bin/supervisord"
mkdir -p "$ROOT/run"
export HOME="${HOME:-/home/ai_lab}"

_status() {
  "$CTL" -c "$CONF" status 2>/dev/null || true
}

_wait_running() {
  local name="$1" tries="${2:-30}"
  local i
  for ((i = 0; i < tries; i++)); do
    if "$CTL" -c "$CONF" status "$name" 2>/dev/null | grep -q RUNNING; then
      return 0
    fi
    sleep 1
  done
  "$CTL" -c "$CONF" status "$name" 2>/dev/null || true
  return 1
}

_start_one() {
  local name="$1"
  "$CTL" -c "$CONF" start "$name" >/dev/null 2>&1 || \
    "$CTL" -c "$CONF" restart "$name" >/dev/null 2>&1 || true
}

_staggered_start() {
  # Heavy workers abort (SIGABRT / can't start thread) if all spawn at once.
  local order=(api_service hexstrike_server red_team_backend blue_team_backend secure_dash)
  local name
  for name in "${order[@]}"; do
    _start_one "$name"
    _wait_running "$name" 40 || echo "warn: $name not RUNNING yet"
    sleep 1
  done
}

cmd="${1:-start}"
case "$cmd" in
  start)
    if [[ -S "$ROOT/run/supervisor.sock" ]] && "$CTL" -c "$CONF" status >/dev/null 2>&1; then
      echo "supervisord already running — ensuring programs are up"
      _staggered_start
      _status
      exit 0
    fi
    # Spawn supervisord with autostart disabled via temporary override would be
    # ideal; instead start daemon then stagger program starts after a brief pause.
    # Programs with autostart=true will race — stop them then bring up in order.
    "$DAEMON" -c "$CONF"
    sleep 2
    "$CTL" -c "$CONF" stop all >/dev/null 2>&1 || true
    sleep 1
    _staggered_start
    _status
    ;;
  stop)
    "$CTL" -c "$CONF" shutdown || true
    ;;
  restart)
    if [[ -S "$ROOT/run/supervisor.sock" ]] && "$CTL" -c "$CONF" status >/dev/null 2>&1; then
      "$CTL" -c "$CONF" stop all >/dev/null 2>&1 || true
      sleep 2
      fuser -k 5173/tcp 8000/tcp 8001/tcp 8002/tcp 8005/tcp >/dev/null 2>&1 || true
      sleep 1
      _staggered_start
      _status
    else
      "$0" start
    fi
    ;;
  status)
    _status
    ;;
  logs)
    tail -n "${2:-80}" "$ROOT/run"/*.log "$ROOT/run"/*.err.log 2>/dev/null || true
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
