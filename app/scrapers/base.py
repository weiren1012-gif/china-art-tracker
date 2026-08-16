import time
import requests
from .. import config


class BaseScraper:
    """所有拍卖行抓取器的公共基类:会话管理、限速、重试。"""

    name = "base"
    label = "Base"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def _get(self, url, **kwargs):
        return self._request("GET", url, **kwargs)

    def _post(self, url, **kwargs):
        return self._request("POST", url, **kwargs)

    def _request(self, method, url, retries=3, **kwargs):
        kwargs.setdefault("timeout", 30)
        last_error = None
        for attempt in range(retries):
            try:
                resp = self.session.request(method, url, **kwargs)
                if resp.status_code in (200, 201):
                    return resp
                # 5xx / 限流:重试
                if resp.status_code in (403, 429, 500, 502, 503, 504) and attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                # 其他 4xx(404 等):返回响应由调用方处理
                return resp
            except requests.RequestException as e:
                last_error = e
                if attempt >= retries - 1:
                    break
                time.sleep(2 * (attempt + 1))
        if last_error is not None:
            print(f"[{self.name}] request failed {url}: {last_error}")
        return None

    def _sleep(self):
        time.sleep(config.REQUEST_DELAY)

    def run(self):
        """返回 (lots, sales)。lots/sales 为符合数据库 schema 的 dict 列表。"""
        raise NotImplementedError
