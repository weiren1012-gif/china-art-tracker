import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper
from .. import config

BASE = "https://auctions.dreweatts.com"
CAT = config.DREWEATTS_CATEGORY_CODE


def _clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def _parse_estimate(text):
    """解析 '3,000 - 5,000 GBP' 或 '£3,000 - £5,000' 形式的估价。"""
    m = re.search(r"([\d,]+)\s*-\s*([\d,]+)", (text or "").replace("£", "").replace("€", "").replace("$", ""))
    if not m:
        return None, None, None
    try:
        low, high = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
    except ValueError:
        return None, None, None
    cur = None
    for c in ("GBP", "EUR", "USD", "£", "€", "$"):
        if c in text:
            cur = "GBP" if c == "£" else ("EUR" if c == "€" else ("USD" if c == "$" else c))
            break
    return low, high, cur


def _parse_date(s):
    for fmt in ("%d %b %Y %H:%M", "%d %b %Y", "%d %B %Y %H:%M", "%d %B %Y"):
        try:
            return datetime.strptime(_clean(s).strip(), fmt).isoformat()
        except ValueError:
            continue
    return None


class DreweattsScraper(BaseScraper):
    name = "dreweatts"
    label = "Dreweatts"

    def __init__(self):
        super().__init__()
        self.known_ids = set()
        self._detail_budget = 100

    def run(self):
        lots = []
        sales = {}
        # 即将举行的拍卖
        for page in range(1, 3):
            items = self._fetch_auction_items(f"{BASE}/auctions?page={page}&pageSize=60")
            if not items:
                break
            for item in items[:15]:
                self._collect_sale_lots(item, lots, sales, upcoming=True)
            self._sleep()
        # 最近已结束的拍卖(带 CWA 分类)
        for page in range(1, 3):
            items = self._fetch_auction_items(
                f"{BASE}/past-auctions?page={page}&pageSize=25&categoryCodes={CAT}"
            )
            if not items:
                break
            for item in items[:8]:
                self._collect_sale_lots(item, lots, sales, upcoming=False)
            self._sleep()
        return lots, list(sales.values())

    def _fetch_auction_items(self, url):
        resp = self._get(url)
        if resp is None:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        items = []
        for el in soup.select("div.auction-list-item"):
            a_ref = el.get("data-auction-ref")
            if not a_ref:
                continue
            link = el.select_one("a.color-inherit[href]")
            if link is None:
                continue
            href = link.get("href") or ""
            m = re.match(r"^/(auctions|past-auctions)/(\d+/)?([a-z0-9-]+)$", href)
            if not m:
                continue
            kind, num, a_ref = m.group(1), m.group(2), m.group(3)
            a_id = (num or "").rstrip("/")
            title = _clean(link.get_text())
            # 只处理含 CWA(中国工艺品)分类的场次,跳过无关拍卖
            cwa_link = el.select_one(f"a[href*='categoryCode={CAT}']")
            if cwa_link is None:
                continue
            cwa_count = 0
            m2 = re.search(r"detail[\"'>]*>\s*(\d+)", str(cwa_link))
            if m2:
                cwa_count = int(m2.group(1))
            start = end = None
            for span in el.select("span.sale-date"):
                txt = _clean(span.get_text())
                if "Start" in txt or "started" in txt.lower():
                    start = _parse_date(txt)
                elif "End" in txt or "closing" in txt.lower():
                    end = _parse_date(txt)
            if not start:
                dates = [_parse_date(_clean(s.get_text())) for s in el.select("span.sale-date")]
                dates = [d for d in dates if d]
                start = dates[0] if dates else None
                end = dates[-1] if len(dates) > 1 else None
            items.append(
                {
                    "auction_id": a_id,
                    "ref": a_ref,
                    "title": title,
                    "start_date": start,
                    "end_date": end,
                    "href": href,
                    "upcoming": kind == "auctions",
                    "cwa_count": cwa_count,
                }
            )
        # 按 CWA 拍品数量降序,优先处理中国文物多的场次
        items.sort(key=lambda x: x["cwa_count"], reverse=True)
        return items

    def _collect_sale_lots(self, item, lots, sales, upcoming):
        sale_id = f"{item['auction_id']}/{item['ref']}"
        sales[sale_id] = {
            "source": self.name,
            "source_sale_id": sale_id,
            "title": item["title"][:300],
            "start_date": item["start_date"],
            "end_date": item["end_date"],
            "location": "",
            "url": urljoin(BASE, item["href"]),
        }
        # 逐页抓取该场拍卖中 CWA 分类的拍品
        for page in range(1, min(4, config.MAX_PAGES) + 1):
            url = urljoin(BASE, f"{item['href']}?page={page}&pageSize=60&categoryCode={CAT}")
            resp = self._get(url)
            if resp is None:
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            page_lots = self._parse_lot_cards(soup, sale_id, item, upcoming)
            if not page_lots:
                break
            # 只对新拍品补充详情页描述(限制预算,避免请求过多)
            for lot in page_lots:
                if (
                    self._detail_budget > 0
                    and lot["source_lot_id"] not in self.known_ids
                    and lot["description"] == ""
                ):
                    self._enrich_detail(lot)
            lots.extend(page_lots)
            if len(page_lots) < 60:
                break
            self._sleep()

    def _enrich_detail(self, lot):
        resp = self._get(lot["source_url"])
        if resp is None:
            return
        soup = BeautifulSoup(resp.text, "html.parser")
        desc_el = soup.select_one("div.ui.tab.active[data-tab='description']") or soup.select_one(
            "div[data-tab='description']"
        )
        if desc_el:
            txt = _clean(desc_el.get_text())
            txt = txt.replace("Condition Report Disclaimer", "").strip()
            if txt:
                lot["description"] = txt[:5000]
                self._detail_budget -= 1
        est_el = soup.select_one("span.estimate-price-value")
        if est_el and lot["estimate_low"] is None:
            low, high, cur = _parse_estimate(_clean(est_el.get_text()))
            lot["estimate_low"] = low
            lot["estimate_high"] = high
            lot["estimate_currency"] = cur
        self._sleep()

    def _parse_lot_cards(self, soup, sale_id, item, upcoming):
        out = []
        for card in soup.select("a.lot-grid-header[href*='lot-details']"):
            href = card.get("href") or ""
            if href.endswith("/additional-fees"):
                continue
            m = re.search(r"lot-details/([0-9a-f-]+)", href)
            if not m:
                continue
            lot_uuid = m.group(1)
            card_el = card.find_parent("div", class_=re.compile(r"card|item"))
            if card_el is None:
                card_el = card.find_parent("div")
            container = card.find_parent("div", class_=re.compile("lot")) or card_el
            lot_no = ""
            ln = card.find_previous("div", class_="lot-number") or card_el.select_one(".lot-number")
            if ln:
                lot_no = _clean(ln.get_text())
            # 图片
            img_url = ""
            img = card_el.find("img") if card_el else None
            if img and img.get("src"):
                img_url = img["src"]
            # 估价与出价
            low = high = cur = None
            est_el = card_el.select_one(".estimate-price-value") if card_el else None
            if est_el:
                low, high, cur = _parse_estimate(_clean(est_el.get_text()))
            bid = bid_cur = None
            bid_el = card_el.select_one(".current-bid-value") if card_el else None
            bid_cur_el = card_el.select_one(".current-bid-currency") if card_el else None
            if bid_el is not None:
                try:
                    bid = float(bid_el.get("data-current-bid") or bid_el.get_text().replace(",", ""))
                except ValueError:
                    bid = None
            if bid_cur_el is not None:
                bid_cur = _clean(bid_cur_el.get_text())
            status = "upcoming" if upcoming else ("sold" if bid is not None and bid > 0 else "unsold")
            title = _clean(card.get("title") or card.get_text())
            if title.lower().find("chinese") < 0 and not (upcoming):
                # 已结束场次仅在分类页内,已按 CWA 过滤,无需再次过滤
                pass
            out.append(
                {
                    "source": self.name,
                    "source_lot_id": lot_uuid,
                    "sale_id": sale_id,
                    "sale_title": item["title"][:300],
                    "lot_number": lot_no[:50],
                    "title": title[:500],
                    "description": "",
                    "category": "Chinese Works of Art",
                    "estimate_low": low,
                    "estimate_high": high,
                    "estimate_currency": cur,
                    "hammer_price": bid if (upcoming is False and bid and bid > 0) else None,
                    "sale_price": bid if (upcoming is False and bid and bid > 0) else None,
                    "price_currency": bid_cur,
                    "status": status,
                    "location": "",
                    "sale_start_date": item["start_date"],
                    "sale_end_date": item["end_date"],
                    "image_url": img_url,
                    "source_url": urljoin(BASE, href),
                }
            )
        return out
