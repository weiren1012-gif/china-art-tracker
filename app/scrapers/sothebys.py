import html
import re
import time
from datetime import datetime, timedelta, timezone

from .base import BaseScraper
from .. import config

APP_ID = "O28SY4Q7WU"
API_KEY = "e732e65c70ebf8b51d4e2f922b536496"
INDEX = "bsp_dotcom_prod_en"
URL = f"https://{APP_ID}-dsn.algolia.net/1/indexes/{INDEX}/query"


class SothebysScraper(BaseScraper):
    name = "sothebys"
    label = "Sotheby's"

    DEPARTMENTS = config.SOTHEBYS_CHINESE_DEPARTMENTS

    def run(self):
        lots = []
        sales = {}
        dept_filter = " OR ".join(f'departments:"{d}"' for d in self.DEPARTMENTS)

        # 1) 即将举行的拍品
        upcoming = self._query(
            query="",
            filters=f"({dept_filter}) AND type:\"Lot\" AND available:\"true\"",
            hits_per_page=1000,
        )
        for hit in upcoming:
            lot, sale = self._parse(hit, status_hint="upcoming")
            if lot:
                lots.append(lot)
                if sale:
                    sales[sale["source_sale_id"]] = sale
            self._sleep()

        # 2) 最近 N 天已成交的拍品
        cutoff = int((datetime.now(timezone.utc) - timedelta(days=config.RESULTS_LOOKBACK_DAYS)).timestamp() * 1000)
        sold = self._query(
            query="",
            filters=f"({dept_filter}) AND type:\"Lot\" AND available:\"false\" AND soldStatus:\"SOLD\"",
            numeric_filters=[f"startDate >= {cutoff}"],
            hits_per_page=1000,
        )
        for hit in sold:
            lot, sale = self._parse(hit, status_hint="sold")
            if lot:
                lots.append(lot)
                if sale:
                    sales[sale["source_sale_id"]] = sale
            self._sleep()
        return lots, list(sales.values())

    def _query(self, query, filters, hits_per_page=32, numeric_filters=None, page=0):
        body = {
            "query": query,
            "hitsPerPage": hits_per_page,
            "page": page,
            "filters": filters,
        }
        if numeric_filters:
            body["numericFilters"] = numeric_filters
        resp = self._post(
            URL,
            json=body,
            headers={
                "X-Algolia-Application-Id": APP_ID,
                "X-Algolia-API-Key": API_KEY,
                "Content-Type": "application/json",
            },
        )
        if resp is None:
            return []
        try:
            data = resp.json()
            return data.get("hits") or []
        except Exception:
            return []

    def _parse(self, hit, status_hint):
        try:
            lot_id = str(hit.get("objectID") or "")
            if not lot_id:
                return None, None
            title = hit.get("title") or ""
            # 拍品标题中带中文时可能包含翻译,保留完整标题
            desc = hit.get("description") or hit.get("fullText") or ""
            desc = html.unescape(re.sub(r"<[^>]+>", " ", str(desc))).strip()
            sold_status = hit.get("soldStatus")
            if sold_status == "SOLD":
                status = "sold"
            elif sold_status == "UNSOLD":
                status = "unsold"
            else:
                status = status_hint
            start_ms = hit.get("startDate")
            end_ms = hit.get("endDate")
            start_date = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).isoformat() if start_ms else None
            end_date = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).isoformat() if end_ms else None
            sale_number = hit.get("saleNumber") or ""
            sale_title = hit.get("auctionTitle") or ""
            lot = {
                "source": self.name,
                "source_lot_id": lot_id,
                "sale_id": sale_number,
                "sale_title": sale_title[:300],
                "lot_number": str(hit.get("lotNumber") or "")[:50],
                "title": title[:500],
                "description": desc[:5000],
                "category": (hit.get("departments") or [""])[0],
                "estimate_low": hit.get("lowEstimate"),
                "estimate_high": hit.get("highEstimate"),
                "estimate_currency": hit.get("estimateCurrency"),
                "hammer_price": hit.get("hammerPrice"),
                "sale_price": hit.get("salePrice"),
                "price_currency": hit.get("estimateCurrency"),
                "status": status,
                "location": (hit.get("locations") or [""])[0],
                "sale_start_date": start_date,
                "sale_end_date": end_date,
                "image_url": hit.get("image") or hit.get("portraitImage") or "",
                "source_url": hit.get("url") or "",
            }
            sale = {
                "source": self.name,
                "source_sale_id": sale_number,
                "title": sale_title[:300],
                "start_date": start_date,
                "end_date": end_date,
                "location": (hit.get("locations") or [""])[0],
                "url": hit.get("url") or "",
            }
            return lot, sale
        except Exception:
            return None, None
