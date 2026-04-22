from __future__ import annotations

from typing import Any

from .config import Settings


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


def symbol_quant_row(quant_snapshot: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    """Per-symbol quant metrics from the current cycle snapshot (if present)."""
    return _metrics_map(quant_snapshot).get(ticker.upper())


def _effective_execution_floor(
    *,
    side: str,
    regime: str,
    regime_block: dict[str, Any],
    met: dict[str, Any] | None,
    learning_feedback: dict[str, Any],
    settings: Settings,
) -> float:
    """
    Dynamic minimum confidence: base from settings, raised in difficult regimes and
    when portfolio-wide learning shows negative average outcomes (de-risk).
    """
    floor = float(settings.min_confidence_execute)
    med_raw = regime_block.get("median_vol_10d")
    try:
        med_vol = float(med_raw) if med_raw is not None else None
    except (TypeError, ValueError):
        med_vol = None

    if regime == "bearish" and side == "buy":
        floor = max(floor, 0.75)
    elif regime == "choppy" and med_vol is not None and med_vol > 0.025:
        # Elevated cross-sectional vol: require more conviction (documented edge in selective trading).
        floor = max(floor, settings.min_confidence_execute + 0.05)
    if side == "buy" and met is not None and regime in {"choppy", "bearish", "unknown"}:
        v10 = float(met.get("vol_10d") or 0.0)
        if v10 > 0.05:
            floor = max(floor, settings.min_confidence_execute + 0.07)

    g = learning_feedback.get("global") or {}
    n_res = int(g.get("resolved_actions") or 0)
    avg_g = g.get("avg_return_pct")
    if (
        n_res >= settings.learning_derisk_min_resolved
        and avg_g is not None
        and float(avg_g) < float(settings.learning_derisk_avg_below)
    ):
        floor = min(0.82, floor + float(settings.learning_derisk_floor_add))

    return min(floor, 0.85)


def evaluate_action_guardrails(
    *,
    action: dict[str, Any],
    learning_feedback: dict[str, Any],
    quant_snapshot: dict[str, Any],
    min_samples: int,
    settings: Settings,
    min_avg_volume_10d: float = 500000.0,
) -> tuple[bool, str]:
    side = str(action.get("side") or "hold").lower()
    ticker = str(action.get("ticker") or "").upper()
    if side == "hold" or not ticker:
        return True, "hold action"

    conf = float(action.get("confidence_0_to_1") or 0.0)
    regime_block = quant_snapshot.get("market_regime") or {}
    regime = (regime_block.get("regime") or "unknown").lower()
    pri = _priors_map(learning_feedback).get(ticker)
    met = _metrics_map(quant_snapshot).get(ticker)

    eff_floor = _effective_execution_floor(
        side=side,
        regime=regime,
        regime_block=regime_block if isinstance(regime_block, dict) else {},
        met=met,
        learning_feedback=learning_feedback,
        settings=settings,
    )
    if conf < eff_floor:
        return False, f"confidence {conf:.2f} below execution floor {eff_floor:.2f}"

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
        if pri:
            samples = int(pri.get("samples") or 0)
            avg = float(pri.get("avg_return_pct") or 0.0)
            # Slightly stricter than before: block chronic losers earlier.
            if samples >= min_samples and avg < -0.004:
                return False, (
                    f"historical prior weak (samples={samples}, avg_return={avg:.2%})"
                )
            if samples >= min_samples * 2 and avg < -0.002:
                return False, (
                    f"historical prior negative (samples={samples}, avg_return={avg:.2%})"
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

