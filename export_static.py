"""将数据库导出为静态 JSON,供 GitHub Pages 使用。"""
import json
import sys

sys.path.insert(0, "/home/fn01/china-art-tracker")
from app import config, database


def export():
    database.init_db()
    with database.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, source, source_lot_id, sale_id, sale_title, lot_number, title, "
            "description, category, estimate_low, estimate_high, estimate_currency, "
            "hammer_price, sale_price, price_currency, status, location, "
            "sale_start_date, sale_end_date, image_url, source_url, tags, first_seen "
            "FROM lots ORDER BY id"
        ).fetchall()

    lots = []
    for r in rows:
        d = dict(r)
        if d.get("description"):
            d["description"] = d["description"][:300]
        # 去掉前端用不到的冗余字段,减小体积
        for k in ("source_lot_id", "sale_id", "hammer_price", "sale_end_date", "category"):
            d.pop(k, None)
        lots.append(d)

    stats = database.get_stats()
    payload = {
        "updated": database.now_iso(),
        "stats": stats,
        "lots": lots,
    }

    out = "/home/fn01/china-art-tracker/gh-pages/data/lots.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    import os

    size = os.path.getsize(out)
    print(f"已导出 {len(lots)} 条拍品 → {out} ({size/1024/1024:.1f} MB)")


if __name__ == "__main__":
    export()
