from __future__ import annotations

from typing import Any

from .config import Settings
from .exit_rules import discretionary_sell_allowed
from .symbol_quality import chronic_losers, evaluate_buy_quality, top_winners


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


def _slice_rows(learning_feedback: dict[str, Any], bucket: str) -> list[dict[str, Any]]:
    return (learning_feedback.get("slice_priors") or {}).get(bucket) or []


def combined_buy_blocklist(
    settings: Settings,
    learning_feedback: dict[str, Any],
) -> set[str]:
    """Manual WEAK_BUY_BLOCKLIST plus auto-blocked chronic losers from learning."""
    out = set(settings.weak_buy_blocklist)
    for row in learning_feedback.get("symbol_priors") or []:
        t = str(row.get("ticker") or "").upper()
        if not t:
            continue
        n = int(row.get("samples") or 0)
        avg = row.get("avg_return_pct")
        wr = row.get("win_rate")
        if (
            n >= settings.auto_blocklist_min_samples
            and avg is not None
            and float(avg) < float(settings.auto_blocklist_avg_below)
        ):
            out.add(t)
        if (
            n >= settings.min_symbol_samples_for_win_filter
            and wr is not None
            and avg is not None
            and float(wr) < float(settings.min_symbol_win_rate)
            and float(avg) <= 0
        ):
            out.add(t)
    out.update(chronic_losers(learning_feedback, min_samples=settings.min_symbol_samples_for_win_filter))
    return out


def _slice_row_by_value(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    for r in rows:
        if str(r.get(key) or "").lower() == value.lower():
            return r
    return None


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
        floor = max(floor, min(0.72, settings.min_confidence_execute + 0.12))
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

    # Auto-tune from recent rolling expectancy (faster adaptation than global average).
    roll = g.get("rolling_20") or {}
    roll_samples = int(roll.get("samples") or 0)
    roll_exp = roll.get("expectancy_pct")
    if roll_samples >= 12 and roll_exp is not None:
        re = float(roll_exp)
        if re < -0.01:
            floor += 0.08
        elif re < -0.005:
            floor += 0.05
        elif re < -0.002:
            floor += 0.03
        elif re > 0.004:
            floor -= 0.015

    return min(floor, 0.85)


def confidence_floor_status(
    *,
    learning_feedback: dict[str, Any],
    quant_snapshot: dict[str, Any],
    settings: Settings,
    side: str = "buy",
) -> dict[str, Any]:
    """
    Explain the current adaptive confidence floor used by guardrails.
    """
    side_l = str(side or "buy").lower()
    regime_block = quant_snapshot.get("market_regime") or {}
    regime = (regime_block.get("regime") or "unknown").lower()
    floor = _effective_execution_floor(
        side=side_l,
        regime=regime,
        regime_block=regime_block if isinstance(regime_block, dict) else {},
        met=None,
        learning_feedback=learning_feedback,
        settings=settings,
    )
    g = learning_feedback.get("global") or {}
    roll = g.get("rolling_20") or {}
    roll_samples = int(roll.get("samples") or 0)
    roll_exp = roll.get("expectancy_pct")
    roll_active = roll_samples >= 12 and roll_exp is not None and float(roll_exp) < -0.002
    return {
        "side": side_l,
        "regime": regime,
        "base_floor": float(settings.min_confidence_execute),
        "effective_floor": float(floor),
        "rolling_derisk_active": bool(roll_active),
        "rolling_expectancy_pct": (float(roll_exp) if roll_exp is not None else None),
        "rolling_samples": roll_samples,
    }


def evaluate_action_guardrails(
    *,
    action: dict[str, Any],
    learning_feedback: dict[str, Any],
    quant_snapshot: dict[str, Any],
    min_samples: int,
    settings: Settings,
    min_avg_volume_10d: float = 500000.0,
    position: dict[str, Any] | None = None,
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

    winners = set(
        top_winners(
            learning_feedback,
            min_samples=settings.min_symbol_samples_for_win_filter,
        )
    )
    eff_floor = _effective_execution_floor(
        side=side,
        regime=regime,
        regime_block=regime_block if isinstance(regime_block, dict) else {},
        met=met,
        learning_feedback=learning_feedback,
        settings=settings,
    )
    if side == "buy" and ticker in winners:
        eff_floor = max(float(settings.min_confidence_execute) - 0.02, eff_floor - 0.03)
    if conf < eff_floor:
        return False, f"confidence {conf:.2f} below execution floor {eff_floor:.2f}"

    if side == "sell" and position is not None:
        ok, reason = discretionary_sell_allowed(
            pos=position, metrics=met, settings=settings
        )
        if not ok:
            return False, reason

    if side == "buy":
        g = learning_feedback.get("global") or {}
        roll = g.get("rolling_20") or {}
        roll_n = int(roll.get("samples") or 0)
        roll_exp = roll.get("expectancy_pct")
        if (
            roll_n >= settings.block_buys_roll_min_samples
            and roll_exp is not None
            and float(roll_exp) < float(settings.block_buys_roll_exp_below)
        ):
            return False, (
                f"rolling expectancy {float(roll_exp):.3%} below "
                f"{settings.block_buys_roll_exp_below:.3%} (samples={roll_n})"
            )
        if settings.bullish_only_buys and regime != "bullish":
            return False, f"buy entries restricted to bullish regime (got {regime})"
        blocked = combined_buy_blocklist(settings, learning_feedback)
        if ticker in blocked:
            return False, f"{ticker} on buy blocklist (manual or learning prior)"
        buy_rows = _slice_rows(learning_feedback, "by_side")
        buy_row = _slice_row_by_value(buy_rows, "side", "buy")
        if buy_row:
            b_n = int(buy_row.get("samples") or 0)
            b_avg = buy_row.get("avg_return_pct")
            if b_n >= max(min_samples * 3, 15) and b_avg is not None and float(b_avg) < -0.003:
                return False, f"buy slice underperforming (samples={b_n}, avg={float(b_avg):.2%})"

    # Slice-level gating (side/regime/horizon) from realized outcomes.
    side_rows = _slice_rows(learning_feedback, "by_side")
    side_row = _slice_row_by_value(side_rows, "side", side)
    if side_row:
        s_n = int(side_row.get("samples") or 0)
        s_avg = side_row.get("avg_return_pct")
        if s_n >= max(min_samples * 2, 10) and s_avg is not None and float(s_avg) < -0.004:
            return False, f"{side} slice weak (samples={s_n}, avg_return={float(s_avg):.2%})"

    reg_rows = _slice_rows(learning_feedback, "by_regime")
    reg_row = _slice_row_by_value(reg_rows, "regime_at_decision", regime)
    if reg_row:
        r_n = int(reg_row.get("samples") or 0)
        r_avg = reg_row.get("avg_return_pct")
        if r_n >= max(min_samples * 2, 10) and r_avg is not None and float(r_avg) < -0.004:
            return False, f"regime slice weak ({regime}, samples={r_n}, avg_return={float(r_avg):.2%})"

    if side == "buy":
        ok, reason = evaluate_buy_quality(
            ticker=ticker,
            action=action,
            metrics=met,
            prior=pri,
            regime=regime,
            settings=settings,
            top_winner_set=winners,
        )
        if not ok:
            return False, reason
        if met:
            vol10 = float(met.get("vol_10d") or 0.0)
            avg_vol = float(met.get("avg_volume_10d") or 0.0)
            if vol10 > 0.07:
                return False, f"volatility too high ({vol10:.2%})"
            if avg_vol < min_avg_volume_10d:
                return False, f"liquidity too low (avg_volume_10d={avg_vol:,.0f})"
        if pri:
            samples = int(pri.get("samples") or 0)
            avg = float(pri.get("avg_return_pct") or 0.0)
            # Slightly stricter than before: block chronic losers earlier.
            if samples >= min_samples and avg < -0.003:
                return False, (
                    f"historical prior weak (samples={samples}, avg_return={avg:.2%})"
                )
            if samples >= max(min_samples - 1, 3) and avg < -0.001:
                return False, (
                    f"historical prior negative (samples={samples}, avg_return={avg:.2%})"
                )
    return True, "passes quant/learning guardrails"


learning_priors_map = _priors_map


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

