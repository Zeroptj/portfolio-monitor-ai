"""
news_feed.py — ดึงข่าวจาก NewsAPI พร้อม daily DB cache

Logic:
  - ถ้าวันนี้มีข่าวใน DB แล้ว → return จาก DB (ไม่ hit API)
  - ถ้ายังไม่มี → fetch จาก NewsAPI แล้ว save ลง DB
"""

import os
import sys
import yaml
import requests
from datetime import datetime
from dotenv import load_dotenv

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR   = os.path.dirname(ENGINE_DIR)
sys.path.insert(0, ENGINE_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

with open(os.path.join(ENGINE_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

NEWS_CFG = config["news"]
API_KEY  = os.getenv("NEWS_API_KEY", "")

QUERY_MAP: dict[str, str] = {
    "BTC":  "Bitcoin crypto",
    "ETH":  "Ethereum crypto",
    "AAPL": "Apple AAPL stock",
    "NVDA": "NVIDIA NVDA stock",
    "SPY":  "S&P 500 ETF SPY",
    "QQQ":  "Nasdaq QQQ ETF",
    "VT":   "Vanguard VT ETF world stock",
    "THD":  "Thailand stock market ETF",
    "GC=F": "Gold price XAU",
    "CL=F": "Crude oil WTI price",
}


# ─── DB helpers ──────────────────────────────────────────────────────────────

def _load_from_db(date: str, symbol: str) -> list[dict] | None:
    """คืน cache ถ้ามีวันนี้แล้ว, None ถ้ายังไม่มี"""
    from portfolio.holdings import SessionLocal, NewsCache
    db = SessionLocal()
    try:
        rows = (
            db.query(NewsCache)
            .filter(NewsCache.date == date, NewsCache.symbol == symbol)
            .order_by(NewsCache.id)
            .all()
        )
        if not rows:
            return None
        return [
            {
                "title":        r.title,
                "description":  r.description or "",
                "url":          r.url,
                "source":       r.source,
                "published_at": r.published_at,
                "symbol":       r.symbol or None,
            }
            for r in rows
        ]
    finally:
        db.close()


def _save_to_db(date: str, symbol: str, articles: list[dict]):
    """บันทึก articles ลง DB (ถ้ายังไม่มีวันนั้น)"""
    if not articles:
        return
    from portfolio.holdings import SessionLocal, NewsCache
    db = SessionLocal()
    try:
        for a in articles:
            db.add(NewsCache(
                date        = date,
                symbol      = symbol,
                title       = a.get("title", ""),
                description = a.get("description", ""),
                url         = a.get("url", ""),
                source      = a.get("source", ""),
                published_at= a.get("published_at", ""),
            ))
        db.commit()
        print(f"[news_feed] Cached {len(articles)} articles for {symbol or 'general'} ({date})")
    except Exception as e:
        db.rollback()
        print(f"[news_feed] DB save error: {e}")
    finally:
        db.close()


# ─── Fetch from API ───────────────────────────────────────────────────────────

def _fetch_from_api(symbol: str | None) -> list[dict]:
    """เรียก NewsAPI จริงๆ"""
    if not API_KEY:
        print("[news_feed] NEWS_API_KEY not set")
        return []

    max_articles = NEWS_CFG.get("max_articles", 10)

    try:
        if symbol and symbol in QUERY_MAP:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q":        QUERY_MAP[symbol],
                    "language": "en",
                    "sortBy":   "publishedAt",
                    "pageSize": max_articles,
                    "apiKey":   API_KEY,
                },
                timeout=10,
            )
        else:
            resp = requests.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    "category": "business",
                    "language": "en",
                    "pageSize": max_articles,
                    "apiKey":   API_KEY,
                },
                timeout=10,
            )

        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "ok":
            print(f"[news_feed] API error: {data.get('message', 'unknown')}")
            return []

        return [
            {
                "title":        a.get("title", ""),
                "description":  a.get("description", "") or "",
                "url":          a.get("url", ""),
                "source":       a.get("source", {}).get("name", ""),
                "published_at": a.get("publishedAt", ""),
                "symbol":       symbol,
            }
            for a in data.get("articles", [])
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]

    except Exception as e:
        print(f"[news_feed] fetch error: {e}")
        return []


# ─── Public API ───────────────────────────────────────────────────────────────

def get_news(symbol: str | None = None) -> list[dict]:
    """
    Cache-first: คืน articles ของวันนี้จาก DB
    ถ้ายังไม่มี → fetch จาก NewsAPI แล้ว cache ลง DB
    """
    today      = datetime.now().strftime("%Y-%m-%d")
    db_key     = symbol or ""   # ใช้ "" แทน None ใน DB

    # ── 1. ลอง DB ก่อน ──────────────────────────────────────────────────────
    cached = _load_from_db(today, db_key)
    if cached is not None:
        print(f"[news_feed] Serving {len(cached)} articles from cache ({db_key or 'general'})")
        return cached

    # ── 2. Fetch จาก API ─────────────────────────────────────────────────────
    print(f"[news_feed] Fetching from NewsAPI ({db_key or 'general'})...")
    articles = _fetch_from_api(symbol)

    # ── 3. Save ลง DB ────────────────────────────────────────────────────────
    _save_to_db(today, db_key, articles)

    return articles


if __name__ == "__main__":
    from portfolio.holdings import init_db
    init_db()

    print("=== General News ===")
    for a in get_news()[:3]:
        print(f"  [{a['source']}] {a['title'][:70]}")

    print("\n=== BTC News ===")
    for a in get_news("BTC")[:3]:
        print(f"  [{a['source']}] {a['title'][:70]}")

    print("\n=== General News (cached) ===")
    for a in get_news()[:2]:   # ครั้งนี้ต้องมาจาก DB
        print(f"  [{a['source']}] {a['title'][:70]}")
