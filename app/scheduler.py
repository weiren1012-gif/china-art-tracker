import threading
import traceback

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from . import config, database
from .scrapers import SCRAPERS
from .scrapers.tagger import tag_lots

_lock = threading.Lock()
_scheduler = None
_running = {}


def fetch_source(scraper, known_ids=None):
    """抓取单个来源,写入数据库。返回 (new_lots, total_lots)。"""
    try:
        if known_ids is not None:
            scraper.known_ids = known_ids
        lots, sales = scraper.run()
        tag_lots(lots)
        inserted = database.upsert_lots(lots)
        database.upsert_sales(sales)
        database.log_fetch(scraper.name, len(lots), "ok")
        return inserted, len(lots)
    except Exception as e:
        database.log_fetch(scraper.name, 0, "error", f"{e}\n{traceback.format_exc()[:800]}")
        return 0, 0


def run_all_sources():
    if not _lock.acquire(blocking=False):
        return
    try:
        with database.get_conn() as conn:
            known = {
                (r["source"], r["source_lot_id"])
                for r in conn.execute("SELECT source, source_lot_id FROM lots")
            }
        for scraper in SCRAPERS:
            if _running.get(scraper.name):
                continue
            _running[scraper.name] = True
            try:
                insert, total = fetch_source(scraper, known_ids=known)
                print(f"[fetch] {scraper.name}: {insert} new / {total} total")
            except Exception as e:
                print(f"[fetch] {scraper.name} failed: {e}")
            finally:
                _running[scraper.name] = False
    finally:
        _lock.release()


def start_scheduler():
    global _scheduler
    if _scheduler:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        run_all_sources,
        IntervalTrigger(hours=config.POLL_INTERVAL_HOURS),
        id="poll_all",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    print(f"[scheduler] started, polling every {config.POLL_INTERVAL_HOURS}h")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
