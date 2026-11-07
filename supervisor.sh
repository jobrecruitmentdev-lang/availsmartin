#!/bin/bash
PROJECT_DIR="/home/u390470426/availsmart"
PID_FILE="/tmp/availsmart_supervisor.pid"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        exit 0
    fi
fi

echo $$ > "$PID_FILE"

while true; do
    bash "$PROJECT_DIR/watchdog.sh" >/dev/null 2>&1
    sleep 10
done
