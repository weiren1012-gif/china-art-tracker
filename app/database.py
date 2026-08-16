import sqlite3
import threading
from datetime import datetime, timezone
from . import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_lot_id TEXT NOT NULL,
    sale_id TEXT,
    sale_title TEXT,
    lot_number TEXT,
    title TEXT,
    description TEXT,
    category TEXT,
    estimate_low REAL,
    estimate_high REAL,
    estimate_currency TEXT,
    hammer_price REAL,
    sale_price REAL,
    price_currency TEXT,
    status TEXT,
    location TEXT,
    sale_start_date TEXT,
    sale_end_date TEXT,
    image_url TEXT,
    source_url TEXT,
    first_seen TEXT,
    last_seen TEXT,
    tags TEXT DEFAULT '',
    UNIQUE(source, source_lot_id)
);

CREATE INDEX IF NOT EXISTS idx_lots_source ON lots(source);
CREATE INDEX IF NOT EXISTS idx_lots_status ON lots(status);
CREATE INDEX IF NOT EXISTS idx_lots_sale_date ON lots(sale_start_date);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_sale_id TEXT NOT NULL,
    title TEXT,
    start_date TEXT,
    end_date TEXT,
    location TEXT,
    url TEXT,
    first_seen TEXT,
    last_seen TEXT,
    UNIQUE(source, source_sale_id)
);

CREATE TABLE IF NOT EXISTS fetch_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    started_at TEXT,
    finished_at TEXT,
    lots_found INTEGER,
    status TEXT,
    error TEXT
);
"""


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with _lock, get_conn() as conn:
        conn.executescript(SCHEMA)
        # 兼容旧库:新增 tags 列
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(lots)")]
        if "tags" not in cols:
            conn.execute("ALTER TABLE lots ADD COLUMN tags TEXT DEFAULT ''")


def upsert_lots(lots):
    """lots: list of dicts with the same keys as the lots table."""
    if not lots:
        return 0
    ts = now_iso()
    with _lock, get_conn() as conn:
        inserted = 0
        for lot in lots:
            cur = conn.execute(
                "SELECT id FROM lots WHERE source=? AND source_lot_id=?",
                (lot["source"], lot["source_lot_id"]),
            )
            row = cur.fetchone()
            data = dict(lot)
            data["last_seen"] = ts
            if row is None:
                data["first_seen"] = ts
                cols = ", ".join(data.keys())
                marks = ", ".join("?" for _ in data)
                conn.execute(
                    f"INSERT INTO lots ({cols}) VALUES ({marks})",
                    list(data.values()),
                )
                inserted += 1
            else:
                sets = ", ".join(f"{k}=?" for k in data)
                conn.execute(
                    f"UPDATE lots SET {sets} WHERE id=?",
                    list(data.values()) + [row["id"]],
                )
    return inserted


def upsert_sales(sales):
    if not sales:
        return 0
    ts = now_iso()
    with _lock, get_conn() as conn:
        for sale in sales:
            cur = conn.execute(
                "SELECT id FROM sales WHERE source=? AND source_sale_id=?",
                (sale["source"], sale["source_sale_id"]),
            )
            row = cur.fetchone()
            data = dict(sale)
            data["last_seen"] = ts
            if row is None:
                data["first_seen"] = ts
                cols = ", ".join(data.keys())
                marks = ", ".join("?" for _ in data)
                conn.execute(
                    f"INSERT INTO sales ({cols}) VALUES ({marks})",
                    list(data.values()),
                )
            else:
                sets = ", ".join(f"{k}=?" for k in data)
                conn.execute(
                    f"UPDATE sales SET {sets} WHERE id=?", list(data.values()) + [row["id"]]
                )


def log_fetch(source, lots_found, status="ok", error=None):
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT INTO fetch_logs (source, started_at, finished_at, lots_found, status, error) "
            "VALUES (?,?,?,?,?,?)",
            (source, now_iso(), now_iso(), lots_found, status, error),
        )


def _apply_filters(q, source, status, search, tag=None):
    clauses = []
    args = []
    if source:
        clauses.append("source=?")
        args.append(source)
    if status:
        clauses.append("status=?")
        args.append(status)
    if search:
        clauses.append("(title LIKE ? OR description LIKE ? OR sale_title LIKE ?)")
        like = f"%{search}%"
        args += [like, like, like]
    if tag:
        clauses.append("tags LIKE ?")
        args.append(f"%{tag}%")
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    return q, args


def query_lots(source=None, status=None, search=None, sort="recent", page=1, page_size=24, tag=None):
    q = "SELECT * FROM lots"
    q, args = _apply_filters(q, source, status, search, tag)
    if sort == "price_high":
        q += " ORDER BY (CASE WHEN sale_price IS NOT NULL THEN sale_price ELSE (estimate_high+estimate_low)/2.0 END) DESC"
    elif sort == "price_low":
        q += " ORDER BY (CASE WHEN sale_price IS NOT NULL THEN sale_price ELSE (estimate_high+estimate_low)/2.0 END) ASC"
    elif sort == "newest":
        q += " ORDER BY first_seen DESC, id DESC"
    else:
        q += " ORDER BY COALESCE(sale_end_date, sale_start_date, last_seen) DESC, id DESC"
    with _lock, get_conn() as conn:
        cq = "SELECT COUNT(*) FROM lots"
        cq, cargs = _apply_filters(cq, source, status, search, tag)
        total = conn.execute(cq, cargs).fetchone()[0]
        rows = conn.execute(q + " LIMIT ? OFFSET ?", args + [page_size, (page - 1) * page_size]).fetchall()
        return total, [dict(r) for r in rows]


def get_recent_new(limit=50, hours=None):
    """最近新增的拍品(first_seen 排序)。"""
    q = "SELECT * FROM lots"
    args = []
    if hours:
        q += f" WHERE first_seen >= datetime('now', ?)"
        args.append(f"-{hours} hours")
    q += " ORDER BY first_seen DESC, id DESC LIMIT ?"
    args.append(limit)
    with _lock, get_conn() as conn:
        rows = conn.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def get_lot(lot_id):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT * FROM lots WHERE id=?", (lot_id,)).fetchone()
        return dict(row) if row else None


def get_stats():
    with _lock, get_conn() as conn:
        by_source = conn.execute(
            "SELECT source, COUNT(*) n, SUM(CASE WHEN status='sold' THEN 1 ELSE 0 END) sold, "
            "SUM(CASE WHEN status='upcoming' THEN 1 ELSE 0 END) upcoming "
            "FROM lots GROUP BY source"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM lots").fetchone()[0]
        grotto = conn.execute("SELECT COUNT(*) FROM lots WHERE tags LIKE '%grotto%'").fetchone()[0]
        new_today = conn.execute(
            "SELECT COUNT(*) FROM lots WHERE first_seen >= datetime('now','-1 day')"
        ).fetchone()[0]
        last_run = conn.execute(
            "SELECT source, MAX(finished_at) last FROM fetch_logs GROUP BY source"
        ).fetchall()
    return {
        "total": total,
        "recent": new_today,
        "grotto": grotto,
        "by_source": {r["source"]: {"count": r["n"], "sold": r["sold"] or 0, "upcoming": r["upcoming"] or 0} for r in by_source},
        "last_runs": {r["source"]: r["last"] for r in last_run},
    }


def query_sales(source=None, limit=50):
    q = "SELECT * FROM sales"
    args = []
    if source:
        q += " WHERE source=?"
        args.append(source)
    q += " ORDER BY COALESCE(start_date,last_seen) DESC LIMIT ?"
    args.append(limit)
    with _lock, get_conn() as conn:
        rows = conn.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def get_fetch_logs(limit=30):
    with _lock, get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM fetch_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
