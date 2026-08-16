import html
import re

from .base import BaseScraper
from .. import config


class ChristiesScraper(BaseScraper):
    name = "christies"
    label = "Christie's"

    API = "https://apim.christies.com.cn/lots"
    IMG_BASE = "https://www.christies.com.cn"

    def run(self):
        lots = []
        sales = {}
        for keyword in config.CHINESE_KEYWORDS:
            page = 1
            while page <= config.MAX_PAGES:
                resp = self._get(
                    self.API,
                    params={
                        "keyword": keyword,
                        "language": "en",
                        "page": page,
                        "pageSize": 50,
                        "geocountrycode": "CN",
                    },
                    headers={"Accept": "application/vnd.christies.v1+json"},
                )
                if resp is None:
                    break
                try:
                    data = resp.json()
                except Exception:
                    break
                items = data.get("lots") or []
                for it in items:
                    lot = self._parse_lot(it, keyword)
                    if lot:
                        lots.append(lot)
                        sid = lot["sale_id"]
                        if sid:
                            sales[sid] = sales.get(sid) or self._parse_sale(it)
                total = data.get("resultInfo", {}).get("totalHits") or 0
                if not items or page * 50 >= total or len(lots) > 1500:
                    break
                page += 1
                self._sleep()
        return lots, list(sales.values())

    def _parse_lot(self, it, keyword):
        try:
            lot_id = str(it.get("id") or it.get("objectIdDotCom") or "")
            if not lot_id:
                return None
            titles = it.get("titles") or {}
            est = it.get("estimatePrice") or {}
            realised = it.get("realisedPrice") or {}
            images = it.get("images") or {}
            primary = images.get("primary") or images.get("medium") or {}
            img = None
            href = primary.get("href") or primary.get("url")
            if href:
                if href.startswith("http"):
                    img = href
                else:
                    img = self.IMG_BASE + href
            withdrawn = bool(it.get("withdrawn"))
            if withdrawn:
                status = "withdrawn"
            elif realised.get("value"):
                status = "sold"
            else:
                status = "upcoming"
            sale = it.get("sale") or {}
            entry = it.get("catalogueEntry") or ""
            return {
                "source": self.name,
                "source_lot_id": lot_id,
                "sale_id": str(sale.get("ID") or sale.get("Number") or it.get("auctionId") or ""),
                "sale_title": (sale.get("Title") or it.get("saleTitle") or "")[:300],
                "lot_number": (it.get("lotNumber") or "")[:50],
                "title": html.unescape(titles.get("primary") or it.get("title") or "")[:500],
                "description": html.unescape(re.sub(r"<[^>]+>", " ", entry)).strip()[:5000],
                "category": keyword,
                "estimate_low": est.get("low"),
                "estimate_high": est.get("high"),
                "estimate_currency": est.get("currency"),
                "hammer_price": None,
                "sale_price": realised.get("value"),
                "price_currency": realised.get("currency"),
                "status": status,
                "location": (sale.get("RoomCode") or sale.get("Location") or ""),
                "sale_start_date": None,
                "sale_end_date": None,
                "image_url": img,
                "source_url": it.get("url") or "",
            }
        except Exception:
            return None

    def _parse_sale(self, it):
        sale = it.get("sale") or {}
        return {
            "source": self.name,
            "source_sale_id": str(sale.get("ID") or sale.get("Number") or ""),
            "title": (sale.get("Title") or it.get("saleTitle") or "")[:300],
            "start_date": it.get("saleStartDate") or None,
            "end_date": it.get("saleEndDate") or None,
            "location": sale.get("RoomCode") or "",
            "url": it.get("url") or "",
        }
