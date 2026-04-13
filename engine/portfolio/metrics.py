"""
metrics.py — คำนวณ metrics ของพอร์ตและ asset แต่ละตัว

Public functions:
  get_portfolio_metrics(days)     → return, sharpe, drawdown, volatility ของทั้งพอร์ต
  get_asset_metrics(symbol, days) → metrics ของ asset เดียว
  get_benchmark_comparison(days)  → alpha, beta, correlation vs benchmark
"""

import os
import sys
import yaml
import numpy as np
import pandas as pd

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR   = os.path.dirname(ENGINE_DIR)
sys.path.insert(0, ENGINE_DIR)

from portfolio.holdings import SessionLocal, Holding
from data.price_feed import get_price_history, get_price_histories_batch

with open(os.path.join(ENGINE_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

RISK_FREE_RATE = config["optimizer"]["risk_free_rate"]  # annual, e.g. 0.03
BENCHMARK      = config["portfolio"]["benchmark"]        # e.g. "SPY"


# ─── Internal Helpers ────────────────────────────────────────────────────────

def _history_df(symbols: list[str], days: int) -> pd.DataFrame:
    """
    ดึง price history ของทุก symbol แล้วรวมเป็น DataFrame
    ใช้ batch fetch เพื่อลด network calls
    """
    all_hist = get_price_histories_batch(symbols, days=days)

    frames: dict[str, pd.Series] = {
        sym: pd.Series(hist)
        for sym, hist in all_hist.items()
        if hist
    }

    if not frames:
        return pd.DataFrame()

    df = pd.DataFrame(frames)
    df.index = pd.to_datetime(df.index)
    return df.sort_index().ffill()


def _portfolio_value_series(holdings: list, price_df: pd.DataFrame) -> pd.Series:
    """
    คำนวณมูลค่าพอร์ตรายวัน
    portfolio_value(t) = Σ quantity_i × price_i(t)
    """
    value = pd.Series(0.0, index=price_df.index)
    for h in holdings:
        if h.symbol in price_df.columns:
            value = value + h.quantity * price_df[h.symbol]
    return value.dropna()


def _calc_metrics(
    value_series: pd.Series,
    cost_basis: float = 0.0,
    risk_free_rate: float = RISK_FREE_RATE,
) -> dict:
    """
    คำนวณ metrics จาก value series
    value_series : มูลค่ารายวัน (พอร์ต หรือราคา × qty ของ asset เดียว)
    cost_basis   : ต้นทุนรวม (0 → ข้ามส่วน P&L)
    """
    if value_series.empty or len(value_series) < 2:
        return {}

    daily_returns = value_series.pct_change().dropna()
    if daily_returns.empty:
        return {}

    first_val = float(value_series.iloc[0])
    last_val  = float(value_series.iloc[-1])

    # ── Return ──────────────────────────────────────────────────────────────
    total_return = (last_val - first_val) / first_val * 100
    days         = max((value_series.index[-1] - value_series.index[0]).days, 1)
    years        = days / 365
    annualized   = ((1 + total_return / 100) ** (1 / years) - 1) * 100

    # ── Sharpe / Volatility (weekdays only — avoids ffill bias from crypto/stock mix) ──
    trading_returns = daily_returns[daily_returns.index.dayofweek < 5]
    if trading_returns.empty:
        trading_returns = daily_returns  # fallback (crypto-only portfolio)

    rf_daily  = (1 + risk_free_rate) ** (1 / 252) - 1
    std_daily = trading_returns.std()
    sharpe    = float((trading_returns - rf_daily).mean() / std_daily * np.sqrt(252)) if std_daily > 0 else 0.0

    # ── Volatility ───────────────────────────────────────────────────────────
    volatility = float(std_daily * np.sqrt(252) * 100)

    # ── Max Drawdown ─────────────────────────────────────────────────────────
    cumulative   = (1 + daily_returns).cumprod()
    rolling_peak = cumulative.cummax()
    max_drawdown = float(((cumulative - rolling_peak) / rolling_peak).min() * 100)

    result = {
        "total_return_pct":      round(total_return, 2),
        "annualized_return_pct": round(annualized, 2),
        "sharpe_ratio":          round(sharpe, 3),
        "volatility_pct":        round(volatility, 2),
        "max_drawdown_pct":      round(max_drawdown, 2),
        "current_value":         round(last_val, 2),
        "days":                  days,
    }

    # ── P&L ──────────────────────────────────────────────────────────────────
    if cost_basis > 0:
        result["cost_basis"] = round(cost_basis, 2)
        result["pnl"]        = round(last_val - cost_basis, 2)
        result["pnl_pct"]    = round((last_val - cost_basis) / cost_basis * 100, 2)

    return result


def _benchmark_metrics(
    portfolio_returns: pd.Series,
    benchmark: str = BENCHMARK,
    risk_free_rate: float = RISK_FREE_RATE,
) -> dict:
    """
    คำนวณ alpha, beta, correlation เทียบกับ benchmark
    """
    bench_hist = get_price_history(benchmark, days=len(portfolio_returns) + 30)
    if not bench_hist:
        return {}

    bench_series = pd.Series(bench_hist)
    bench_series.index = pd.to_datetime(bench_series.index)
    bench_returns = bench_series.sort_index().pct_change().dropna()

    aligned = pd.concat(
        [portfolio_returns.rename("portfolio"), bench_returns.rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()

    if len(aligned) < 20:
        return {}

    bench_var = aligned["benchmark"].var()
    beta      = float(aligned.cov().loc["portfolio", "benchmark"] / bench_var) if bench_var > 0 else 0.0

    rf_daily  = (1 + risk_free_rate) ** (1 / 252) - 1
    alpha     = (
        aligned["portfolio"].mean() - rf_daily
        - beta * (aligned["benchmark"].mean() - rf_daily)
    ) * 252 * 100

    bench_total = ((1 + aligned["benchmark"]).prod() - 1) * 100

    return {
        "benchmark":            benchmark,
        "alpha_pct":            round(float(alpha), 2),
        "beta":                 round(beta, 3),
        "correlation":          round(float(aligned["portfolio"].corr(aligned["benchmark"])), 3),
        "benchmark_return_pct": round(float(bench_total), 2),
    }


# ─── Public Functions ─────────────────────────────────────────────────────────

def get_portfolio_metrics(days: int = 365) -> dict:
    """
    คำนวณ metrics ของพอร์ตทั้งหมด

    Returns:
      total_return_pct, annualized_return_pct, sharpe_ratio,
      volatility_pct, max_drawdown_pct, current_value,
      cost_basis, pnl, pnl_pct,
      benchmark: { alpha_pct, beta, correlation, benchmark_return_pct }
    """
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    if not holdings:
        return {}

    symbols      = list({h.symbol for h in holdings})
    price_df     = _history_df(symbols, days=days)

    if price_df.empty:
        return {}

    value_series = _portfolio_value_series(holdings, price_df)
    cost_basis   = sum(h.quantity * h.cost for h in holdings)

    metrics = _calc_metrics(value_series, cost_basis=cost_basis)
    if not metrics:
        return {}

    bm = _benchmark_metrics(value_series.pct_change().dropna())
    if bm:
        metrics["benchmark"] = bm
    return metrics


def get_asset_metrics(symbol: str, days: int = 365) -> dict:
    """
    คำนวณ metrics ของ asset เดียว

    Returns:
      total_return_pct, annualized_return_pct, sharpe_ratio,
      volatility_pct, max_drawdown_pct, current_value,
      cost_basis, pnl, pnl_pct (ถ้ามี holding),
      benchmark: { alpha_pct, beta, correlation, benchmark_return_pct }
    """
    hist = get_price_history(symbol, days=days)
    if not hist:
        return {}

    price_series = pd.Series(hist)
    price_series.index = pd.to_datetime(price_series.index)
    price_series = price_series.sort_index().ffill()

    db = SessionLocal()
    try:
        holding = db.query(Holding).filter(Holding.symbol == symbol).first()
    finally:
        db.close()

    if holding:
        value_series = price_series * holding.quantity
        cost_basis   = holding.quantity * holding.cost
    else:
        value_series = price_series
        cost_basis   = 0.0

    metrics = _calc_metrics(value_series, cost_basis=cost_basis)
    if not metrics:
        return {}

    bm = _benchmark_metrics(price_series.pct_change().dropna())
    if bm:
        metrics["benchmark"] = bm
    return metrics


def get_benchmark_comparison(days: int = 365) -> dict:
    """
    เปรียบเทียบพอร์ตกับ benchmark
    Convenience wrapper สำหรับ API endpoint
    """
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    if not holdings:
        return {}

    symbols      = list({h.symbol for h in holdings})
    price_df     = _history_df(symbols, days=days)
    value_series = _portfolio_value_series(holdings, price_df)

    return _benchmark_metrics(value_series.pct_change().dropna())


# ─── CLI test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from portfolio.holdings import init_db
    init_db()

    print("=== Portfolio Metrics (365d) ===")
    m = get_portfolio_metrics(days=365)
    if m:
        print(f"  Current Value    : ${m.get('current_value', 0):>12,.2f}")
        print(f"  Cost Basis       : ${m.get('cost_basis', 0):>12,.2f}")
        print(f"  P&L              : ${m.get('pnl', 0):>+12,.2f}  ({m.get('pnl_pct', 0):+.2f}%)")
        print(f"  Total Return     : {m.get('total_return_pct', 0):+.2f}%")
        print(f"  Annualized Return: {m.get('annualized_return_pct', 0):+.2f}%")
        print(f"  Sharpe Ratio     : {m.get('sharpe_ratio', 0):.3f}")
        print(f"  Volatility       : {m.get('volatility_pct', 0):.2f}%")
        print(f"  Max Drawdown     : {m.get('max_drawdown_pct', 0):.2f}%")
        bm = m.get("benchmark", {})
        if bm:
            print(f"\n  vs {bm['benchmark']}:")
            print(f"    Alpha       : {bm['alpha_pct']:+.2f}%")
            print(f"    Beta        : {bm['beta']:.3f}")
            print(f"    Correlation : {bm['correlation']:.3f}")
            print(f"    Bench Return: {bm['benchmark_return_pct']:+.2f}%")
    else:
        print("  No data — add holdings + run price_feed first")

    print("\n=== SPY Asset Metrics ===")
    a = get_asset_metrics("SPY", days=365)
    if a:
        print(f"  Total Return : {a.get('total_return_pct', 0):+.2f}%")
        print(f"  Sharpe Ratio : {a.get('sharpe_ratio', 0):.3f}")
        print(f"  Max Drawdown : {a.get('max_drawdown_pct', 0):.2f}%")
    else:
        print("  No data — run price_feed first")
