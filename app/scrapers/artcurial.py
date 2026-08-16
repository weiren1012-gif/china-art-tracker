import html
import re

from .base import BaseScraper

BASE = "https://www.artcurial.com/ace"
CHINESE_TERMS = ["chinese", "china", "porcelain", "jade", "celadon", "buddha",
                 "famille", "dunhuang", "lacquer", "snuff"]


class ArtcurialScraper(BaseScraper):
    name = "artcurial"
    label = "Artcurial"

    def run(self):
        lots = []
        sales = {}
        # 1) Art d'Asie 已结束专场
        resp = self._get(
            f"{BASE}/sales/results",
            params={"filter": "specialties.specialty.ref,MTCA,ASIAN", "page": 0, "size": 50},
            headers={"X-Art-locale": "en", "Accept": "application/json"},
        )
        if resp is not None:
            try:
                for s in (resp.json() or {}).get("content") or []:
                    self._collect_sale(s, lots, sales)
            except Exception:
                pass
        # 2) 进行中专场
        resp = self._get(
            f"{BASE}/sales/calendar",
            params={"filter": "specialties.specialty.ref,MTCA,ASIAN", "size": 20},
            headers={"X-Art-locale": "en", "Accept": "application/json"},
        )
        if resp is not None:
            try:
                for s in (resp.json() or {}).get("content") or []:
                    self._collect_sale(s, lots, sales)
            except Exception:
                pass
        # 3) 关键词搜索补充
        for kw in ("chinese", "jade", "buddha", "porcelain"):
            resp = self._get(
                f"{BASE}/search",
                params={"objectType": "item", "filter": f"fts,MTC_FTS,{kw}", "page": 0, "size": 100},
                headers={"X-Art-locale": "en", "Accept": "application/json"},
            )
            if resp is not None:
                try:
                    for it in (resp.json() or {}).get("content") or []:
                        lot = self._parse_lot(it)
                        if lot:
                            lots.append(lot)
                except Exception:
                    pass
            self._sleep()
        return lots, list(sales.values())

    def _collect_sale(self, s, lots, sales):
        ref = str(s.get("saleRef") or s.get("ref") or "")
        if not ref:
            return
        name = (s.get("name") or s.get("subTitle") or "")[:300]
        sales[ref] = {
            "source": self.name,
            "source_sale_id": ref,
            "title": name,
            "start_date": s.get("effectiveDate") or None,
            "end_date": s.get("endDate") or None,
            "location": (s.get("city") or "")[:100],
            "url": f"https://www.artcurial.com/en/sales/{ref}",
        }
        if str(s.get("status")).upper() == "FINISHED":
            page = 0
            while page < 30:
                resp = self._get(
                    f"{BASE}/sales/{ref}/items",
                    params={"page": page, "size": 100},
                    headers={"X-Art-locale": "en", "Accept": "application/json"},
                )
                if resp is None:
                    break
                try:
                    data = resp.json()
                except Exception:
                    break
                items = data.get("content") or []
                for it in items:
                    lot = self._parse_lot(it)
                    if lot:
                        lots.append(lot)
                total = data.get("totalElements") or 0
                if not items or len(items) < 100 or (page + 1) * 100 >= total:
                    break
                page += 1
                self._sleep()

    def _parse_lot(self, it):
        try:
            idx = str(it.get("index") or it.get("id") or "")
            if not idx:
                return None
            ref = str(it.get("saleRef") or "")
            descs = (it.get("descriptions") or {})
            en = descs.get("ENGLISH") or {}
            title = html.unescape(re.sub(r"<[^>]+>", " ", str(en.get("titleWithHtml") or "") or "")).strip()
            if not title:
                title = html.unescape(re.sub(r"<[^>]+>", " ", str(en.get("subtitleWithHtml") or "") or "")).strip()
            desc = html.unescape(re.sub(r"<[^>]+>", " ", str(en.get("descriptionWithHtml") or "") or "")).strip()
            status = str(it.get("status") or "").upper()
            pics = it.get("pictures") or []
            img = ""
            for p in pics:
                doc = (p.get("document") or {})
                if doc.get("servingUrl"):
                    img = doc["servingUrl"]
                    break
            return {
                "source": self.name,
                "source_lot_id": f"{ref}-{idx}",
                "sale_id": ref,
                "sale_title": "",
                "lot_number": str(idx)[:50],
                "title": title[:500],
                "description": desc[:5000],
                "category": "Art d'Asie",
                "estimate_low": it.get("low"),
                "estimate_high": it.get("high"),
                "estimate_currency": it.get("currency"),
                "hammer_price": it.get("adjudicationPrice"),
                "sale_price": it.get("finalPrice"),
                "price_currency": it.get("currency"),
                "status": "sold" if status == "SOLD" else ("upcoming" if status in ("PENDING", "OPEN") else "unsold"),
                "location": (it.get("city") or "")[:100],
                "sale_start_date": it.get("adjudicationDate"),
                "sale_end_date": it.get("adjudicationDate"),
                "image_url": img,
                "source_url": f"https://www.artcurial.com/en/sales/{ref}/lots/{idx}" if ref else "",
            }
        except Exception:
            return None
