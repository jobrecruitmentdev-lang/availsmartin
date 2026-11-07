#!/bin/bash
SOCK="/home/u390470426/availsmart/gunicorn.sock"
PROJECT_DIR="/home/u390470426/availsmart"
GUNICORN="$PROJECT_DIR/venv/bin/gunicorn"
LOG_FILE="$PROJECT_DIR/watchdog.log"

RESPONSE=$(curl -s -m 3 -o /dev/null -w "%{http_code}" --unix-socket "$SOCK" http://localhost/ 2>/dev/null)

if [ "$RESPONSE" != "200" ] && [ "$RESPONSE" != "301" ] && [ "$RESPONSE" != "302" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backend down (Response: $RESPONSE). Respawning Gunicorn..." >> "$LOG_FILE"
    pkill -9 -f "gunicorn.*availsmart" 2>/dev/null
    rm -f "$SOCK"
    cd "$PROJECT_DIR"
    nohup "$GUNICORN" availsmart.wsgi:application \
        --bind "unix:$SOCK" \
        --workers 2 \
        --max-requests 1000 \
        --max-requests-jitter 50 \
        --timeout 60 \
        --chdir "$PROJECT_DIR" >> "$PROJECT_DIR/gunicorn_sock.log" 2>&1 &
    sleep 2
    chmod 666 "$SOCK" 2>/dev/null
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Gunicorn respawned successfully." >> "$LOG_FILE"
fi
