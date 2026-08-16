#!/usr/bin/env bash
# 中国文物拍卖追踪 - 一键启动
# 用法: ./start.sh [--fetch-only]
set -e
cd "$(dirname "$0")"

VENV=venv/bin/python
PORT=8001

start_web() {
    if ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
        echo "[ok] Web 服务已在端口 $PORT 运行"
    else
        nohup $VENV run.py > data/web.log 2>&1 &
        echo "[ok] Web 服务已启动: http://localhost:$PORT"
    fi
}

start_tunnel() {
    local bin=""
    for c in cloudflared /usr/local/bin/cloudflared "$HOME/.local/bin/cloudflared"; do
        command -v "$c" >/dev/null 2>&1 && bin="$c" && break
    done
    if [ -z "$bin" ]; then
        echo "[!] 未找到 cloudflared,跳过隧道"
        return
    fi
    local url
    url=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" data/tunnel.log 2>/dev/null | head -1)
    if [ -n "$url" ] && curl -s -m 10 -o /dev/null "$url" 2>/dev/null; then
        echo "[ok] 隧道已在运行: $url"
    else
        nohup "$bin" tunnel --url http://localhost:$PORT --no-autoupdate > data/tunnel.log 2>&1 &
        sleep 8
        url=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" data/tunnel.log | head -1)
        echo "[ok] 隧道已启动: $url"
    fi
}

start_web
start_tunnel
