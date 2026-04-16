from __future__ import annotations

import statistics
from typing import Any


def _returns(closes: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        cur = closes[i]
        if prev <= 0:
            continue
        out.append((cur - prev) / prev)
    return out


def _closes_from_bars(bars: list[dict[str, Any]]) -> list[float]:
    vals: list[float] = []
    for b in bars:
        c = b.get("c")
        if c is None:
            continue
        vals.append(float(c))
    return vals


def symbol_metrics(bars_by_symbol: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for sym, bars in bars_by_symbol.items():
        closes = _closes_from_bars(bars)
        if len(closes) < 6:
            continue
        rets = _returns(closes[-11:])  # up to 10 recent returns
        vol10 = statistics.pstdev(rets) if len(rets) >= 2 else 0.0
        mom5 = (closes[-1] / closes[-6]) - 1.0
        mom10 = (closes[-1] / closes[-11]) - 1.0 if len(closes) >= 11 else mom5
        vols = [float(b.get("v") or 0.0) for b in bars[-10:]]
        avg_vol_10d = (sum(vols) / len(vols)) if vols else 0.0
        out[sym.upper()] = {
            "last_close": closes[-1],
            "mom_5d": mom5,
            "mom_10d": mom10,
            "vol_10d": vol10,
            "avg_volume_10d": avg_vol_10d,
        }
    return out


def market_regime(metrics: dict[str, dict[str, float]]) -> dict[str, Any]:
    if not metrics:
        return {
            "regime": "unknown",
            "breadth_up_5d": None,
            "median_vol_10d": None,
            "notes": "Insufficient bar data.",
        }
    moms = [m["mom_5d"] for m in metrics.values()]
    vols = [m["vol_10d"] for m in metrics.values()]
    breadth = sum(1 for m in moms if m > 0) / len(moms)
    med_vol = statistics.median(vols) if vols else 0.0
    if breadth >= 0.58 and med_vol < 0.03:
        reg = "bullish"
    elif breadth <= 0.42:
        reg = "bearish"
    else:
        reg = "choppy"
    return {
        "regime": reg,
        "breadth_up_5d": breadth,
        "median_vol_10d": med_vol,
        "notes": "Derived from context-symbol 5D breadth and 10D volatility.",
    }


def build_quant_snapshot(bars_by_symbol: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    metrics = symbol_metrics(bars_by_symbol)
    reg = market_regime(metrics)
    # Keep payload compact: include top symbols by absolute 5D momentum.
    ranked = sorted(
        (
            {"ticker": t, **m}
            for t, m in metrics.items()
        ),
        key=lambda x: abs(float(x["mom_5d"])),
        reverse=True,
    )[:120]
    return {"market_regime": reg, "symbol_metrics": ranked}

