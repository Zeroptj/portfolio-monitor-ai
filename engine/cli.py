"""
cli.py — Python entry point สำหรับ Next.js API Routes

Next.js เรียกผ่าน subprocess แล้วอ่าน JSON จาก stdout

Usage:
  python cli.py prices
  python cli.py holdings
  python cli.py holdings --action add --symbol BTC --name Bitcoin --asset_type crypto --quantity 0.5 --cost 50000
  python cli.py holdings --action delete --id 1
  python cli.py metrics --days 365
  python cli.py allocation
  python cli.py optimizer --model all
  python cli.py optimizer --model max_sharpe
  python cli.py rebalance
  python cli.py ai-summary
  python cli.py ai-summary --refresh
  python cli.py recommend --question "พอร์ตเสี่ยงไปไหม"
  python cli.py news
  python cli.py news --symbol BTC
  python cli.py fx
"""

import sys
import os
import json
import argparse
import io

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

# Force UTF-8 on stderr so Thai print() calls don't crash on Windows
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# redirect print() ทั้งหมดจาก engine modules ไป stderr
# เพื่อให้ stdout มีแค่ JSON output เท่านั้น
sys.stdout = sys.stderr

# Keep a UTF-8 binary reference to real stdout for JSON output
_STDOUT_BUF = sys.__stdout__.buffer if hasattr(sys.__stdout__, "buffer") else None


def _out(data):
    """Write JSON to real stdout as UTF-8 bytes (bypasses charmap on Windows)"""
    raw = (json.dumps(data, ensure_ascii=False, default=str) + "\n").encode("utf-8")
    if _STDOUT_BUF:
        _STDOUT_BUF.write(raw)
        _STDOUT_BUF.flush()
    else:
        sys.__stdout__.write(raw.decode("utf-8"))
        sys.__stdout__.flush()


def cmd_prices(_args):
    from data.price_feed import get_prices
    _out(get_prices())


def cmd_fx(_args):
    from data.price_feed import fetch_fx_rate
    _out({"rate": fetch_fx_rate()})


def cmd_holdings(args):
    from portfolio.holdings import get_holdings, add_holding, update_holding, delete_holding

    action = getattr(args, "action", None) or "list"

    if action == "list":
        rows = get_holdings()
        _out([
            {
                "id":         h.id,
                "symbol":     h.symbol,
                "name":       h.name,
                "asset_type": h.asset_type,
                "exchange":   h.exchange,
                "quantity":   h.quantity,
                "cost":       h.cost,
                "created_at": str(h.created_at),
                "updated_at": str(h.updated_at),
            }
            for h in rows
        ])

    elif action == "add":
        h = add_holding(
            symbol     = args.symbol,
            name       = args.name or args.symbol,
            asset_type = args.asset_type,
            quantity   = float(args.quantity),
            cost       = float(args.cost),
            exchange   = getattr(args, "exchange", None) or None,
        )
        _out({"id": h.id, "symbol": h.symbol, "asset_type": h.asset_type, "exchange": h.exchange})

    elif action == "update":
        h = update_holding(
            id       = int(args.id),
            quantity = float(args.quantity) if args.quantity else None,
            cost     = float(args.cost) if args.cost else None,
        )
        _out({"id": h.id, "symbol": h.symbol})

    elif action == "delete":
        ok = delete_holding(int(args.id))
        _out({"ok": ok})


def cmd_metrics(args):
    from portfolio.metrics import get_portfolio_metrics, get_asset_metrics
    days = int(args.days) if args.days else 365
    if args.symbol:
        _out(get_asset_metrics(args.symbol, days=days))
    else:
        _out(get_portfolio_metrics(days=days))


def cmd_allocation(_args):
    from portfolio.holdings import SessionLocal, Holding, ETFHolding, ETFAllocation
    from data.price_feed import get_prices

    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    if not holdings:
        _out({})
        return

    symbols        = [h.symbol for h in holdings]
    current_prices = get_prices(symbols)

    values = {h.symbol: h.quantity * current_prices.get(h.symbol, 0) for h in holdings}
    total  = sum(values.values()) or 1

    # by_asset
    by_asset = {sym: round(val / total * 100, 2) for sym, val in values.items()}

    # by_type
    by_type: dict[str, float] = {}
    for h in holdings:
        t = h.asset_type or "other"
        by_type[t] = round(by_type.get(t, 0) + values[h.symbol] / total * 100, 2)

    # by_sector / by_exposure / by_region / by_etf
    by_sector:   dict[str, float] = {}
    by_exposure: dict[str, float] = {}
    by_region:   dict[str, float] = {}
    by_etf:      dict[str, list]  = {}

    db = SessionLocal()
    try:
        etf_symbols = [h.symbol for h in holdings if h.asset_type == "etf"]
        for sym in etf_symbols:
            etf_weight = values.get(sym, 0) / total
            for alloc_type, target in [("sector", by_sector), ("exposure", by_exposure), ("region", by_region)]:
                rows = db.query(ETFAllocation).filter(
                    ETFAllocation.etf  == sym,
                    ETFAllocation.type == alloc_type,
                ).all()
                for r in rows:
                    target[r.name] = round(target.get(r.name, 0) + r.weight * etf_weight, 2)

            etf_rows = db.query(ETFHolding).filter(ETFHolding.etf == sym).all()
            by_etf[sym] = [{"name": r.name, "weight": r.weight} for r in etf_rows]
    finally:
        db.close()

    _out({
        "by_asset":    by_asset,
        "by_type":     by_type,
        "by_sector":   by_sector,
        "by_exposure": by_exposure,
        "by_region":   by_region,
        "by_etf":      by_etf,
    })


def cmd_summary(_args):
    from portfolio.holdings import SessionLocal, Holding
    from data.price_feed import get_prices
    from portfolio.metrics import get_portfolio_metrics

    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    symbols        = [h.symbol for h in holdings]
    current_prices = get_prices(symbols)
    metrics        = get_portfolio_metrics(days=365)

    values      = {h.symbol: h.quantity * current_prices.get(h.symbol, 0) for h in holdings}
    total_value = sum(values.values())
    total_cost  = sum(h.quantity * h.cost for h in holdings)

    holdings_out = [
        {
            "symbol":     h.symbol,
            "name":       h.name,
            "asset_type": h.asset_type,
            "exchange":   h.exchange,
            "quantity":   h.quantity,
            "cost":       h.cost,
            "price":      current_prices.get(h.symbol, 0),
            "value":      values[h.symbol],
            "pnl":        values[h.symbol] - h.quantity * h.cost,
            "pnl_pct":    round(
                (values[h.symbol] - h.quantity * h.cost) / (h.quantity * h.cost) * 100, 2
            ) if h.cost > 0 else 0,
            "weight_pct": round(values[h.symbol] / total_value * 100, 2) if total_value > 0 else 0,
        }
        for h in holdings
    ]

    _out({
        "total_value": round(total_value, 2),
        "total_cost":  round(total_cost, 2),
        "total_pnl":   round(total_value - total_cost, 2),
        "total_pnl_pct": round((total_value - total_cost) / total_cost * 100, 2) if total_cost > 0 else 0,
        "holdings":    holdings_out,
        "metrics":     metrics,
    })


def cmd_optimizer(args):
    from portfolio.optimizer import run_all_models, run_model
    model = getattr(args, "model", "all") or "all"
    if model == "all":
        _out(run_all_models())
    else:
        _out(run_model(model))


def cmd_rebalance(_args):
    from portfolio.optimizer import check_rebalance
    _out(check_rebalance())


def cmd_ai_summary(args):
    from ai.summary import get_daily_summary
    force = getattr(args, "refresh", False)
    _out(get_daily_summary(force_refresh=bool(force)))


def cmd_recommend(args):
    from ai.recommender import get_recommendation
    question = getattr(args, "question", "") or ""
    _out({"answer": get_recommendation(question)})


def cmd_ai_allocation(_args):
    from portfolio.holdings import SessionLocal, Holding, ETFAllocation
    from data.price_feed import get_prices
    from ai.recommender import get_allocation_insight

    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    if not holdings:
        _out({"insight": "ไม่มีข้อมูล holdings"})
        return

    symbols        = [h.symbol for h in holdings]
    current_prices = get_prices(symbols)
    values         = {h.symbol: h.quantity * current_prices.get(h.symbol, 0) for h in holdings}
    total          = sum(values.values()) or 1

    by_type: dict[str, float] = {}
    for h in holdings:
        t = h.asset_type or "other"
        by_type[t] = round(by_type.get(t, 0) + values[h.symbol] / total * 100, 2)

    by_sector: dict[str, float] = {}
    by_exposure: dict[str, float] = {}
    by_region: dict[str, float] = {}

    db2 = SessionLocal()
    try:
        etf_syms = [h.symbol for h in holdings if h.asset_type == "etf"]
        for sym in etf_syms:
            etf_weight = values.get(sym, 0) / total
            for at, target in [("sector", by_sector), ("exposure", by_exposure), ("region", by_region)]:
                for r in db2.query(ETFAllocation).filter(ETFAllocation.etf == sym, ETFAllocation.type == at).all():
                    target[r.name] = round(target.get(r.name, 0) + r.weight * etf_weight, 2)
    finally:
        db2.close()

    alloc = {"by_type": by_type, "by_sector": by_sector, "by_exposure": by_exposure, "by_region": by_region}
    _out({"insight": get_allocation_insight(alloc)})


def cmd_ai_optimizer(_args):
    from portfolio.optimizer import run_all_models
    from ai.recommender import get_optimizer_advice
    results = run_all_models()
    _out({"advice": get_optimizer_advice(results), "results": results})


def cmd_news(args):
    from data.news_feed import get_news
    symbol = getattr(args, "symbol", None)
    _out(get_news(symbol=symbol))


def cmd_morningstar(args):
    """Scrape Morningstar สำหรับ ETF เดียว แล้ว save ลง DB"""
    from data.morningstar import scrape_etf
    symbol   = (getattr(args, "symbol",   None) or "").upper()
    exchange = (getattr(args, "exchange", None) or "arcx").lower()
    if not symbol:
        _out({"error": "symbol required"})
        return
    ok = scrape_etf(symbol, exchange)
    _out({"ok": ok, "symbol": symbol, "exchange": exchange})


def cmd_refresh(args):
    """
    Refresh ราคาปัจจุบัน + price history เฉพาะวันใหม่ที่ยังไม่มีใน DB
    สำหรับแค่ symbol ที่อยู่ใน holdings เท่านั้น
    """
    from portfolio.holdings import SessionLocal, Holding, PriceHistory
    from data.price_feed import (
        get_prices, fetch_crypto_history, fetch_yfinance_history,
        save_price_history, _classify,
    )
    from datetime import datetime, timedelta

    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    if not holdings:
        _out({"ok": True, "message": "No holdings to refresh", "updated": []})
        return

    symbols = list({h.symbol for h in holdings})
    print(f"[refresh] Holdings symbols: {symbols}")

    # ── 1. ราคาปัจจุบัน (force refresh โดยลบ cache ก่อน) ────────────────────
    db = SessionLocal()
    try:
        from portfolio.holdings import Price
        db.query(Price).filter(Price.symbol.in_(symbols)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

    current = get_prices(symbols)
    print(f"[refresh] Current prices: {current}")

    # ── 2. Price history — fetch เฉพาะวันที่ยังไม่มีใน DB ──────────────────
    today     = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    updated   = []

    db = SessionLocal()
    try:
        rows = db.query(PriceHistory).filter(
            PriceHistory.symbol.in_(symbols)
        ).all()
    finally:
        db.close()

    # หา latest date ของแต่ละ symbol
    latest_by_symbol: dict[str, str] = {}
    for r in rows:
        if r.symbol not in latest_by_symbol or r.date > latest_by_symbol[r.symbol]:
            latest_by_symbol[r.symbol] = r.date

    # แบ่ง symbol ตามว่าต้องการ days เท่าไหน
    needs_full   = [s for s in symbols if s not in latest_by_symbol]        # ยังไม่มีเลย
    needs_update = [s for s in symbols if s in latest_by_symbol
                    and latest_by_symbol[s] < yesterday]                    # มีแต่ยังไม่ถึงเมื่อวาน
    fresh        = [s for s in symbols if s in latest_by_symbol
                    and latest_by_symbol[s] >= yesterday]                   # สดแล้ว

    print(f"[refresh] needs_full={needs_full} needs_update={needs_update} fresh={fresh}")

    # fetch full (365 วัน)
    if needs_full:
        crypto, yf = _classify(needs_full)
        hist: dict = {}
        for sym in crypto:
            h = fetch_crypto_history(sym, days=365)
            if h: hist[sym] = h
        if yf:
            hist.update(fetch_yfinance_history(yf, days=365))
        if hist:
            save_price_history(hist)
            updated.extend(needs_full)

    # fetch incremental (นับจาก latest_date ถึงวันนี้)
    if needs_update:
        crypto, yf = _classify(needs_update)
        hist = {}

        # คำนวณ days ที่ต้องดึง (max ของทุก symbol ที่ต้อง update)
        max_days = max(
            (datetime.now() - datetime.strptime(latest_by_symbol[s], "%Y-%m-%d")).days + 2
            for s in needs_update
        )

        for sym in crypto:
            h = fetch_crypto_history(sym, days=max_days)
            # เก็บเฉพาะวันใหม่
            cutoff = latest_by_symbol.get(sym, "")
            if h:
                hist[sym] = {d: v for d, v in h.items() if d > cutoff}

        if yf:
            raw = fetch_yfinance_history(yf, days=max_days)
            for sym, h in raw.items():
                cutoff = latest_by_symbol.get(sym, "")
                hist[sym] = {d: v for d, v in h.items() if d > cutoff}

        if hist:
            save_price_history(hist)
            updated.extend(needs_update)

    _out({
        "ok":      True,
        "symbols": symbols,
        "prices":  current,
        "updated": updated,
        "fresh":   fresh,
        "message": f"Refreshed {len(updated)} symbol(s), {len(fresh)} already up-to-date",
    })


# ─── Main ────────────────────────────────────────────────────────────────────

COMMANDS = {
    "prices":      cmd_prices,
    "fx":          cmd_fx,
    "holdings":    cmd_holdings,
    "metrics":     cmd_metrics,
    "allocation":  cmd_allocation,
    "summary":     cmd_summary,
    "optimizer":   cmd_optimizer,
    "rebalance":   cmd_rebalance,
    "ai-summary":       cmd_ai_summary,
    "recommend":        cmd_recommend,
    "ai-allocation":    cmd_ai_allocation,
    "ai-optimizer":     cmd_ai_optimizer,
    "news":        cmd_news,
    "refresh":     cmd_refresh,
    "morningstar": cmd_morningstar,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=COMMANDS.keys())
    parser.add_argument("--action",     default=None)
    parser.add_argument("--symbol",     default=None)
    parser.add_argument("--name",       default=None)
    parser.add_argument("--asset_type", default=None)
    parser.add_argument("--quantity",   default=None)
    parser.add_argument("--cost",       default=None)
    parser.add_argument("--id",         default=None)
    parser.add_argument("--days",       default=365)
    parser.add_argument("--model",      default="all")
    parser.add_argument("--question",   default=None)
    parser.add_argument("--refresh",    action="store_true")
    parser.add_argument("--exchange",   default=None)

    args   = parser.parse_args()
    fn     = COMMANDS[args.command]

    try:
        fn(args)
    except Exception as e:
        _out({"error": str(e)})
        sys.exit(1)
