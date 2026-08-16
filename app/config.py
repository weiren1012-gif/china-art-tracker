import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "auctions.db")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

CHINESE_KEYWORDS = [
    "Chinese ceramics",
    "Chinese works of art",
    "Chinese paintings",
    "Chinese porcelain",
    "Chinese art",
]

SOTHEBYS_CHINESE_DEPARTMENTS = [
    "Chinese Works of Art",
    "Chinese Paintings – Classical",
    "Chinese Paintings – Modern",
    "Chinese Export Porcelain",
]

BONHAMS_CHINESE_DEPARTMENTS = ["ORI-CHI", "PIC-CHI"]

DREWEATTS_CATEGORY_CODE = "CWA"
DREWEATTS_KEYWORDS = ["chinese", "china", "asian"]

WOOLLEY_DEPARTMENTS = {"Asian Art": "1281", "Chinese Paintings & Calligraphy": "1620"}

# 定时轮询间隔(小时)
POLL_INTERVAL_HOURS = int(os.environ.get("POLL_INTERVAL_HOURS", "6"))

# 结果追溯天数(每次轮询拉取最近 N 天成交结果)
RESULTS_LOOKBACK_DAYS = int(os.environ.get("RESULTS_LOOKBACK_DAYS", "30"))

# 每个来源单次轮询的请求间隔(秒)
REQUEST_DELAY = float(os.environ.get("REQUEST_DELAY", "1.0"))

# 每个来源单次轮询最多抓取多少页
MAX_PAGES = int(os.environ.get("MAX_PAGES", "40"))

os.makedirs(DATA_DIR, exist_ok=True)
