import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config, database, scheduler, tunnel
from .scrapers import SCRAPERS, get_scraper

_fetch_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    scheduler.start_scheduler()
    yield
    scheduler.stop_scheduler()


app = FastAPI(title="中国文物拍卖追踪", lifespan=lifespan)


@app.get("/api/lots")
def api_lots(
    source: str = None,
    status: str = None,
    search: str = None,
    sort: str = "recent",
    tag: str = None,
    page: int = 1,
    page_size: int = Query(24, le=200),
):
    try:
        total, rows = database.query_lots(
            source=source, status=status, search=search, sort=sort, page=page, page_size=page_size, tag=tag
        )
        return {"total": total, "page": page, "page_size": page_size, "items": rows}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/lots/new")
def api_new_lots(limit: int = Query(50, le=200), hours: int = None):
    return {"items": database.get_recent_new(limit=limit, hours=hours)}


@app.get("/api/lots/{lot_id}")
def api_lot(lot_id: int):
    lot = database.get_lot(lot_id)
    if not lot:
        return JSONResponse({"error": "not found"}, status_code=404)
    return lot


@app.get("/api/stats")
def api_stats():
    return database.get_stats()


@app.get("/api/sales")
def api_sales(source: str = None, limit: int = 50):
    return {"items": database.query_sales(source=source, limit=limit)}


@app.get("/api/sources")
def api_sources():
    return [
        {"name": s.name, "label": s.label}
        for s in SCRAPERS
    ]


@app.post("/api/fetch")
def api_fetch(source: str = None):
    if not _fetch_lock.acquire(blocking=False):
        return JSONResponse({"error": "已有抓取任务在进行中"}, status_code=409)
    try:
        if source:
            scraper = get_scraper(source)
            if not scraper:
                return JSONResponse({"error": "unknown source"}, status_code=404)
            inserted, total = scheduler.fetch_source(scraper)
            return {"ok": True, "source": source, "new": inserted, "total": total}
        threading.Thread(target=scheduler.run_all_sources, daemon=True).start()
        return {"ok": True, "message": "抓取任务已在后台启动"}
    finally:
        _fetch_lock.release()


@app.get("/api/tunnel")
def api_tunnel():
    url = tunnel.get_tunnel_url()
    if not url:
        return JSONResponse({"error": "未找到隧道地址,请运行 start.sh"}, status_code=404)
    return {"url": url}


@app.get("/api/qrcode.png")
def api_qrcode():
    url = tunnel.get_tunnel_url()
    if not url:
        return JSONResponse({"error": "未找到隧道地址"}, status_code=404)
    return Response(
        content=tunnel.get_qrcode_png(url),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/fetch/logs")
def api_logs(limit: int = 30):
    return {"items": database.get_fetch_logs(limit=limit)}


app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
