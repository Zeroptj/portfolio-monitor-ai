"""
scheduler.py — Background job scheduler

Jobs:
  prices      every price_interval_seconds (default 5 min)
  news        daily at 08:00 Asia/Bangkok  — general + all holding symbols
  ai_summary  daily at 08:10 Asia/Bangkok  — after news
  etf_data    1st of every month           — Morningstar scrape

Start:
  cd engine
  python scheduler.py
"""

import os
import sys
import yaml
import logging
from datetime import datetime
from dotenv import load_dotenv

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron     import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(ENGINE_DIR)
sys.path.insert(0, ENGINE_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

with open(os.path.join(ROOT_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

_groq_key  = os.getenv("GROQ_API_KEY", "").strip()
_ai_flag   = os.getenv("AI_ENABLED", "true").lower()
AI_ENABLED = bool(_groq_key) and _ai_flag != "false"

PRICE_INTERVAL = config["refresh"]["price_interval_seconds"]   # default 300
SUMMARY_TIME   = config["refresh"]["ai_summary_time"]          # "08:00"
TZ             = config["refresh"]["timezone"]                  # "Asia/Bangkok"

_summary_hour, _summary_min = map(int, SUMMARY_TIME.split(":"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [scheduler] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scheduler")


# ─── Jobs ────────────────────────────────────────────────────────────────────

def job_prices():
    log.info("Refreshing prices...")
    try:
        from data.price_feed import get_prices, get_all_symbols
        syms = get_all_symbols()
        all_syms = syms["crypto"] + syms["stocks"] + syms["etf"] + syms["commodities"]
        prices = get_prices(all_syms)
        log.info(f"Prices updated — {len(prices)} symbols")
    except Exception as e:
        log.error(f"job_prices error: {e}")


def job_news():
    log.info("Refreshing news...")
    try:
        from portfolio.holdings import SessionLocal, Holding
        from data.news_feed import get_news, QUERY_MAP

        # symbols ที่อยู่ใน holdings และมีข่าวใน QUERY_MAP
        db = SessionLocal()
        try:
            holdings = db.query(Holding).all()
        finally:
            db.close()

        symbols = [h.symbol for h in holdings if h.symbol in QUERY_MAP]
        symbols = list(dict.fromkeys(symbols))  # dedupe, preserve order

        # General news
        articles = get_news(symbol=None)
        log.info(f"General news: {len(articles)} articles")

        # Per-symbol news
        for sym in symbols:
            articles = get_news(symbol=sym)
            log.info(f"  {sym}: {len(articles)} articles")

    except Exception as e:
        log.error(f"job_news error: {e}")


def job_ai_summary():
    log.info("Regenerating AI summary...")
    try:
        from ai.summary import get_daily_summary
        result = get_daily_summary(force_refresh=True)
        log.info(f"AI summary done — {len(result.get('summary', ''))} chars")
    except Exception as e:
        log.error(f"job_ai_summary error: {e}")


def job_etf_data():
    log.info("Refreshing Morningstar ETF data...")
    try:
        from data.morningstar import refresh_etf_data
        results = refresh_etf_data()
        ok = sum(v for v in results.values())
        log.info(f"ETF data done — {ok}/{len(results)} succeeded")
    except Exception as e:
        log.error(f"job_etf_data error: {e}")


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from portfolio.holdings import init_db
    init_db()

    scheduler = BlockingScheduler(timezone=TZ)

    # Prices — every N seconds
    scheduler.add_job(
        job_prices,
        trigger=IntervalTrigger(seconds=PRICE_INTERVAL),
        id="prices",
        next_run_time=datetime.now(),   # run immediately on start
    )

    # News — daily at 08:00
    scheduler.add_job(
        job_news,
        trigger=CronTrigger(hour=_summary_hour, minute=_summary_min, timezone=TZ),
        id="news",
    )

    # AI summary — daily at 08:10 (after news) — only if AI enabled
    if AI_ENABLED:
        scheduler.add_job(
            job_ai_summary,
            trigger=CronTrigger(hour=_summary_hour, minute=_summary_min + 10, timezone=TZ),
            id="ai_summary",
        )
    else:
        log.info("AI summary job skipped — GROQ_API_KEY not set or AI_ENABLED=false")

    # ETF data — 1st of every month at 02:00
    scheduler.add_job(
        job_etf_data,
        trigger=CronTrigger(day=1, hour=2, minute=0, timezone=TZ),
        id="etf_data",
    )

    log.info(
        f"Scheduler started — "
        f"prices every {PRICE_INTERVAL}s | "
        f"news+AI daily {SUMMARY_TIME} | "
        f"ETF monthly"
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")
