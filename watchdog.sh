#!/usr/bin/env bash
# 看门狗:每 60 秒检查 Web 服务与 Cloudflare 隧道,挂了自动重启
# 用法: ./watchdog.sh &
set -u
cd "$(dirname "$0")"
VENV=venv/bin/python
PORT=8001

while true; do
    # 1) Web 服务
    if ! curl -s -m 5 -o /dev/null "http://localhost:$PORT/api/stats"; then
        echo "[$(date '+%F %T')] web down, restarting" >> data/watchdog.log
        setsid nohup $VENV run.py >> data/web.log 2>&1 < /dev/null &
        sleep 10
    fi

    # 2) Cloudflare 隧道
    URL_LINE=$(grep -oE 'https://(?!api\.)[a-z0-9-]{8,}\.trycloudflare\.com' data/tunnel.log 2>/dev/null | head -1)
    if [ -z "$URL_LINE" ] || ! curl -s -m 8 -o /dev/null "$URL_LINE" 2>/dev/null; then
        echo "[$(date '+%F %T')] tunnel down, restarting" >> data/watchdog.log
        setsid nohup /home/fn01/.local/bin/cloudflared tunnel --url http://localhost:$PORT --no-autoupdate > data/tunnel.log 2>&1 < /dev/null &
        sleep 15
        grep -oE "https://(?!api\.)[a-z0-9-]{8,}\.trycloudflare\.com" data/tunnel.log | head -1 > data/tunnel.url
    fi

    sleep 60
done
