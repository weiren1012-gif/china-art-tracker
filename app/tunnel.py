"""管理 Cloudflare 隧道 URL,并提供二维码生成。"""
import io
import os
import re

from . import config

TUNNEL_LOG = os.path.join(config.DATA_DIR, "tunnel.log")
_QR_BIN = os.path.join(config.DATA_DIR, "qrcode.png")


def get_tunnel_url():
    """从 tunnel.log 解析当前 trycloudflare 地址。"""
    pattern = re.compile(r"https://(?!api\.)[a-z0-9-]{8,}\.trycloudflare\.com")
    for path in (TUNNEL_LOG, "/tmp/opencode/tunnel.log"):
        try:
            with open(path, errors="ignore") as f:
                m = pattern.search(f.read())
                if m:
                    return m.group(0)
        except FileNotFoundError:
            continue
    return None


def get_qrcode_png(url=None):
    """返回二维码 PNG 字节。"""
    url = url or get_tunnel_url() or "http://localhost:8001"
    import qrcode

    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
