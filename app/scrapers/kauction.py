import re

from .base import BaseScraper

BASE = "https://www.k-auction.com/api"
KINDS = {"Major": 1, "Weekly": 4}


class KAuctionScraper(BaseScraper):
    name = "kauction"
    label = "K Auction"

    def run(self):
        lots = []
        sales = {}
        for label, kind in KINDS.items():
            resp = self._post(
                f"{BASE}/Auction/{kind}/1",
                json={"page": 1, "page_size": 100, "page_type": "P", "artist_sort": "", "work_type": ""},
                headers={"Content-Type": "application/json"},
            )
            if resp is None:
                continue
            try:
                data = resp.json()
            except Exception:
                continue
            items = data.get("data") or []
            if not items:
                continue
            for it in items:
                lot = self._parse_lot(it)
                if lot:
                    lots.append(lot)
                    sales.setdefault(lot["sale_id"], None)
        sale_list = [s for s in (sales.get(k) for k in sales) if s]
        return lots, sale_list

    def _parse_lot(self, it):
        try:
            uid = str(it.get("uid") or "")
            if not uid:
                return None
            title = (it.get("title") or "")[:500]
            artist = it.get("artist_name") or ""
            full_title = f"{artist} {title}".strip()[:500]
            final = it.get("price_hammer")
            low = it.get("price_estimated_low")
            high = it.get("price_estimated_high")
            img = it.get("thum_file_name") or ""
            if img and not img.startswith("http"):
                img = f"https://images.k-auction.com/www/Work/0200/T/{img}"
            sale_id = str(it.get("auc_num") or "")
            return {
                "source": self.name,
                "source_lot_id": uid,
                "sale_id": sale_id,
                "sale_title": "",
                "lot_number": str(it.get("lot_num") or "")[:50],
                "title": full_title,
                "description": str(it.get("material") or "")[:1000],
                "category": "韩国拍卖(中国相关)",
                "estimate_low": low,
                "estimate_high": high,
                "estimate_currency": "KRW",
                "hammer_price": final,
                "sale_price": final,
                "price_currency": "KRW",
                "status": "sold" if final not in (None, "", 0) else "upcoming",
                "location": "韩国",
                "sale_start_date": it.get("auc_date"),
                "sale_end_date": it.get("auc_date"),
                "image_url": img,
                "source_url": f"https://www.k-auction.com/Auction/Major/{sale_id}/{uid}",
            }
        except Exception:
            return None
