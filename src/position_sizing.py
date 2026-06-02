"""Risk-based position sizing (fractional Kelly + per-trade risk cap)."""

from __future__ import annotations

from typing import Any

from .config import Settings


def _effective_stop_pct(
    met: dict[str, Any] | None, settings: Settings
) -> float:
    stop = float(settings.stop_loss_pct)
    if not settings.use_atr_stops or not met:
        return max(stop, 0.01)
    atr = float(met.get("atr_10d") or 0.0)
    last = float(met.get("last_close") or 0.0)
    if atr > 0 and last > 0:
        atr_stop = (float(settings.atr_stop_mult) * atr) / last
        stop = min(stop, max(atr_stop, 0.008))
    return max(stop, 0.008)


def adjust_buy_notional(
    base_notional: float,
    *,
    equity_usd: float,
    settings: Settings,
    learning_feedback: dict[str, Any],
    symbol_prior: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
) -> float:
    """Cap size by % equity at risk; scale down in weak rolling periods."""
    base = float(base_notional)
    if base <= 0 or equity_usd <= 0:
        return base

    stop_pct = _effective_stop_pct(metrics, settings)
    risk_budget = equity_usd * float(settings.risk_per_trade_pct)
    max_from_risk = risk_budget / stop_pct
    sized = min(base, max_from_risk, float(settings.max_order_notional_usd))

    mult = 1.0
    if settings.use_fractional_kelly:
        roll = (learning_feedback.get("global") or {}).get("rolling_20") or {}
        exp = roll.get("expectancy_pct")
        wr = roll.get("win_rate")
        samples = int(roll.get("samples") or 0)
        if samples >= 12 and exp is not None:
            e = float(exp)
            if e > 0.003:
                mult = min(1.25, 1.0 + e * 40.0)
            elif e < -0.002:
                mult = 0.55
            elif wr is not None and float(wr) < 0.38:
                mult = 0.7

    if symbol_prior:
        avg = float(symbol_prior.get("avg_return_pct") or 0.0)
        n = int(symbol_prior.get("samples") or 0)
        if n >= 3:
            if avg > 0.004:
                mult *= 1.12
            elif avg < -0.003:
                mult *= 0.55

    if metrics and not metrics.get("trend_aligned"):
        mult *= 0.75

    out = sized * mult
    return max(25.0, min(out, float(settings.max_order_notional_usd)))
