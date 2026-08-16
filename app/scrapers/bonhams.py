import html
import re
import time
from datetime import datetime, timedelta, timezone

from .base import BaseScraper
from .. import config

LOTS_API = "https://api01.bonhams.com/search-proxy/collections/lots/documents/search"
AUCTIONS_API = "https://api01.bonhams.com/search-proxy/collections/auctions-search/documents/search"
KEY = "7YZqOyG0twgst4ACc2VuCyZxpGAYzM0weFTLCC20FQY"
DEPARTMENTS = [
    "Chinese Ceramics & Works of Art",
    "Chinese Paintings",
    "Asian Art",
    "Japanese, Korean & Southeast Asian Art",
    "Chinese & Asian Furniture",
]


class BonhamsScraper(BaseScraper):
    name = "bonhams"
    label = "Bonhams"

    def run(self):
        lots = []
        auctions = self._fetch_auctions()
        auction_map = {a["id"]: a for a in auctions}
        dept = "department.code:=[`{}`]".format("`,`".join(config.BONHAMS_CHINESE_DEPARTMENTS))

        lots += self._fetch_lots(f"{dept} && flags.isToBeSold:=true", "hammerTime.timestamp:desc")
        cutoff = int((datetime.now(timezone.utc) - timedelta(days=config.RESULTS_LOOKBACK_DAYS)).timestamp())
        lots += self._fetch_lots(
            f"{dept} && status:=sold && hammerTime.timestamp:>={cutoff}",
            "hammerTime.timestamp:desc",
        )

        out = []
        sales = {}
        for lot in lots:
            info = auction_map.get(lot["auctionId"]) or {}
            lot["sale_title"] = (info.get("title") or "")[:300]
            lot["sale_start_date"] = info.get("start")
            lot["sale_end_date"] = info.get("end")
            if not lot.get("location"):
                lot["location"] = info.get("country") or ""
            sid = lot["auctionId"]
            sales[sid] = {
                "source": self.name,
                "source_sale_id": sid,
                "title": (info.get("title") or "")[:300],
                "start_date": info.get("start"),
                "end_date": info.get("end"),
                "location": info.get("country") or "",
                "url": f"https://www.bonhams.com/auctions/{sid}/" if sid else "",
            }
            lot.pop("auctionId", None)
            out.append(lot)
        return out, list(sales.values())

    def _fetch_auctions(self):
        """抓取中国文物相关部门的拍卖会信息(id → 标题/日期/国家)。"""
        dept_names = "departments.name:=[`{}`]".format("`,`".join(DEPARTMENTS))
        out = {}
        for status in ("NEW", "READY", "FINISHED"):
            page = 1
            while page <= 10:
                resp = self._get(
                    AUCTIONS_API,
                    params={
                        "q": "",
                        "query_by": "auctionTitle",
                        "page": page,
                        "per_page": 250,
                        "filter_by": f"auctionStatus:={status} && {dept_names}",
                        "sort_by": "dates.end.timestamp:desc",
                    },
                    headers={"X-TYPESENSE-API-KEY": KEY},
                )
                if resp is None:
                    break
                try:
                    data = resp.json()
                except Exception:
                    break
                hits = data.get("hits") or []
                for hit in hits:
                    doc = hit.get("document") or {}
                    dates = doc.get("dates") or {}
                    start = (dates.get("start") or {}).get("datetime")
                    end = (dates.get("end") or {}).get("datetime")
                    out[doc.get("id")] = {
                        "id": str(doc.get("id") or ""),
                        "title": doc.get("auctionTitle") or doc.get("auctionHeading") or "",
                        "start": start,
                        "end": end,
                        "country": (doc.get("country") or {}).get("name") or "",
                        "status": doc.get("auctionStatus"),
                    }
                found = data.get("found") or 0
                if not hits or (page * 250) >= found:
                    break
                page += 1
                self._sleep()
        return list(out.values())

    def _fetch_lots(self, filter_by, sort_by, per_page=250):
        out = []
        page = 1
        while page <= config.MAX_PAGES:
            resp = self._get(
                LOTS_API,
                params={
                    "q": "",
                    "query_by": "title",
                    "page": page,
                    "per_page": per_page,
                    "filter_by": filter_by,
                    "sort_by": sort_by,
                    "exclude_fields": "footnotes,embedding",
                },
                headers={"X-TYPESENSE-API-KEY": KEY},
            )
            if resp is None:
                break
            try:
                data = resp.json()
            except Exception:
                break
            hits = data.get("hits") or []
            for hit in hits:
                lot = self._parse_lot(hit.get("document") or {})
                if lot:
                    out.append(lot)
            found = data.get("found") or 0
            if not hits or (page * per_page) >= found or len(out) > 2500:
                break
            page += 1
            self._sleep()
        return out

    def _parse_lot(self, doc):
        try:
            auction_id = str(doc.get("auctionId") or "")
            lot_id = str(doc.get("lotUniqueId") or doc.get("id") or "")
            if not lot_id:
                return None
            lot_no_raw = (doc.get("lotNo") or {})
            lot_no = lot_no_raw.get("full")
            if lot_no in (None, "", "0"):
                lot_no = str(lot_no_raw.get("number") or "")
            price = doc.get("price") or {}
            img = doc.get("image") or {}
            hammer_time = doc.get("hammerTime") or {}
            date_str = hammer_time.get("datetime")
            status_raw = (doc.get("status") or "").lower()
            if status_raw == "sold":
                status = "sold"
            elif status_raw == "unsold":
                status = "unsold"
            elif status_raw == "withdrawn":
                status = "withdrawn"
            else:
                status = "upcoming"
            title = html.unescape(re.sub(r"<[^>]+>", " ", str(doc.get("title") or ""))).strip()
            desc = html.unescape(
                re.sub(r"<[^>]+>", " ", str(doc.get("styledDescription") or doc.get("catalogDesc") or ""))
            ).strip()
            url = doc.get("url") or ""
            if not url and doc.get("slug"):
                url = f"https://www.bonhams.com/{doc['slug']}"
            return {
                "source": self.name,
                "source_lot_id": f"{auction_id}-{lot_id}",
                "sale_id": auction_id,
                "auctionId": auction_id,
                "sale_title": "",
                "lot_number": lot_no[:50],
                "title": title[:500],
                "description": desc[:5000],
                "category": (doc.get("department") or {}).get("name") or "",
                "estimate_low": price.get("estimateLow"),
                "estimate_high": price.get("estimateHigh"),
                "estimate_currency": html.unescape(str(price.get("currencySymbol") or "")),
                "hammer_price": price.get("hammerPrice") or None,
                "sale_price": price.get("hammerPremium") or None,
                "price_currency": (doc.get("currency") or {}).get("iso_code")
                or html.unescape(str(price.get("currencySymbol") or "")),
                "status": status,
                "location": (doc.get("country") or {}).get("name") or "",
                "sale_start_date": date_str,
                "sale_end_date": date_str,
                "image_url": img.get("url") or "",
                "source_url": url,
            }
        except Exception:
            return None
