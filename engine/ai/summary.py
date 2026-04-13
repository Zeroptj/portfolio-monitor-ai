"""
summary.py — สรุปพอร์ตรายวันด้วย Gemini

Public functions:
  get_daily_summary()  → คืน summary วันนี้ (cache-first จาก DB)
  generate_summary()   → สร้าง summary ใหม่ด้วย Gemini แล้ว save ลง DB
"""

import os
import sys
import yaml
from datetime import datetime
from dotenv import load_dotenv

import google.generativeai as genai

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR   = os.path.dirname(ENGINE_DIR)
sys.path.insert(0, ENGINE_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from portfolio.holdings import SessionLocal, Holding, AISummary, init_db
from data.price_feed import get_prices
from portfolio.metrics import get_portfolio_metrics

with open(os.path.join(ROOT_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

AI_CFG = config["ai"]
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


# ─── Context Builder ─────────────────────────────────────────────────────────

def _build_portfolio_context() -> str:
    """รวบรวมข้อมูลพอร์ตสำหรับส่งให้ Gemini"""
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    if not holdings:
        return "ไม่มีข้อมูล holdings"

    symbols        = [h.symbol for h in holdings]
    current_prices = get_prices(symbols)
    metrics        = get_portfolio_metrics(days=365)

    holdings_lines = []
    total_value    = 0.0
    for h in holdings:
        price   = current_prices.get(h.symbol, 0)
        value   = h.quantity * price
        cost    = h.quantity * h.cost
        pnl_pct = ((value - cost) / cost * 100) if cost > 0 else 0
        total_value += value
        holdings_lines.append(
            f"  {h.symbol} ({h.asset_type}): qty={h.quantity}, "
            f"price=${price:,.2f}, value=${value:,.2f}, "
            f"P&L={pnl_pct:+.2f}%"
        )

    metrics_lines = []
    if metrics:
        metrics_lines = [
            f"  Total Value     : ${metrics.get('current_value', 0):,.2f}",
            f"  Total Return    : {metrics.get('total_return_pct', 0):+.2f}%",
            f"  Annualized Ret  : {metrics.get('annualized_return_pct', 0):+.2f}%",
            f"  Sharpe Ratio    : {metrics.get('sharpe_ratio', 0):.3f}",
            f"  Max Drawdown    : {metrics.get('max_drawdown_pct', 0):.2f}%",
            f"  Volatility      : {metrics.get('volatility_pct', 0):.2f}%",
        ]
        bm = metrics.get("benchmark", {})
        if bm:
            metrics_lines += [
                f"  Alpha vs {bm.get('benchmark', 'SPY')}: {bm.get('alpha_pct', 0):+.2f}%",
                f"  Beta            : {bm.get('beta', 0):.3f}",
            ]

    today = datetime.now().strftime("%Y-%m-%d")
    return (
        f"วันที่: {today}\n\n"
        f"Holdings:\n" + "\n".join(holdings_lines) + "\n\n"
        f"Portfolio Metrics (365 วัน):\n" + "\n".join(metrics_lines)
    )


# ─── Gemini Call ─────────────────────────────────────────────────────────────

def generate_summary() -> str:
    """
    สร้าง AI summary ใหม่ด้วย Gemini แล้ว save ลง DB
    Returns summary text
    """
    context       = _build_portfolio_context()
    system_prompt = AI_CFG.get("summary_prompt", "วิเคราะห์พอร์ตการลงทุนนี้เป็นภาษาไทย")

    model = genai.GenerativeModel(
        model_name=AI_CFG["model"],
        system_instruction=system_prompt,
    )

    print("[ai/summary] Calling Gemini...")
    response     = model.generate_content(f"ข้อมูลพอร์ตปัจจุบัน:\n\n{context}")
    summary_text = response.text
    today        = datetime.now().strftime("%Y-%m-%d")

    db = SessionLocal()
    try:
        existing = db.query(AISummary).filter(AISummary.date == today).first()
        if existing:
            existing.summary = summary_text
        else:
            db.add(AISummary(date=today, summary=summary_text))
        db.commit()
        print(f"[ai/summary] Saved summary for {today}")
    except Exception as e:
        db.rollback()
        print(f"[ai/summary] DB error: {e}")
    finally:
        db.close()

    return summary_text


# ─── Cache-first Getter ──────────────────────────────────────────────────────

def get_daily_summary(force_refresh: bool = False) -> dict:
    """
    Cache-first: คืน summary วันนี้จาก DB
    ถ้าไม่มี หรือ force_refresh=True → generate ใหม่
    Returns {"date": str, "summary": str}
    """
    today = datetime.now().strftime("%Y-%m-%d")

    if not force_refresh:
        db = SessionLocal()
        try:
            row = db.query(AISummary).filter(AISummary.date == today).first()
            if row:
                return {"date": row.date, "summary": row.summary}
        finally:
            db.close()

    summary = generate_summary()
    return {"date": today, "summary": summary}


# ─── CLI test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()

    print("=== AI Daily Summary ===\n")
    result = get_daily_summary()
    print(f"Date: {result['date']}\n")
    print(result["summary"])
