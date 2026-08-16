import ast
import json

from .base import BaseScraper

BASE = "https://www.seoulauction.com/api"


class SeoulScraper(BaseScraper):
    name = "seoul"
    label = "Seoul Auction"

    TRADITIONAL_ART = "405"  # 고미술 Traditional Art

    def run(self):
        lots = []
        sales = {}
        # 进行中拍卖
        resp = self._get(f"{BASE}/main/ingAuctions", headers={"Accept": "application/json"})
        if resp is not None:
            try:
                data = resp.json()
                data = (data or {}).get("data") or data
                items = data.get("list") if isinstance(data, dict) else data or []
                if isinstance(items, dict):
                    items = items.get("list") or []
                for s in items[:10]:
                    sale_no = str(s.get("SALE_NO") or "")
                    if sale_no and sale_no not in sales:
                        self._collect_sale(s, sale_no, lots, sales)
            except Exception:
                pass
        # 过往拍卖
        resp = self._post(
            f"{BASE}/auction/results",
            json={"from": 0, "rows": 10, "sale_kind_cd": "", "find_word": ""},
            headers={"Accept": "application/json, text/plain, */*", "Content-Type": "application/json"},
        )
        if resp is not None:
            try:
                data = resp.json()
                data = (data or {}).get("data") or data
                items = data.get("list") or [] if isinstance(data, dict) else data or []
                if isinstance(items, dict):
                    items = items.get("list") or []
                for s in items[:10]:
                    sale_no = str(s.get("SALE_NO") or "")
                    if sale_no and sale_no not in sales:
                        self._collect_sale(s, sale_no, lots, sales)
            except Exception:
                pass
        return lots, list(sales.values())

    def _collect_sale(self, s, sale_no, lots, sales):
        title = str(s.get("TITLE_JSON") or s.get("SHORT_TITLE") or "")
        try:
            if isinstance(title, str):
                t = json.loads(title)
                title = t.get("en") or t.get("ko") or ""
        except Exception:
            pass
        sales[sale_no] = {
            "source": self.name,
            "source_sale_id": sale_no,
            "title": title[:300],
            "start_date": s.get("FROM_DT"),
            "end_date": s.get("TO_DT"),
            "location": "韩国",
            "url": f"https://www.seoulauction.com/auction/live/sales/{sale_no}/one",
        }
        # 拍品列表(古美术分类)
        page = 1
        while page <= 10:
            resp = self._get(
                f"{BASE}/auction/live/list/{sale_no}",
                params={"page": page, "size": 1000, "sortBy": "LOTAS", "search": "", "category": self.TRADITIONAL_ART},
                headers={"Accept": "application/json, text/plain, */*"},
            )
            if resp is None:
                break
            try:
                data = resp.json()
                data = (data or {}).get("data") or data
                items = data.get("list") if isinstance(data, dict) else data or []
                if isinstance(items, dict):
                    items = items.get("list") or []
            except Exception:
                break
            if not items:
                break
            for it in items:
                lot = self._parse_lot(it, sale_no, title)
                if lot:
                    lots.append(lot)
            if len(items) < 100:
                break
            page += 1
            self._sleep()

    def _parse_lot(self, it, sale_no, sale_title):
        try:
            lot_no = str(it.get("LOT_NO") or "")
            title = self._parse_json_text(it.get("LOT_TITLE_JSON")) or self._parse_json_text(it.get("LOT_TITLE"))
            artist = self._parse_json_text(it.get("ARTIST_NAME_JSON")) or self._parse_json_text(it.get("ARTIST_NAME"))
            if artist:
                title = f"{artist} {title}".strip()
            price_from = it.get("EXPE_PRICE_FROM_JSON") or ""
            price_to = it.get("EXPE_PRICE_TO_JSON") or ""
            low = self._first_number(price_from)
            high = self._first_number(price_to)
            max_bid = it.get("MAX_BID_PRICE")
            img_path = (it.get("LOT_IMG_PATH") or "").rstrip("/")
            img_name = it.get("LOT_IMG_NAME") or ""
            img = f"https://public.seoulauction.io{img_path}/{img_name}" if img_path and img_name else ""
            final = max_bid
            return {
                "source": self.name,
                "source_lot_id": f"{sale_no}-{lot_no}",
                "sale_id": sale_no,
                "sale_title": sale_title[:300],
                "lot_number": lot_no[:50],
                "title": title[:500],
                "description": "",
                "category": "韩国古美术",
                "estimate_low": low,
                "estimate_high": high,
                "estimate_currency": "KRW",
                "hammer_price": final,
                "sale_price": final,
                "price_currency": "KRW",
                "status": "sold" if final not in (None, "", 0) else "upcoming",
                "location": "韩国",
                "sale_start_date": None,
                "sale_end_date": None,
                "image_url": img,
                "source_url": f"https://www.seoulauction.com/auction/live/sales/{sale_no}/one",
            }
        except Exception:
            return None

    @staticmethod
    def _parse_json_text(s):
        """解析 {'en':..., 'ko':...} 或 {\"en\":...} 格式的多语言字段。"""
        if isinstance(s, dict):
            return str(s.get("en") or s.get("ko") or s.get("zh") or "")
        if not isinstance(s, str) or not s.strip():
            return str(s or "")
        try:
            d = json.loads(s)
            if isinstance(d, dict):
                return str(d.get("en") or d.get("ko") or d.get("zh") or "")
        except Exception:
            pass
        try:
            d = ast.literal_eval(s)
            if isinstance(d, dict):
                return str(d.get("en") or d.get("ko") or d.get("zh") or "")
        except Exception:
            pass
        return s.strip()

    @staticmethod
    def _first_number(s):
        if isinstance(s, (int, float)):
            return s
        import re

        m = re.search(r"[\d,]+", str(s or ""))
        if not m:
            return None
        try:
            return float(m.group(0).replace(",", ""))
        except ValueError:
            return None
