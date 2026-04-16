from __future__ import annotations

from typing import Any


def _priors_map(learning_feedback: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in learning_feedback.get("symbol_priors") or []:
        t = str(row.get("ticker") or "").upper()
        if t:
            out[t] = row
    return out


def _metrics_map(quant_snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in quant_snapshot.get("symbol_metrics") or []:
        t = str(row.get("ticker") or "").upper()
        if t:
            out[t] = row
    return out


def evaluate_action_guardrails(
    *,
    action: dict[str, Any],
    learning_feedback: dict[str, Any],
    quant_snapshot: dict[str, Any],
    min_samples: int,
    min_avg_volume_10d: float = 500000.0,
) -> tuple[bool, str]:
    side = str(action.get("side") or "hold").lower()
    ticker = str(action.get("ticker") or "").upper()
    if side == "hold" or not ticker:
        return True, "hold action"

    conf = float(action.get("confidence_0_to_1") or 0.0)
    regime = ((quant_snapshot.get("market_regime") or {}).get("regime") or "unknown").lower()
    pri = _priors_map(learning_feedback).get(ticker)
    met = _metrics_map(quant_snapshot).get(ticker)

    # Global confidence floor to reduce noisy trades.
    if conf < 0.55:
        return False, f"confidence {conf:.2f} below execution floor 0.55"

    if side == "buy":
        if met:
            mom5 = float(met.get("mom_5d") or 0.0)
            vol10 = float(met.get("vol_10d") or 0.0)
            avg_vol = float(met.get("avg_volume_10d") or 0.0)
            if mom5 < -0.01:
                return False, f"negative 5D momentum ({mom5:.2%})"
            if vol10 > 0.07:
                return False, f"volatility too high ({vol10:.2%})"
            if avg_vol < min_avg_volume_10d:
                return False, f"liquidity too low (avg_volume_10d={avg_vol:,.0f})"
            if regime == "bearish" and conf < 0.75:
                return False, f"bearish regime requires >=0.75 confidence (got {conf:.2f})"
        if pri:
            samples = int(pri.get("samples") or 0)
            avg = float(pri.get("avg_return_pct") or 0.0)
            if samples >= min_samples and avg < -0.005:
                return False, (
                    f"historical prior weak (samples={samples}, avg_return={avg:.2%})"
                )
    return True, "passes quant/learning guardrails"


def regime_notional_multiplier(
    quant_snapshot: dict[str, Any],
    *,
    bullish: float,
    choppy: float,
    bearish: float,
) -> float:
    regime = ((quant_snapshot.get("market_regime") or {}).get("regime") or "unknown").lower()
    if regime == "bullish":
        return bullish
    if regime == "bearish":
        return bearish
    return choppy

