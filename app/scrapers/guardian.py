import hashlib
import html
import re
import time

from .base import BaseScraper

BASE = "https://www.cguardian.com.hk/gdmall"
APP_ID = "THXMNCR1M5DA4A08"
SECRET = "5f2d6554b4c2c14078b59e05"
CHINESE_ROOM_TERMS = ("中國", "中国", "佛", "瓷", "玉", "書畫", "书画", "古籍", "工藝", "工艺")


class GuardianScraper(BaseScraper):
    name = "guardian"
    label = "Guardian 嘉德香港"

    def _headers(self):
        ts = str(int(time.time() * 1000))
        sign = hashlib.md5((SECRET + ts).encode()).hexdigest()
        return {
            "Content-Type": "application/json",
            "appId": APP_ID,
            "timestamp": ts,
            "sign": sign,
            "Accept": "application/json",
        }

    def run(self):
        lots = []
        sales = {}
        # 关键词搜索:佛像 + 中国文物
        for kw in ("佛像", "青花", "玉", "書畫", "書法", "瓷器"):
            resp = self._post(
                f"{BASE}/auction_syn/home_search/web/queryAuctionItem",
                json={
                    "currentPage": 1, "pageNum": 1, "pageSize": 50,
                    "ItemName": kw, "auctionID": "", "categoryID": "",
                    "minprice": "", "maxprice": "", "flag": "0", "requestFrom": "2",
                    "language": "Hk", "auctionDate": "", "auctionPrice": "",
                    "gjgd": "", "gjdd": "", "gjstatus": "", "goodsClass1": "",
                    "goodsClass2": "", "orderbyDate": "", "orderbyPrice": "",
                    "startDate": "", "endDate": "", "auctionItemID": "",
                },
                headers=self._headers(),
            )
            if resp is None:
                continue
            try:
                data = resp.json()
                items = ((data.get("data") or {}).get("auctionItemListPage") or {}).get("list") or []
            except Exception:
                continue
            for it in items:
                lot, sale = self._parse_lot(it)
                if lot:
                    lots.append(lot)
                    if sale and sale["source_sale_id"]:
                        sales[sale["source_sale_id"]] = sale
            self._sleep()
        return lots, list(sales.values())

    def _parse_lot(self, it):
        try:
            infoid = str(it.get("infoid") or "")
            if not infoid:
                return None, None
            name = html.unescape(str(it.get("name") or "")).strip()
            author = html.unescape(str(it.get("author") or "")).strip()
            title = f"{author} {name}".strip()[:500]
            price_text = str(it.get("gjzt") or "")
            m = re.search(r"([\d,]+)\s*-\s*([\d,]+)", price_text)
            low = high = None
            if m:
                low = float(m.group(1).replace(",", ""))
                high = float(m.group(2).replace(",", ""))
            final = it.get("finalPrice") or it.get("dealPrice")
            try:
                final = float(final) if final not in (None, "") else None
            except (TypeError, ValueError):
                final = None
            aid = str(it.get("auctionId") or "")
            cat = str(it.get("categoryName") or "")[:100]
            pic = str(it.get("picturepath") or "")
            img = f"https://www.cguardian.com.hk{pic}" if pic and pic.startswith("/") else pic
            lot = {
                "source": self.name,
                "source_lot_id": infoid,
                "sale_id": aid,
                "sale_title": "",
                "lot_number": str(it.get("itemCode") or "")[:50],
                "title": title,
                "description": "",
                "category": cat,
                "estimate_low": low,
                "estimate_high": high,
                "estimate_currency": "HKD",
                "hammer_price": final,
                "sale_price": final,
                "price_currency": "HKD",
                "status": "sold" if final else "upcoming",
                "location": "香港",
                "sale_start_date": None,
                "sale_end_date": None,
                "image_url": img,
                "source_url": f"https://www.cguardian.com.hk{gdmall_path(it)}" if False else "",
            }
            sale = {
                "source": self.name,
                "source_sale_id": aid,
                "title": "",
                "start_date": None,
                "end_date": None,
                "location": "香港",
                "url": "",
            }
            return lot, sale
        except Exception:
            return None, None


def gdmall_path(it):
    return ""
