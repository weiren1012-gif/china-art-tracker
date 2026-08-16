import html
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from .base import BaseScraper
from .. import config

BASE = "https://www.woolleyandwallis.co.uk"
SEARCH_URL = f"{BASE}/umbraco/ua2/CoreApi/SearchLots"
LOTS_URL = f"{BASE}/api/lots/search"


class WoolleyScraper(BaseScraper):
    name = "woolley"
    label = "Woolley & Wallis"

    def __init__(self):
        super().__init__()
        self.known_ids = set()

    def run(self):
        lots = []
        sales = {}
        seen_sales = set()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=config.RESULTS_LOOKBACK_DAYS)).isoformat()
        budget = 25
        for dept_name, dept_id in config.WOOLLEY_DEPARTMENTS.items():
            if budget <= 0:
                break
            for q in ("chinese", "asian"):
                data = self._search_lots(q, dept_id)
                if not data:
                    continue
                for is_past, group in (
                    (False, data.get("futureSales") or []),
                    (True, data.get("pastSales") or []),
                ):
                    past_processed = 0
                    for sale in group:
                        sid = str(sale.get("id") or "")
                        if not sid or sid in seen_sales:
                            continue
                        start = sale.get("startDate") or sale.get("date") or ""
                        # 窗口内的过去场次 + 最近的 2 场,保证始终有数据
                        if is_past:
                            if start and start < cutoff and past_processed >= 2:
                                continue
                            past_processed += 1
                        seen_sales.add(sid)
                        self._collect_sale(sale, dept_name, lots, sales)
                        budget -= 1
                        if budget <= 0:
                            break
                    if budget <= 0:
                        break
                if budget <= 0:
                    break
                self._sleep()
        return lots, list(sales.values())

    def _search_lots(self, q, dept_id):
        resp = self._post(
            SEARCH_URL,
            json={"q": q, "s": 1, "t": "a", "d": dept_id},
            headers={"Content-Type": "application/json"},
        )
        if resp is None:
            return None
        try:
            return (resp.json() or {}).get("data") or {}
        except Exception:
            return None

    def _collect_sale(self, sale, dept_name, lots, sales):
        sale_id = str(sale.get("id") or "")
        if not sale_id:
            return
        title = (sale.get("title") or "")[:300]
        sales[sale_id] = {
            "source": self.name,
            "source_sale_id": sale_id,
            "title": title,
            "start_date": sale.get("startDate") or sale.get("date"),
            "end_date": sale.get("endDate"),
            "location": (sale.get("saleLocation") or ""),
            "url": urljoin(BASE, sale.get("url") or ""),
        }
        # 使用分页接口拉取该场全部拍品
        page_index = 0
        while page_index < 100:
            resp = self._get(
                LOTS_URL,
                params={"pageIndex": page_index, "saleId": sale_id, "pageSize": 160},
            )
            if resp is None:
                break
            try:
                data = resp.json()
            except Exception:
                break
            results = data.get("Results") or []
            for r in results:
                lot = self._parse_lot(r, sale_id, title, dept_name)
                if lot:
                    lots.append(lot)
            total = data.get("TotalRecords") or 0
            if not results or (page_index + 1) * 160 >= total:
                break
            page_index += 1
            self._sleep()

    def _parse_lot(self, r, sale_id, sale_title, dept_name):
        try:
            lot_id = str(r.get("Id") or "")
            if not lot_id:
                return None
            title = html.unescape(re.sub(r"<[^>]+>", " ", str(r.get("Title") or ""))).strip()
            desc = html.unescape(re.sub(r"<[^>]+>", " ", str(r.get("FullDescription") or ""))).strip()
            low = r.get("LowerEstimate")
            high = r.get("UpperEstimate")
            hammer = r.get("HammerPrice")
            if low is None and r.get("LowerEstimateFormatted"):
                low, high, _ = self._parse_formatted(
                    r.get("LowerEstimateFormatted"), r.get("UpperEstimateFormatted")
                )
            status = "upcoming"
            if r.get("BiddingAllowed") in ("False", False):
                if hammer not in (None, "", 0):
                    status = "sold"
                else:
                    status = "unsold"
            view_url = r.get("ViewUrl") or ""
            cat_text = str(r.get("Categories") or "")
            return {
                "source": self.name,
                "source_lot_id": lot_id,
                "sale_id": sale_id,
                "sale_title": sale_title[:300],
                "lot_number": str(r.get("LotNumber") or "")[:50],
                "title": title[:500] or (desc[:500] if desc else "(untitled)"),
                "description": desc[:5000],
                "category": dept_name,
                "estimate_low": low,
                "estimate_high": high,
                "estimate_currency": "GBP",
                "hammer_price": hammer,
                "sale_price": hammer,
                "price_currency": "GBP",
                "status": status,
                "location": "",
                "sale_start_date": None,
                "sale_end_date": None,
                "image_url": r.get("MainImageUrl") or r.get("MainImageThumbUrl") or "",
                "source_url": urljoin(BASE, view_url),
            }
        except Exception:
            return None

    @staticmethod
    def _parse_formatted(low_s, high_s):
        nums = []
        for s in (low_s, high_s):
            m = re.search(r"[\d,]+", str(s or ""))
            nums.append(float(m.group(0).replace(",", "")) if m else None)
        return nums[0], nums[1], "GBP"
