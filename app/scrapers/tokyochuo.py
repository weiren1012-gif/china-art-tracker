import html
import re

from .base import BaseScraper

BASE = "https://tcabid.com/app_api/v1"
CHINESE_TERMS = ["佛", "書畫", "书画", "瓷器", "玉", "青花", "chinese", "china", "buddha",
                 "buddhist", "gilt", "buddhist figure", "jade", "porcelain", "snuff",
                 "cloisonne", "celadon"]


class TokyoChuoScraper(BaseScraper):
    name = "tokyochuo"
    label = "Tokyo Chuo"

    def run(self):
        lots = []
        sales = {}
        # 拍卖会列表(取最近若干场)
        resp = self._get(f"{BASE}/auctions", params={"page": 1, "per_page": 25})
        if resp is None:
            return [], []
        try:
            data = resp.json()
            if isinstance(data, dict):
                auctions = (data.get("auctions") or data.get("data") or []) or []
            else:
                auctions = data or []
        except Exception:
            return [], []
        for a in auctions[:8]:
            self._collect_auction(a, lots, sales)
        return lots, list(sales.values())

    def _collect_auction(self, a, lots, sales):
        aid = str(a.get("id") or "")
        if not aid:
            return
        title = (a.get("title") or "")[:300]
        sales[aid] = {
            "source": self.name,
            "source_sale_id": aid,
            "title": title,
            "start_date": a.get("start_at"),
            "end_date": None,
            "location": (a.get("place") or "")[:100],
            "url": f"https://tcabid.com/auctions/{aid}",
        }
        # 专场列表
        resp = self._get(
            f"{BASE}/auction_categories",
            params={"auction_id_eq": aid, "per_page": 50},
        )
        if resp is None:
            return
        try:
            data = resp.json()
            if isinstance(data, dict):
                cats = (data.get("auction_categories") or data.get("data") or []) or []
            else:
                cats = data or []
        except Exception:
            return
        for cat in cats:
            cat_title = str(cat.get("title") or "")
            if not any(t in cat_title for t in ("中國", "中国", "Chinese", "佛", "瓷", "書畫", "书画", "玉", "文房", "古籍")):
                continue
            self._collect_category(cat, aid, title, lots)

    def _collect_category(self, cat, aid, sale_title, lots):
        cid = str(cat.get("id") or "")
        page = 0
        while page < 30:
            resp = self._get(
                f"{BASE}/auction_items",
                params={
                    "auction_category_auction_id_eq": aid,
                    "auction_category_id_eq": cid,
                    "page": page,
                    "per_page": 100,
                    "sort": "number asc",
                },
            )
            if resp is None:
                break
            try:
                data = resp.json()
                if isinstance(data, dict):
                    items = (data.get("auction_items") or data.get("data") or []) or []
                else:
                    items = data or []
            except Exception:
                break
            for it in items:
                lot = self._parse_lot(it, aid, sale_title)
                if lot:
                    lots.append(lot)
            if len(items) < 100:
                break
            page += 1
            self._sleep()

    def _parse_lot(self, it, aid, sale_title):
        try:
            lid = str(it.get("id") or "")
            if not lid:
                return None
            title = html.unescape(re.sub(r"<[^>]+>", " ", str(it.get("title") or ""))).strip()
            desc = html.unescape(re.sub(r"<[^>]+>", " ", str(it.get("desc") or ""))).strip()
            images = it.get("images") or []
            img = ""
            if images:
                img = images[0].get("url") or images[0].get("thumb_url") or ""
            status = str(it.get("status") or "")
            final = it.get("final_price")
            return {
                "source": self.name,
                "source_lot_id": lid,
                "sale_id": aid,
                "sale_title": sale_title[:300],
                "lot_number": str(it.get("number") or "")[:50],
                "title": title[:500],
                "description": desc[:5000],
                "category": "中国文物(东京中央)",
                "estimate_low": it.get("estimate_price_from"),
                "estimate_high": it.get("estimate_price_to"),
                "estimate_currency": "JPY",
                "hammer_price": final,
                "sale_price": final,
                "price_currency": "JPY",
                "status": "sold" if final not in (None, "", 0) else "upcoming",
                "location": "日本",
                "sale_start_date": None,
                "sale_end_date": None,
                "image_url": img,
                "source_url": f"https://tcabid.com/auction_items/{lid}",
            }
        except Exception:
            return None
