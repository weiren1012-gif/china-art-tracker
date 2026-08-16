import html
import re

from .base import BaseScraper

BASE = "https://www.polyauctionhk.com/api/public/front"
KEY = "fea4f323d0e24ab30d267e290b45fd8e"


class PolyScraper(BaseScraper):
    name = "poly"
    label = "Poly 保利香港"

    def run(self):
        lots = []
        sales = {}
        # 拍卖会列表(即将 + 过往)
        for a_type in ("upcoming", "archive"):
            resp = self._get(
                f"{BASE}/auction/list",
                params={"page": 1, "limit": 50, "registered_auction": 1, "type": a_type},
                headers={"Accept": "application/json", "Cccrm-Client-Secret-Key": KEY},
            )
            if resp is None:
                continue
            try:
                auctions = (resp.json() or {}).get("data", {}).get("list") or []
            except Exception:
                continue
            for a in auctions[:12]:
                self._collect_auction(a, lots, sales)
            self._sleep()
        return lots, list(sales.values())

    def _collect_auction(self, a, lots, sales):
        aid = str(a.get("uid") or "")
        if not aid:
            return
        title = (a.get("auction_name_tc") or a.get("auction_name_en") or "")[:300]
        sales[aid] = {
            "source": self.name,
            "source_sale_id": aid,
            "title": title,
            "start_date": a.get("auction_start_date"),
            "end_date": None,
            "location": "香港",
            "url": a.get("page_url") or "",
        }
        # 专场
        resp = self._get(
            f"{BASE}/auction/saleroom/list",
            params={"page": 0, "limit": 50, "auction_id": aid, "type": "archive"},
            headers={"Accept": "application/json", "Cccrm-Client-Secret-Key": KEY},
        )
        if resp is None:
            return
        try:
            rooms = (resp.json() or {}).get("data", {}).get("list") or []
        except Exception:
            return
        for room in rooms:
            room_title = str(room.get("saleroom_name_tc") or "")
            if not any(k in room_title for k in ("中國古董", "中國書畫", "高古", "佛", "瓷", "玉", "珍玩", "古董")):
                continue
            self._collect_room(room, aid, title, lots)

    def _collect_room(self, room, aid, sale_title, lots):
        rid = str(room.get("uid") or "")
        if not rid:
            return
        page = 0
        while page < 50:
            resp = self._get(
                f"{BASE}/auction/saleroom/lots/list",
                params={"saleroom_id": rid, "page": page, "limit": 100, "order": "lot_id", "order_direction": "asc"},
                headers={"Accept": "application/json", "Cccrm-Client-Secret-Key": KEY},
            )
            if resp is None:
                break
            try:
                data = resp.json()
                items = (data.get("data") or {}).get("list") or []
            except Exception:
                break
            for it in items:
                lot = self._parse_lot(it, aid, sale_title)
                if lot:
                    lots.append(lot)
            total = (data.get("data") or {}).get("total") or 0
            if not items or len(items) < 100 or (page + 1) * 100 >= total:
                break
            page += 1
            self._sleep()

    def _parse_lot(self, it, aid, sale_title):
        try:
            lid = str(it.get("uid") or "")
            if not lid:
                return None
            title = html.unescape(re.sub(r"<[^>]+>", " ", str(it.get("name_tc") or it.get("name_en") or ""))).strip()
            desc = html.unescape(re.sub(r"<[^>]+>", " ", str(it.get("description_tc") or ""))).strip()
            images = it.get("images") or []
            img = images[0].get("image") if images else ""
            cat = ((it.get("category") or {}).get("name_tc") or "")[:100]
            status = str(it.get("lot_status") or "").lower()
            final = it.get("sold_price") or it.get("hammer_price")
            return {
                "source": self.name,
                "source_lot_id": lid,
                "sale_id": aid,
                "sale_title": sale_title[:300],
                "lot_number": str(it.get("lot_id") or "")[:50],
                "title": title[:500],
                "description": desc[:5000],
                "category": cat,
                "estimate_low": it.get("estimate_start_price"),
                "estimate_high": it.get("estimate_end_price"),
                "estimate_currency": "HKD",
                "hammer_price": it.get("hammer_price"),
                "sale_price": it.get("sold_price"),
                "price_currency": "HKD",
                "status": status if status in ("sold", "unsold", "withdrawn") else "upcoming",
                "location": "香港",
                "sale_start_date": it.get("saleroom_date"),
                "sale_end_date": it.get("saleroom_date"),
                "image_url": img,
                "source_url": f"https://www.polyauctionhk.com{it.get('page_url') or ''}" if it.get("page_url") else "",
            }
        except Exception:
            return None
