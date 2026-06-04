#!/bin/bash
# Start/stop the Amp Slack Bot
# Usage: ./scripts/amp-slack-bot.sh start|stop|status|restart

VAULT_PATH="${VAULT_PATH:-$(cd "$(dirname "$0")/.." && pwd)}"
VENV="$VAULT_PATH/.venv/bin/python3"
BOT="$VAULT_PATH/scripts/amp_slack_bot.py"
PIDFILE="/tmp/amp-slack-bot.pid"
LOGFILE="/tmp/amp-slack-bot.log"

start() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Amp Slack Bot already running (PID $(cat "$PIDFILE"))"
        return 1
    fi

    echo "Starting Amp Slack Bot..."
    VAULT_PATH="$VAULT_PATH" nohup "$VENV" "$BOT" >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    echo "Started (PID $!, log: $LOGFILE)"
}

stop() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm -f "$PIDFILE"
            echo "Stopped (PID $PID)"
        else
            rm -f "$PIDFILE"
            echo "PID file stale, cleaned up"
        fi
    else
        echo "Not running"
    fi
}

status() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Running (PID $(cat "$PIDFILE"))"
    else
        echo "Not running"
    fi
}

case "${1:-start}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    status)  status ;;
    *)       echo "Usage: $0 {start|stop|restart|status}" ;;
esac
