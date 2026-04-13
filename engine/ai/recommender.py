"""
recommender.py — AI recommendation ด้วย Gemini

Public functions:
  get_recommendation(question)         → ตอบคำถามเกี่ยวกับพอร์ต
  get_rebalance_advice(optimizer_results) → แนะนำ rebalance จาก optimizer output
"""

import os
import sys
import yaml
from dotenv import load_dotenv

import google.generativeai as genai

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR   = os.path.dirname(ENGINE_DIR)
sys.path.insert(0, ENGINE_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from portfolio.holdings import SessionLocal, Holding, init_db
from data.price_feed import get_prices
from portfolio.metrics import get_portfolio_metrics
from portfolio.optimizer import run_all_models

with open(os.path.join(ROOT_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

AI_CFG = config["ai"]
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_BASE = """คุณเป็น AI financial advisor ที่เชี่ยวชาญด้านการลงทุน
ตอบเป็นภาษาไทย กระชับ ตรงประเด็น
ไม่แนะนำให้ซื้อขายเฉพาะเจาะจง แต่ให้ข้อมูลและมุมมองที่เป็นประโยชน์
คำนึงถึงความเสี่ยงและ diversification เสมอ"""


# ─── Context Builders ────────────────────────────────────────────────────────

def _portfolio_snapshot() -> str:
    """สรุปพอร์ตสำหรับ context ของ Gemini"""
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    if not holdings:
        return "ไม่มี holdings"

    symbols        = [h.symbol for h in holdings]
    current_prices = get_prices(symbols)
    metrics        = get_portfolio_metrics(days=365)

    lines       = ["=== Portfolio Snapshot ==="]
    total_value = 0.0

    for h in holdings:
        price   = current_prices.get(h.symbol, 0)
        value   = h.quantity * price
        cost    = h.quantity * h.cost
        pnl_pct = ((value - cost) / cost * 100) if cost > 0 else 0
        total_value += value
        lines.append(
            f"{h.symbol} ({h.asset_type}): "
            f"qty={h.quantity}, price=${price:,.2f}, "
            f"value=${value:,.2f}, P&L={pnl_pct:+.2f}%"
        )

    lines.append(f"\nTotal Portfolio Value: ${total_value:,.2f}")

    if metrics:
        lines += [
            "\n=== Performance (365d) ===",
            f"Total Return     : {metrics.get('total_return_pct', 0):+.2f}%",
            f"Annualized Return: {metrics.get('annualized_return_pct', 0):+.2f}%",
            f"Sharpe Ratio     : {metrics.get('sharpe_ratio', 0):.3f}",
            f"Max Drawdown     : {metrics.get('max_drawdown_pct', 0):.2f}%",
            f"Volatility       : {metrics.get('volatility_pct', 0):.2f}%",
        ]
        bm = metrics.get("benchmark", {})
        if bm:
            lines += [
                f"Alpha vs {bm.get('benchmark', 'SPY')}: {bm.get('alpha_pct', 0):+.2f}%",
                f"Beta             : {bm.get('beta', 0):.3f}",
            ]

    return "\n".join(lines)


def _optimizer_summary(optimizer_results: dict) -> str:
    """แปลง optimizer results เป็น text สำหรับ Gemini"""
    if not optimizer_results:
        return "ไม่มีข้อมูล optimizer"

    lines = ["=== Optimizer Results ==="]
    for model_name, r in optimizer_results.items():
        if "error" in r:
            lines.append(f"\n[{model_name}] Error: {r['error']}")
            continue
        lines.append(f"\n[{model_name}]")
        lines.append(f"  Expected Return : {r.get('expected_return_pct', 0):+.2f}%")
        lines.append(f"  Expected Vol    : {r.get('expected_volatility_pct', 0):.2f}%")
        lines.append(f"  Sharpe Ratio    : {r.get('sharpe_ratio', 0):.3f}")
        lines.append("  Target Weights  :")
        for sym, w in sorted(r.get("weights", {}).items(), key=lambda x: -x[1]):
            lines.append(f"    {sym}: {w:.2f}%")

        top_moves = sorted(
            r.get("rebalance_plan", []),
            key=lambda x: abs(x["diff_pct"]),
            reverse=True,
        )[:5]
        if top_moves:
            lines.append("  Top Rebalance Moves:")
            for move in top_moves:
                lines.append(
                    f"    {move['symbol']}: {move['action']} "
                    f"({move['current_pct']:.1f}% → {move['target_pct']:.1f}%)"
                )

    return "\n".join(lines)


# ─── Gemini Calls ─────────────────────────────────────────────────────────────

def get_recommendation(question: str, context_days: int = 365) -> str:
    """
    ตอบคำถามเกี่ยวกับพอร์ตด้วย Gemini
    Returns: คำตอบเป็น string
    """
    snapshot = _portfolio_snapshot()
    model    = genai.GenerativeModel(
        model_name=AI_CFG["model"],
        system_instruction=SYSTEM_BASE,
    )

    print("[ai/recommender] Calling Gemini for recommendation...")
    response = model.generate_content(f"{snapshot}\n\nคำถาม: {question}")
    return response.text


def get_rebalance_advice(optimizer_results: dict | None = None) -> str:
    """
    แนะนำ rebalance plan จาก optimizer results
    ถ้า optimizer_results=None → run ใหม่เลย
    Returns: คำแนะนำเป็น string
    """
    if optimizer_results is None:
        print("[ai/recommender] Running optimizer...")
        optimizer_results = run_all_models()

    snapshot = _portfolio_snapshot()
    opt_text = _optimizer_summary(optimizer_results)
    prompt   = (
        f"{snapshot}\n\n"
        f"{opt_text}\n\n"
        "จากผล optimizer ทั้ง 5 model ด้านบน "
        "ช่วยสรุปว่าควร rebalance พอร์ตอย่างไร "
        "และ model ไหนเหมาะกับสไตล์การลงทุนแบบไหน"
    )

    model = genai.GenerativeModel(
        model_name=AI_CFG["model"],
        system_instruction=SYSTEM_BASE,
    )

    print("[ai/recommender] Calling Gemini for rebalance advice...")
    response = model.generate_content(prompt)
    return response.text


# ─── CLI test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()

    print("=== AI Recommendation ===\n")
    answer = get_recommendation("พอร์ตตอนนี้มีความเสี่ยงสูงไปไหม และควรปรับอะไร?")
    print(answer)

    print("\n" + "=" * 60)
    print("=== Rebalance Advice ===\n")
    advice = get_rebalance_advice()
    print(advice)
