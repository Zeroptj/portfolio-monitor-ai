"""
main.py — FastAPI backend server

Start:
  cd engine
  uvicorn main:app --host 127.0.0.1 --port 8000 --reload

All imports happen once at startup → ไม่มี subprocess overhead
"""

import os
import sys
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(ENGINE_DIR)
sys.path.insert(0, ENGINE_DIR)

# ── Load config ──────────────────────────────────────────────────────────────
with open(os.path.join(ROOT_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(title="Portfolio Monitor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Lazy imports (ทำที่นี่เพื่อให้ startup เร็ว) ──────────────────────────────
from portfolio.holdings import (
    SessionLocal, Holding, ETFHolding, ETFAllocation,
    get_holdings, add_holding, update_holding, delete_holding, init_db,
)
from data.price_feed import get_prices, fetch_fx_rate, get_price_histories_batch
from portfolio.metrics import get_portfolio_metrics, get_asset_metrics
from portfolio.optimizer import run_all_models, run_model, check_rebalance
from ai.summary import get_daily_summary
from ai.recommender import get_recommendation
from data.news_feed import get_news

init_db()

# ─── Models ──────────────────────────────────────────────────────────────────

class HoldingCreate(BaseModel):
    symbol:     str
    name:       str
    asset_type: str
    quantity:   float
    cost:       float

class HoldingUpdate(BaseModel):
    quantity: float | None = None
    cost:     float | None = None

class OptimizerRequest(BaseModel):
    model: str = "all"

class RecommendRequest(BaseModel):
    question: str


# ─── Holdings ────────────────────────────────────────────────────────────────

@app.get("/holdings")
def api_get_holdings():
    rows = get_holdings()
    return [
        {
            "id":         h.id,
            "symbol":     h.symbol,
            "name":       h.name,
            "asset_type": h.asset_type,
            "quantity":   h.quantity,
            "cost":       h.cost,
            "created_at": str(h.created_at),
            "updated_at": str(h.updated_at),
        }
        for h in rows
    ]

@app.post("/holdings", status_code=201)
def api_add_holding(body: HoldingCreate):
    h = add_holding(body.symbol, body.name, body.asset_type, body.quantity, body.cost)
    return {"id": h.id, "symbol": h.symbol}

@app.patch("/holdings/{id}")
def api_update_holding(id: int, body: HoldingUpdate):
    h = update_holding(id, quantity=body.quantity, cost=body.cost)
    if not h:
        raise HTTPException(404, "Not found")
    return {"id": h.id, "symbol": h.symbol}

@app.delete("/holdings/{id}")
def api_delete_holding(id: int):
    ok = delete_holding(id)
    return {"ok": ok}


# ─── Prices ──────────────────────────────────────────────────────────────────

@app.get("/prices")
def api_prices():
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()
    symbols = list({h.symbol for h in holdings}) if holdings else []
    return get_prices(symbols) if symbols else {}

@app.get("/prices/fx")
def api_fx():
    return {"rate": fetch_fx_rate()}


# ─── Portfolio ───────────────────────────────────────────────────────────────

@app.get("/portfolio/summary")
def api_summary():
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    if not holdings:
        return {"total_value": 0, "total_cost": 0, "total_pnl": 0,
                "total_pnl_pct": 0, "holdings": [], "metrics": {}}

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

    return {
        "total_value":   round(total_value, 2),
        "total_cost":    round(total_cost, 2),
        "total_pnl":     round(total_value - total_cost, 2),
        "total_pnl_pct": round((total_value - total_cost) / total_cost * 100, 2) if total_cost > 0 else 0,
        "holdings":      holdings_out,
        "metrics":       metrics,
    }

@app.get("/portfolio/metrics")
def api_metrics(days: int = 365, symbol: str | None = None):
    if symbol:
        return get_asset_metrics(symbol, days=days)
    return get_portfolio_metrics(days=days)

@app.get("/portfolio/allocation")
def api_allocation():
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    if not holdings:
        return {}

    symbols        = [h.symbol for h in holdings]
    current_prices = get_prices(symbols)
    values         = {h.symbol: h.quantity * current_prices.get(h.symbol, 0) for h in holdings}
    total          = sum(values.values()) or 1

    by_asset = {sym: round(val / total * 100, 2) for sym, val in values.items()}
    by_type: dict[str, float] = {}
    for h in holdings:
        t = h.asset_type or "other"
        by_type[t] = round(by_type.get(t, 0) + values[h.symbol] / total * 100, 2)

    db2 = SessionLocal()
    try:
        etf_symbols = [h.symbol for h in holdings if h.asset_type == "etf"]
        by_sector: dict[str, float] = {}
        by_region: dict[str, float] = {}
        by_etf: dict[str, list]     = {}

        for sym in etf_symbols:
            etf_weight = values.get(sym, 0) / total
            sec_rows = db2.query(ETFAllocation).filter(
                ETFAllocation.etf == sym, ETFAllocation.type == "sector"
            ).all()
            for r in sec_rows:
                by_sector[r.name] = round(by_sector.get(r.name, 0) + r.weight * etf_weight, 2)

            reg_rows = db2.query(ETFAllocation).filter(
                ETFAllocation.etf == sym, ETFAllocation.type == "region"
            ).all()
            for r in reg_rows:
                by_region[r.name] = round(by_region.get(r.name, 0) + r.weight * etf_weight, 2)

            etf_rows = db2.query(ETFHolding).filter(ETFHolding.etf == sym).all()
            by_etf[sym] = [{"name": r.name, "weight": r.weight} for r in etf_rows]
    finally:
        db2.close()

    return {
        "by_asset":  by_asset,
        "by_type":   by_type,
        "by_sector": by_sector,
        "by_region": by_region,
        "by_etf":    by_etf,
    }


# ─── Optimizer ───────────────────────────────────────────────────────────────

@app.post("/optimizer/run")
def api_optimizer_run(body: OptimizerRequest):
    if body.model == "all":
        return run_all_models()
    return run_model(body.model)

@app.get("/optimizer/rebalance")
def api_rebalance():
    return check_rebalance()


# ─── AI ──────────────────────────────────────────────────────────────────────

@app.get("/ai/summary")
def api_ai_summary(refresh: bool = False):
    return get_daily_summary(force_refresh=refresh)

@app.post("/ai/recommend")
def api_ai_recommend(body: RecommendRequest):
    return {"answer": get_recommendation(body.question)}


# ─── News ────────────────────────────────────────────────────────────────────

@app.get("/news")
def api_news(symbol: str | None = None):
    return get_news(symbol=symbol)


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}
