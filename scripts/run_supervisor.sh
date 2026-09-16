#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="$ROOT/supervisord.conf"
CTL="$ROOT/.venv/bin/supervisorctl"
DAEMON="$ROOT/.venv/bin/supervisord"
mkdir -p "$ROOT/run"
export HOME="${HOME:-/home/ai_lab}"

cmd="${1:-start}"
case "$cmd" in
  start)
    if [[ -S "$ROOT/run/supervisor.sock" ]] && "$CTL" -c "$CONF" status >/dev/null 2>&1; then
      echo "supervisord already running"
      "$CTL" -c "$CONF" status
      exit 0
    fi
    "$DAEMON" -c "$CONF"
    sleep 2
    "$CTL" -c "$CONF" status
    ;;
  stop)
    "$CTL" -c "$CONF" shutdown || true
    ;;
  restart)
    "$CTL" -c "$CONF" restart all || { "$0" stop; sleep 1; "$0" start; }
    ;;
  status)
    "$CTL" -c "$CONF" status
    ;;
  logs)
    tail -n "${2:-80}" "$ROOT/run"/*.log "$ROOT/run"/*.err.log 2>/dev/null || true
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
