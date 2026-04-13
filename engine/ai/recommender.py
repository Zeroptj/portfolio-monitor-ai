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

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR   = os.path.dirname(ENGINE_DIR)
sys.path.insert(0, ENGINE_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

from portfolio.holdings import SessionLocal, Holding, init_db
from data.price_feed import get_prices
from portfolio.metrics import get_portfolio_metrics

with open(os.path.join(ENGINE_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

AI_CFG = config["ai"]

_groq_client = None

def _groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq_client

SYSTEM_BASE = """You are an AI financial advisor specializing in investment portfolio analysis.
Respond in English. Be concise and to the point.
Do not give specific buy/sell recommendations, but provide useful data-driven insights.
Always consider risk and diversification."""


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

def get_recommendation(question: str) -> str:
    """
    ตอบคำถามเกี่ยวกับพอร์ตด้วย Gemini
    Returns: คำตอบเป็น string
    """
    snapshot = _portfolio_snapshot()

    print("[ai/recommender] Calling Groq for recommendation...")
    response = _groq().chat.completions.create(
        model=AI_CFG["model"],
        messages=[
            {"role": "system", "content": SYSTEM_BASE},
            {"role": "user",   "content": f"{snapshot}\n\nคำถาม: {question}"},
        ],
        max_tokens=AI_CFG.get("max_tokens", 500),
    )
    return response.choices[0].message.content


# ─── Allocation Insight ──────────────────────────────────────────────────────

def get_allocation_insight(alloc: dict) -> str:
    """
    วิเคราะห์ portfolio allocation — ส่งแค่ summary ไม่ใช่ข้อมูลดิบทั้งหมด
    """
    def _top(d: dict, n: int = 5) -> str:
        return ", ".join(
            f"{k}={v:.1f}%" for k, v in sorted(d.items(), key=lambda x: -x[1])[:n]
        )

    lines = ["=== Portfolio Allocation ==="]
    if alloc.get("by_type"):
        lines.append(f"By Type       : {_top(alloc['by_type'], 6)}")
    if alloc.get("by_sector"):
        lines.append(f"By Sector     : {_top(alloc['by_sector'])}")
    if alloc.get("by_exposure"):
        lines.append(f"Fixed Income  : {_top(alloc['by_exposure'])}")
    if alloc.get("by_region"):
        lines.append(f"By Region     : {_top(alloc['by_region'])}")

    context = "\n".join(lines)
    prompt  = (
        f"{context}\n\n"
        "Analyze this portfolio allocation in English. Under 150 words.\n"
        "Cover: 1) Concentration / diversification 2) Key risks from the allocation 3) Short actionable suggestion"
    )

    print("[ai/recommender] Calling Groq for allocation insight...")
    response = _groq().chat.completions.create(
        model=AI_CFG["model"],
        messages=[
            {"role": "system", "content": SYSTEM_BASE},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=AI_CFG.get("max_tokens", 500),
    )
    return response.choices[0].message.content


# ─── Optimizer Advice ─────────────────────────────────────────────────────────

def get_optimizer_advice(optimizer_results: dict) -> str:
    """
    อธิบาย optimizer results และแนะนำ model + action
    """
    lines = ["=== Optimizer Results ==="]
    for name, r in optimizer_results.items():
        if "error" in r:
            lines.append(f"[{name}] Error")
            continue
        top_w = sorted(r.get("weights", {}).items(), key=lambda x: -x[1])[:3]
        top_str = ", ".join(f"{s}={w:.1f}%" for s, w in top_w)
        lines.append(
            f"[{name}] Ret={r.get('expected_return_pct', 0):+.1f}%"
            f" Vol={r.get('expected_volatility_pct', 0):.1f}%"
            f" Sharpe={r.get('sharpe_ratio', 0):.2f}"
            f" | Top: {top_str}"
        )

    # top rebalance moves จาก best sharpe model
    best = max(
        ((n, r) for n, r in optimizer_results.items() if "error" not in r),
        key=lambda x: x[1].get("sharpe_ratio", 0),
        default=(None, {}),
    )
    if best[0]:
        moves = sorted(
            best[1].get("rebalance_plan", []),
            key=lambda x: abs(x["diff_pct"]),
            reverse=True,
        )[:4]
        if moves:
            lines.append(f"\nTop moves ({best[0]}):")
            for m in moves:
                lines.append(f"  {m['symbol']} {m['action']} {m['diff_pct']:+.1f}%")

    context = "\n".join(lines)
    prompt  = (
        f"{context}\n\n"
        "Analyze these optimizer results in English. Under 180 words.\n"
        "Cover: 1) Which model suits which investor style "
        "2) Which model to pick and why 3) Top 3 rebalance actions to take first"
    )

    print("[ai/recommender] Calling Groq for optimizer advice...")
    response = _groq().chat.completions.create(
        model=AI_CFG["model"],
        messages=[
            {"role": "system", "content": SYSTEM_BASE},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=AI_CFG.get("max_tokens", 500),
    )
    return response.choices[0].message.content


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
