"""
optimizer.py — Portfolio optimization models

Models:
  equal_weight     → 1/N
  min_volatility   → minimize portfolio variance
  max_sharpe       → maximize Sharpe ratio
  risk_parity      → equal risk contribution
  hrp              → Hierarchical Risk Parity (Lopez de Prado)

Public functions:
  run_all_models(days)        → results ของทุก model
  run_model(model_name, days) → results ของ model เดียว
  check_rebalance()           → เช็คว่าพอร์ตต้อง rebalance ไหม
"""

import os
import sys
import yaml
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR   = os.path.dirname(ENGINE_DIR)
sys.path.insert(0, ENGINE_DIR)

from portfolio.holdings import SessionLocal, Holding, get_current_weights
from data.price_feed import get_price_history, get_prices

with open(os.path.join(ROOT_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

RISK_FREE_RATE  = config["optimizer"]["risk_free_rate"]
LOOKBACK_DAYS   = config["optimizer"]["lookback_days"]
THRESHOLD       = config["optimizer"]["rebalance_threshold"]
MODELS          = config["optimizer"]["models"]


# ─── Data Preparation ────────────────────────────────────────────────────────

def _get_returns(symbols: list[str], days: int) -> pd.DataFrame:
    """
    Returns DataFrame ของ daily returns
    index = date, columns = symbol
    """
    frames: dict[str, pd.Series] = {}
    for sym in symbols:
        hist = get_price_history(sym, days=days)
        if hist:
            frames[sym] = pd.Series(hist)

    if not frames:
        return pd.DataFrame()

    df = pd.DataFrame(frames)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill().dropna()
    return df.pct_change().dropna()


def _portfolio_stats(weights: np.ndarray, returns: pd.DataFrame) -> tuple[float, float, float]:
    """(annual_return, annual_vol, sharpe)"""
    rf_daily   = (1 + RISK_FREE_RATE) ** (1 / 252) - 1
    mean_ret   = returns.mean()
    cov        = returns.cov()
    port_ret   = float(weights @ mean_ret) * 252
    port_vol   = float(np.sqrt(weights @ cov @ weights) * np.sqrt(252))
    sharpe     = (port_ret - RISK_FREE_RATE) / port_vol if port_vol > 0 else 0.0
    return round(port_ret * 100, 2), round(port_vol * 100, 2), round(sharpe, 3)


def _weights_to_dict(symbols: list[str], weights: np.ndarray) -> dict[str, float]:
    return {sym: round(float(w) * 100, 2) for sym, w in zip(symbols, weights)}


# ─── Optimization Models ─────────────────────────────────────────────────────

def _equal_weight(symbols: list[str], **_) -> np.ndarray:
    n = len(symbols)
    return np.ones(n) / n


def _min_volatility(symbols: list[str], returns: pd.DataFrame, **_) -> np.ndarray:
    n   = len(symbols)
    cov = returns.cov().values
    w0  = np.ones(n) / n

    result = minimize(
        lambda w: w @ cov @ w,
        w0,
        method="SLSQP",
        bounds=[(0, 1)] * n,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
        options={"ftol": 1e-9, "maxiter": 1000},
    )
    w = result.x
    w = np.clip(w, 0, 1)
    return w / w.sum()


def _max_sharpe(symbols: list[str], returns: pd.DataFrame, **_) -> np.ndarray:
    n        = len(symbols)
    cov      = returns.cov().values
    mean_ret = returns.mean().values
    rf_daily = (1 + RISK_FREE_RATE) ** (1 / 252) - 1
    w0       = np.ones(n) / n

    def neg_sharpe(w):
        port_ret = float(w @ mean_ret)
        port_vol = float(np.sqrt(w @ cov @ w))
        if port_vol < 1e-10:
            return 0.0
        return -(port_ret - rf_daily) / port_vol

    result = minimize(
        neg_sharpe,
        w0,
        method="SLSQP",
        bounds=[(0, 1)] * n,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
        options={"ftol": 1e-9, "maxiter": 1000},
    )
    w = result.x
    w = np.clip(w, 0, 1)
    return w / w.sum()


def _risk_parity(symbols: list[str], returns: pd.DataFrame, **_) -> np.ndarray:
    n   = len(symbols)
    cov = returns.cov().values
    w0  = np.ones(n) / n

    def risk_contrib_obj(w):
        port_var = float(w @ cov @ w)
        if port_var < 1e-10:
            return 0.0
        rc     = w * (cov @ w) / port_var     # risk contribution ของแต่ละ asset
        target = np.ones(n) / n                # เป้าหมาย: equal contribution
        return float(np.sum((rc - target) ** 2))

    result = minimize(
        risk_contrib_obj,
        w0,
        method="SLSQP",
        bounds=[(0.001, 1)] * n,   # lower bound เล็กน้อยเพื่อ numerical stability
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
        options={"ftol": 1e-10, "maxiter": 2000},
    )
    w = result.x
    w = np.clip(w, 0, 1)
    return w / w.sum()


def _hrp(symbols: list[str], returns: pd.DataFrame, **_) -> np.ndarray:
    """Hierarchical Risk Parity (Lopez de Prado 2016)"""
    cov  = returns.cov()
    corr = returns.corr()

    # Distance matrix จาก correlation
    dist_matrix = np.sqrt((1 - corr.values) / 2)
    np.fill_diagonal(dist_matrix, 0)
    dist_condensed = squareform(dist_matrix)

    # Hierarchical clustering (single linkage)
    link = linkage(dist_condensed, method="single")

    # Quasi-diagonalization: sort indices ตาม cluster
    sorted_idx = _quasi_diag(link, len(symbols))
    sorted_syms = [symbols[i] for i in sorted_idx]

    # Recursive bisection
    weights_dict = _recursive_bisect(cov, sorted_syms)

    return np.array([weights_dict[s] for s in symbols])


def _quasi_diag(link: np.ndarray, n: int) -> list[int]:
    """Sort indices ตาม hierarchical clustering result"""
    link = link.astype(int)
    sort_ix = [link[-1, 0], link[-1, 1]]
    num_items = link[-1, 3]

    while max(sort_ix) >= n:
        new_sort = []
        for item in sort_ix:
            if item >= n:
                row = item - n
                new_sort += [link[row, 0], link[row, 1]]
            else:
                new_sort.append(item)
        sort_ix = new_sort

    return sort_ix


def _recursive_bisect(cov: pd.DataFrame, sorted_syms: list[str]) -> dict[str, float]:
    """Assign weights ด้วย inverse-variance recursive bisection"""
    weights = {s: 1.0 for s in sorted_syms}

    def _bisect(syms: list[str]):
        if len(syms) <= 1:
            return
        mid   = len(syms) // 2
        left  = syms[:mid]
        right = syms[mid:]

        # Variance ของแต่ละ cluster
        var_left  = _cluster_var(cov, left)
        var_right = _cluster_var(cov, right)

        alpha = 1 - var_left / (var_left + var_right)

        for s in left:
            weights[s] *= alpha
        for s in right:
            weights[s] *= 1 - alpha

        _bisect(left)
        _bisect(right)

    _bisect(sorted_syms)
    total = sum(weights.values())
    return {s: w / total for s, w in weights.items()}


def _cluster_var(cov: pd.DataFrame, syms: list[str]) -> float:
    """Variance ของ cluster ที่ใช้ inverse-variance weights"""
    sub_cov = cov.loc[syms, syms].values
    if len(syms) == 1:
        return float(sub_cov[0, 0])
    iv    = 1 / np.diag(sub_cov)
    w     = iv / iv.sum()
    return float(w @ sub_cov @ w)


# ─── Rebalance Plan ──────────────────────────────────────────────────────────

def _build_rebalance_plan(
    symbols: list[str],
    target_weights: dict[str, float],
    current_prices: dict[str, float],
) -> list[dict]:
    """
    สร้าง rebalance plan เทียบ current weights vs target weights
    """
    current_weights = get_current_weights(current_prices)   # % จาก holdings.py
    plan = []

    for sym in symbols:
        target  = target_weights.get(sym, 0.0)
        current = current_weights.get(sym, 0.0)
        diff    = target - current

        plan.append({
            "symbol":      sym,
            "current_pct": round(current, 2),
            "target_pct":  round(target, 2),
            "diff_pct":    round(diff, 2),
            "action":      "BUY" if diff > 0 else ("SELL" if diff < 0 else "HOLD"),
        })

    return sorted(plan, key=lambda x: abs(x["diff_pct"]), reverse=True)


# ─── Public Functions ─────────────────────────────────────────────────────────

_MODEL_FN = {
    "equal_weight":   _equal_weight,
    "min_volatility": _min_volatility,
    "max_sharpe":     _max_sharpe,
    "risk_parity":    _risk_parity,
    "hrp":            _hrp,
}


def run_model(model_name: str, days: int = LOOKBACK_DAYS) -> dict:
    """
    รัน optimization model เดียว

    Returns:
      model, weights (%), expected_return, expected_volatility,
      sharpe_ratio, rebalance_plan
    """
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    if not holdings:
        return {}

    symbols = list({h.symbol for h in holdings})
    returns = _get_returns(symbols, days=days)

    if returns.empty or len(returns) < 30:
        return {}

    # กรอง symbols ที่มีข้อมูลครบ
    symbols = [s for s in symbols if s in returns.columns]

    fn      = _MODEL_FN.get(model_name, _equal_weight)
    weights = fn(symbols=symbols, returns=returns)

    exp_ret, exp_vol, sharpe = _portfolio_stats(weights, returns[symbols])
    weight_dict = _weights_to_dict(symbols, weights)

    current_prices = get_prices(symbols)
    rebalance      = _build_rebalance_plan(symbols, weight_dict, current_prices)

    return {
        "model":                model_name,
        "weights":              weight_dict,
        "expected_return_pct":  exp_ret,
        "expected_volatility_pct": exp_vol,
        "sharpe_ratio":         sharpe,
        "lookback_days":        days,
        "rebalance_plan":       rebalance,
    }


def run_all_models(days: int = LOOKBACK_DAYS) -> dict[str, dict]:
    """
    รันทุก model ใน config แล้วคืน dict {model_name: result}
    """
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    if not holdings:
        return {}

    symbols = list({h.symbol for h in holdings})
    returns = _get_returns(symbols, days=days)

    if returns.empty or len(returns) < 30:
        return {}

    symbols        = [s for s in symbols if s in returns.columns]
    current_prices = get_prices(symbols)
    results        = {}

    for model_name in MODELS:
        print(f"[optimizer] Running {model_name}...")
        try:
            fn      = _MODEL_FN.get(model_name, _equal_weight)
            weights = fn(symbols=symbols, returns=returns)

            exp_ret, exp_vol, sharpe = _portfolio_stats(weights, returns[symbols])
            weight_dict = _weights_to_dict(symbols, weights)

            results[model_name] = {
                "model":                    model_name,
                "weights":                  weight_dict,
                "expected_return_pct":      exp_ret,
                "expected_volatility_pct":  exp_vol,
                "sharpe_ratio":             sharpe,
                "lookback_days":            days,
                "rebalance_plan":           _build_rebalance_plan(
                    symbols, weight_dict, current_prices
                ),
            }
        except Exception as e:
            print(f"[optimizer] {model_name} failed: {e}")
            results[model_name] = {"model": model_name, "error": str(e)}

    return results


def check_rebalance(threshold: float = THRESHOLD) -> dict:
    """
    เช็คว่าพอร์ตต้อง rebalance ไหม
    Returns drift ของแต่ละ asset เทียบกับ equal weight
    threshold: % drift ที่ถือว่าต้องทำ (default 10%)
    """
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
    finally:
        db.close()

    if not holdings:
        return {}

    symbols        = [h.symbol for h in holdings]
    current_prices = get_prices(symbols)
    current_weights = get_current_weights(current_prices)
    target          = 100.0 / len(symbols)   # equal weight เป็น baseline

    drifts = {
        sym: round(abs(current_weights.get(sym, 0) - target), 2)
        for sym in symbols
    }
    needs_rebalance = any(d > threshold * 100 for d in drifts.values())

    return {
        "needs_rebalance":  needs_rebalance,
        "threshold_pct":    threshold * 100,
        "current_weights":  {k: round(v, 2) for k, v in current_weights.items()},
        "drift":            drifts,
    }


# ─── CLI test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from portfolio.holdings import init_db
    init_db()

    print("=== Running All Optimizer Models ===\n")
    results = run_all_models(days=365)

    for model, r in results.items():
        if "error" in r:
            print(f"[{model}] ERROR: {r['error']}")
            continue
        print(f"[{model}]")
        print(f"  Expected Return : {r['expected_return_pct']:+.2f}%")
        print(f"  Expected Vol    : {r['expected_volatility_pct']:.2f}%")
        print(f"  Sharpe Ratio    : {r['sharpe_ratio']:.3f}")
        print(f"  Weights:")
        for sym, w in sorted(r["weights"].items(), key=lambda x: -x[1]):
            print(f"    {sym:10s} {w:.2f}%")
        print()

    print("=== Rebalance Check ===")
    rb = check_rebalance()
    if rb:
        status = "YES" if rb["needs_rebalance"] else "NO"
        print(f"  Needs rebalance: {status}")
        for sym, drift in rb["drift"].items():
            print(f"  {sym:10s} drift {drift:.2f}%")
