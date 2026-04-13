import os
import sys
import time
import yaml
import requests
import yfinance as yf
from datetime import datetime, timedelta
from sqlalchemy import and_

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR   = os.path.dirname(ENGINE_DIR)
sys.path.insert(0, ENGINE_DIR)

from portfolio.holdings import SessionLocal, Price, PriceHistory, init_db

with open(os.path.join(ROOT_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

COINGECKO_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
}


# ─── Helpers ────────────────────────────────────────────────────────────────

def get_all_symbols() -> dict[str, list[str]]:
    assets = config["assets"]
    return {
        "crypto":      [a["symbol"] for a in assets.get("crypto", [])],
        "stocks":      [a["symbol"] for a in assets.get("stocks", [])],
        "etf":         [a["symbol"] for a in assets.get("etf", [])],
        "commodities": [a["symbol"] for a in assets.get("commodities", [])],
    }


def _classify(symbols: list[str]) -> tuple[list[str], list[str]]:
    """แยก symbols เป็น crypto vs yfinance"""
    crypto = [s for s in symbols if s in COINGECKO_IDS]
    yf_sym = [s for s in symbols if s not in COINGECKO_IDS]
    return crypto, yf_sym


# ─── Fetch: Current Prices ───────────────────────────────────────────────────

def fetch_crypto_prices(symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {}
    ids = [COINGECKO_IDS[s] for s in symbols if s in COINGECKO_IDS]
    if not ids:
        return {}
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ",".join(ids), "vs_currencies": "usd"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        id_to_symbol = {v: k for k, v in COINGECKO_IDS.items()}
        return {
            id_to_symbol[gid]: float(info["usd"])
            for gid, info in data.items()
            if gid in id_to_symbol
        }
    except Exception as e:
        print(f"[price_feed] CoinGecko price error: {e}")
        return {}


def _is_rate_limited(e: Exception) -> bool:
    s = str(e).lower()
    return "rate limit" in s or "too many requests" in s or "429" in s


def fetch_yfinance_prices(symbols: list[str]) -> dict[str, float]:
    """ดึงราคาปัจจุบันด้วย Ticker.fast_info"""
    if not symbols:
        return {}
    unique = list(dict.fromkeys(symbols))
    prices: dict[str, float] = {}
    for symbol in unique:
        for attempt in range(2):
            try:
                info  = yf.Ticker(symbol).fast_info
                price = float(info.get("lastPrice") or info.get("regularMarketPrice") or 0)
                if price > 0:
                    prices[symbol] = price
                break
            except Exception as e:
                if _is_rate_limited(e):
                    print(f"[price_feed] Rate limited on {symbol}, skipping retry")
                    break   # ไม่ retry เมื่อโดน rate limit
                print(f"[price_feed] price error {symbol} (attempt {attempt+1}): {e}")
                if attempt == 0:
                    time.sleep(1)
    return prices


def fetch_fx_rate() -> float:
    try:
        data = yf.download("THB=X", period="2d", auto_adjust=True, progress=False)
        series = data["Close"].dropna()
        if not series.empty:
            return float(series.iloc[-1])
    except Exception as e:
        print(f"[price_feed] FX rate error: {e}")
    return 35.0


# ─── Fetch: Price History ────────────────────────────────────────────────────

def fetch_crypto_history(symbol: str, days: int = 365) -> dict[str, float]:
    gecko_id = COINGECKO_IDS.get(symbol)
    if not gecko_id:
        return {}
    try:
        resp = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{gecko_id}/market_chart",
            params={"vs_currency": "usd", "days": days, "interval": "daily"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d"): float(price)
            for ts, price in data.get("prices", [])
        }
    except Exception as e:
        print(f"[price_feed] CoinGecko history error ({symbol}): {e}")
        return {}


def fetch_yfinance_history(
    symbols: list[str], days: int = 365, batch_size: int = 8
) -> dict[str, dict[str, float]]:
    if not symbols:
        return {}
    start   = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    history: dict[str, dict[str, float]] = {}

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i: i + batch_size]
        print(f"[price_feed] Downloading history: {batch}")
        for attempt in range(2):
            try:
                data  = yf.download(batch, start=start, auto_adjust=True, progress=False)
                close = data["Close"]
                if len(batch) == 1:
                    series = close.dropna()
                    history[batch[0]] = {str(idx.date()): float(val) for idx, val in series.items()}
                else:
                    for symbol in batch:
                        if symbol in close.columns:
                            series = close[symbol].dropna()
                            history[symbol] = {str(idx.date()): float(val) for idx, val in series.items()}
                break
            except Exception as e:
                if _is_rate_limited(e):
                    print(f"[price_feed] Rate limited on history {batch}, skipping retry")
                    break
                print(f"[price_feed] history error (attempt {attempt+1}): {e}")
                if attempt == 0:
                    time.sleep(3)
        if i + batch_size < len(symbols):
            time.sleep(1)
    return history


# ─── Save to DB ──────────────────────────────────────────────────────────────

def save_current_prices(prices: dict[str, float]):
    db = SessionLocal()
    try:
        now = datetime.now()
        for symbol, price in prices.items():
            row = db.query(Price).filter(Price.symbol == symbol).first()
            if row:
                row.price      = price
                row.updated_at = now
            else:
                db.add(Price(symbol=symbol, price=price, currency="USD", updated_at=now))
        db.commit()
        print(f"[price_feed] Saved {len(prices)} current prices")
    except Exception as e:
        db.rollback()
        print(f"[price_feed] DB error (current prices): {e}")
    finally:
        db.close()


def save_price_history(history: dict[str, dict[str, float]]):
    db = SessionLocal()
    try:
        now      = datetime.now()
        inserted = 0
        for symbol, dates in history.items():
            # bulk-check existing dates for this symbol
            existing = {
                r.date
                for r in db.query(PriceHistory.date)
                         .filter(PriceHistory.symbol == symbol)
                         .all()
            }
            for date_str, close in dates.items():
                if date_str not in existing:
                    db.add(PriceHistory(symbol=symbol, date=date_str, close=close, updated_at=now))
                    inserted += 1
        db.commit()
        print(f"[price_feed] Saved {inserted} price history rows")
    except Exception as e:
        db.rollback()
        print(f"[price_feed] DB error (price history): {e}")
    finally:
        db.close()


# ─── Cache-first Getters ────────────────────────────────────────────────────

def get_prices(symbols: list[str] | None = None) -> dict[str, float]:
    """
    Cache-first: คืนราคาจาก DB ถ้ายังสด
    ถ้า miss → fetch เฉพาะ symbol ที่หมดอายุ/ไม่มี (ไม่ fetch ทั้งหมด)
    """
    if symbols is None:
        all_syms = get_all_symbols()
        symbols  = (all_syms["crypto"] + all_syms["stocks"] +
                    all_syms["etf"]    + all_syms["commodities"])

    stale_sec = config["refresh"]["price_interval_seconds"]
    now       = datetime.now()

    db = SessionLocal()
    try:
        rows   = db.query(Price).filter(Price.symbol.in_(symbols)).all()
        cached = {r.symbol: r for r in rows}
    finally:
        db.close()

    fresh = {
        sym: cached[sym].price
        for sym in symbols
        if sym in cached
        and (now - cached[sym].updated_at).total_seconds() < stale_sec
    }

    stale = [s for s in symbols if s not in fresh]
    if not stale:
        return fresh

    # Stale-but-existing as fallback (ใช้ถ้า fetch ไม่สำเร็จ)
    stale_fallback = {sym: cached[sym].price for sym in stale if sym in cached}

    # Fetch only the stale/missing symbols
    print(f"[price_feed] Refreshing {len(stale)} stale prices: {stale}")
    crypto, yf_syms = _classify(stale)
    refreshed: dict[str, float] = {}
    if crypto:
        refreshed.update(fetch_crypto_prices(crypto))
    if yf_syms:
        refreshed.update(fetch_yfinance_prices(yf_syms))

    if refreshed:
        save_current_prices(refreshed)

    # merge: fresh > refreshed > stale fallback
    return {**stale_fallback, **fresh, **refreshed}


def get_price_history(symbol: str, days: int = 365) -> dict[str, float]:
    """
    Cache-first: คืน price history จาก DB
    ถ้า miss → fetch เฉพาะ symbol นั้น (ไม่ fetch ทั้งหมด)
    """
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    db = SessionLocal()
    try:
        rows = (
            db.query(PriceHistory)
            .filter(PriceHistory.symbol == symbol, PriceHistory.date >= start)
            .all()
        )
        if rows:
            latest = max(r.date for r in rows)
            cutoff = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            if latest >= cutoff:
                return {r.date: r.close for r in rows}
    finally:
        db.close()

    # Fetch only this symbol
    print(f"[price_feed] Fetching history for {symbol} ({days}d)...")
    crypto, yf_syms = _classify([symbol])
    hist: dict[str, float] = {}
    if crypto:
        hist = fetch_crypto_history(symbol, days=days)
    elif yf_syms:
        hist = fetch_yfinance_history([symbol], days=days).get(symbol, {})

    if hist:
        save_price_history({symbol: hist})
    return {d: v for d, v in hist.items() if d >= start}


def get_price_histories_batch(symbols: list[str], days: int = 365) -> dict[str, dict[str, float]]:
    """
    Batch cache-first: ดึง history หลาย symbol ครั้งเดียว
    - ถ้ามีใน DB ครบ → return จาก DB เลย
    - ถ้ามี miss → fetch เฉพาะ symbol ที่ miss ในครั้งเดียว (batch yfinance)
    """
    start  = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    cutoff = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Load all from DB at once
    db = SessionLocal()
    try:
        rows = (
            db.query(PriceHistory)
            .filter(PriceHistory.symbol.in_(symbols), PriceHistory.date >= start)
            .all()
        )
    finally:
        db.close()

    # Group by symbol
    by_symbol: dict[str, dict[str, float]] = {s: {} for s in symbols}
    for r in rows:
        by_symbol[r.symbol][r.date] = r.close

    # Determine which symbols are fresh
    fresh_syms = {
        sym for sym, hist in by_symbol.items()
        if hist and max(hist.keys()) >= cutoff
    }
    stale_syms = [s for s in symbols if s not in fresh_syms]

    if stale_syms:
        print(f"[price_feed] Batch fetching history: {stale_syms}")
        crypto, yf_syms = _classify(stale_syms)

        new_hist: dict[str, dict[str, float]] = {}
        for sym in crypto:
            h = fetch_crypto_history(sym, days=days)
            if h:
                new_hist[sym] = h

        if yf_syms:
            yf_h = fetch_yfinance_history(yf_syms, days=days)
            new_hist.update(yf_h)

        if new_hist:
            save_price_history(new_hist)
            for sym, hist in new_hist.items():
                by_symbol[sym] = {d: v for d, v in hist.items() if d >= start}

    return {sym: hist for sym, hist in by_symbol.items() if hist}


# ─── Full Refresh Jobs (ใช้จาก scheduler เท่านั้น) ──────────────────────────

def refresh_prices() -> dict[str, float]:
    """Fetch + save ราคาปัจจุบันทุก asset (scheduler job)"""
    symbols = get_all_symbols()
    all_syms = (symbols["crypto"] + symbols["stocks"] +
                symbols["etf"]    + symbols["commodities"])
    return get_prices(all_syms)


def refresh_price_history(days: int = 365) -> dict[str, dict[str, float]]:
    """Fetch + save ราคาย้อนหลังทุก asset (scheduler job)"""
    symbols = get_all_symbols()
    all_syms = (symbols["crypto"] + symbols["stocks"] +
                symbols["etf"]    + symbols["commodities"])
    return get_price_histories_batch(all_syms, days=days)


# ─── CLI test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("\n=== Current Prices ===")
    prices = refresh_prices()
    for symbol, price in sorted(prices.items()):
        print(f"  {symbol:10s} ${price:>12,.2f}")
    fx = fetch_fx_rate()
    print(f"\n  USD/THB: {fx:.2f}")
    print("\n=== Price History (30d sample) ===")
    refresh_price_history(days=30)
    print("\nDone.")
