from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .ai_advisor import propose_actions
from .config import Settings, load_settings, validate_order_execution_allowed
from .context import TradingContext, gather_trading_context
from .decision_engine import evaluate_action_guardrails, regime_notional_multiplier
from .learning import record_cycle_and_actions
from .position_state import load_position_state, save_position_state, sync_position_state
from .reporting import write_daily_postmortem
from .risk import position_map, validate_buy, validate_sell
from .state import bump_orders_placed


def _print(msg: str) -> None:
    print(msg, flush=True)


def _sell_qty_for_action(
    act: dict[str, Any], pos: dict[str, Any] | None
) -> float | None:
    if pos is None:
        return None
    avail = float(pos.get("qty_available") or 0.0)
    if avail <= 0:
        return None
    q = act.get("qty")
    if q is not None and float(q) > 0:
        return min(float(q), avail)
    n = act.get("notional_usd")
    px = float(pos.get("current_price_usd") or 0.0)
    if n is not None and px > 0:
        return min(avail, float(n) / px)
    return avail


def propose_plan(ctx: TradingContext) -> dict[str, Any]:
    s = ctx.settings
    plan = propose_actions(
        api_key=s.openai_api_key,
        model=s.openai_model,
        user_payload=ctx.user_payload,
    )
    record_cycle_and_actions(
        payload=ctx.user_payload,
        plan=plan,
        model=s.openai_model,
    )
    return plan


def _sector_exposure_after_buy(
    *,
    ticker: str,
    buy_notional: float,
    pmap: dict[str, dict[str, Any]],
    symbol_metadata: dict[str, dict[str, Any]],
) -> tuple[str, float]:
    sector = (symbol_metadata.get(ticker) or {}).get("sector", "Unknown")
    current = 0.0
    for sym, pos in pmap.items():
        s = (symbol_metadata.get(sym) or {}).get("sector", "Unknown")
        if s == sector:
            current += float(pos.get("market_value_usd") or 0.0)
    return sector, current + buy_notional


def _days_since_iso(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(ts)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - d).total_seconds() / 86400.0


def _run_hard_exits(ctx: TradingContext, lines: list[str]) -> int:
    s = ctx.settings
    if not s.hard_exits_enabled:
        return 0
    state = sync_position_state(
        positions=ctx.positions,
        symbol_metadata=ctx.user_payload.get("symbol_metadata") or {},
    )
    sold = 0
    for pos in ctx.positions:
        sym = str(pos.get("symbol") or "").upper()
        if not sym:
            continue
        qty = float(pos.get("qty_available") or 0.0)
        if qty <= 0 or qty < 1e-6:
            continue
        entry = float(pos.get("avg_entry_price") or 0.0)
        px = float(pos.get("current_price_usd") or 0.0)
        if entry <= 0 or px <= 0:
            continue
        st = state.get(sym) or {}
        high = float(st.get("high_watermark") or px)
        opened_days = _days_since_iso(st.get("opened_at"))

        reason: str | None = None
        if px <= entry * (1.0 - s.stop_loss_pct):
            reason = f"stop-loss ({(px/entry-1):.2%})"
        elif px >= entry * (1.0 + s.take_profit_pct):
            reason = f"take-profit ({(px/entry-1):.2%})"
        elif high >= entry * (1.0 + s.trailing_activation_pct) and px <= high * (
            1.0 - s.trailing_stop_pct
        ):
            reason = "trailing-stop"
        elif opened_days is not None and opened_days >= s.max_hold_days:
            reason = f"max-hold-days ({opened_days:.1f}d)"

        if reason:
            lines.append(f"HARD EXIT SELL {sym} qty={qty:.6f} reason={reason}")
            try:
                ctx.broker.market_sell_qty(sym, qty)
                bump_orders_placed(1)
                sold += 1
                if sym in state:
                    state.pop(sym, None)
            except Exception as e:
                lines.append(f"HARD EXIT FAILED {sym}: {e}")
    save_position_state(state)
    return sold


def execute_plan(ctx: TradingContext, plan: dict[str, Any]) -> list[str]:
    """Submit orders per plan. Returns log lines."""
    lines: list[str] = []
    s = ctx.settings
    uni_set = set(ctx.universe)
    broker = ctx.broker
    acct = ctx.account
    pmap = ctx.pmap
    st = ctx.daily_state
    positions = ctx.positions

    exec_errors = validate_order_execution_allowed(s)
    if exec_errors:
        for line in exec_errors:
            lines.append(line)
        lines.append("Dry run only (no orders submitted).")
        return lines

    if not s.execute_trades:
        lines.append("EXECUTE_TRADES=false — proposal only, no orders submitted.")
        return lines

    if st.orders_placed >= s.max_orders_per_day:
        lines.append("MAX_ORDERS_PER_DAY reached — not submitting.")
        return lines

    hard_exit_sells = _run_hard_exits(ctx, lines)
    if hard_exit_sells:
        lines.append(f"Hard exits executed: {hard_exit_sells}")
        # Refresh account and positions after forced sells.
        acct = broker.account()
        positions = broker.positions()
        pmap = position_map(positions)

    actions = plan.get("actions") or []
    submitted = 0
    regime_mult = regime_notional_multiplier(
        ctx.user_payload.get("quant_snapshot") or {},
        bullish=s.regime_mult_bullish,
        choppy=s.regime_mult_choppy,
        bearish=s.regime_mult_bearish,
    )
    for act in actions:
        side = (act.get("side") or "hold").lower()
        ticker = (act.get("ticker") or "").upper()
        if side == "hold" or not ticker:
            continue

        if side == "buy":
            g_ok, g_reason = evaluate_action_guardrails(
                action=act,
                learning_feedback=ctx.user_payload.get("learning_feedback") or {},
                quant_snapshot=ctx.user_payload.get("quant_snapshot") or {},
                min_samples=s.learning_min_samples,
                min_avg_volume_10d=s.min_avg_volume_10d,
            )
            if not g_ok:
                lines.append(f"GUARDRAIL BLOCK {ticker}: {g_reason}")
                continue
            n = act.get("notional_usd")
            if n is None:
                lines.append(f"Skip BUY {ticker}: need notional_usd.")
                continue
            notional = float(n) * regime_mult
            if notional < 20:
                lines.append(f"BLOCK BUY {ticker}: regime-sized notional too small (${notional:.2f})")
                continue
            sector, sector_after = _sector_exposure_after_buy(
                ticker=ticker,
                buy_notional=notional,
                pmap=pmap,
                symbol_metadata=ctx.user_payload.get("symbol_metadata") or {},
            )
            if acct.equity_usd > 0 and sector_after > acct.equity_usd * s.max_sector_exposure_pct:
                lines.append(
                    f"BLOCK BUY {ticker}: sector {sector} exposure would be "
                    f"{(sector_after/acct.equity_usd):.1%} > {s.max_sector_exposure_pct:.1%}"
                )
                continue
            cur_mv = float(pmap.get(ticker, {}).get("market_value_usd") or 0.0)
            d = validate_buy(
                ticker=ticker,
                universe=uni_set,
                notional=notional,
                max_order_notional=s.max_order_notional_usd,
                current_position_value=cur_mv,
                max_position_notional=s.max_position_notional_usd,
                buying_power=acct.buying_power_usd,
            )
            if not d.ok:
                lines.append(f"BLOCK BUY {ticker}: {d.reason}")
                continue
            lines.append(f"SUBMIT BUY {ticker} notional=${notional:.2f}")
            try:
                broker.market_buy_notional(ticker, notional)
                bump_orders_placed(1)
                submitted += 1
                acct = broker.account()
            except Exception as e:
                lines.append(f"BUY FAILED {ticker}: {e}")

        elif side == "sell":
            g_ok, g_reason = evaluate_action_guardrails(
                action=act,
                learning_feedback=ctx.user_payload.get("learning_feedback") or {},
                quant_snapshot=ctx.user_payload.get("quant_snapshot") or {},
                min_samples=s.learning_min_samples,
                min_avg_volume_10d=s.min_avg_volume_10d,
            )
            if not g_ok:
                lines.append(f"GUARDRAIL BLOCK {ticker}: {g_reason}")
                continue
            sq = _sell_qty_for_action(act, pmap.get(ticker))
            if sq is None or sq <= 0 or sq < 1e-6:
                lines.append(f"Skip SELL {ticker}: no position / size.")
                continue
            d = validate_sell(
                ticker=ticker,
                universe=uni_set,
                qty=sq,
                available_qty=float(pmap[ticker]["qty_available"]),
            )
            if not d.ok:
                lines.append(f"BLOCK SELL {ticker}: {d.reason}")
                continue
            lines.append(f"SUBMIT SELL {ticker} qty={sq:.6f}")
            try:
                broker.market_sell_qty(ticker, sq)
                bump_orders_placed(1)
                submitted += 1
                positions = broker.positions()
                pmap = position_map(positions)
            except Exception as e:
                lines.append(f"SELL FAILED {ticker}: {e}")

        else:
            lines.append(f"Unknown side {side!r} for {ticker}, skip.")

    lines.append(f"Done. Orders submitted this run: {submitted}")
    return lines


def _max_confidence(plan: dict[str, Any]) -> float:
    vals: list[float] = []
    for a in plan.get("actions") or []:
        v = a.get("confidence_0_to_1")
        try:
            if v is not None:
                vals.append(float(v))
        except (TypeError, ValueError):
            continue
    return max(vals) if vals else 0.0


def run_cycle(settings: Settings | None = None) -> dict[str, Any]:
    s = settings or load_settings()
    if not s.alpaca_api_key or not s.alpaca_secret_key:
        return {"ok": False, "exit_code": 1, "error": "Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env."}
    if not s.openai_api_key:
        return {"ok": False, "exit_code": 1, "error": "Set OPENAI_API_KEY in .env."}

    ctx, err = gather_trading_context(s)
    if err:
        return {"ok": False, "exit_code": 1, "error": err}
    assert ctx is not None

    warnings: list[str] = []
    if ctx.bars_warning:
        warnings.append(f"Market data warning (continuing with less context): {ctx.bars_warning}")
    if ctx.news_warning:
        warnings.append(f"News warning (continuing without news): {ctx.news_warning}")
    if ctx.learning_update:
        warnings.append(
            "Learning update: "
            f"{ctx.learning_update.get('resolved', 0)} action(s) resolved, "
            f"{ctx.learning_update.get('pending', 0)} still pending."
        )

    if ctx.blocked_reason:
        return {
            "ok": True,
            "exit_code": 0,
            "warnings": warnings,
            "blocked_reason": ctx.blocked_reason,
            "plan": None,
            "execution_lines": [],
            "max_confidence": 0.0,
        }

    try:
        plan = propose_plan(ctx)
    except Exception as e:
        return {"ok": False, "exit_code": 1, "warnings": warnings, "error": f"Model error: {e}"}

    lines = execute_plan(ctx, plan)
    write_daily_postmortem(execution_lines=lines)
    return {
        "ok": True,
        "exit_code": 0,
        "warnings": warnings,
        "plan": plan,
        "execution_lines": lines,
        "max_confidence": _max_confidence(plan),
        "action_count": len(plan.get("actions") or []),
    }


def run_once() -> int:
    result = run_cycle()
    for line in result.get("warnings") or []:
        _print(line)
    if result.get("error"):
        _print(str(result["error"]))
    if result.get("blocked_reason"):
        _print(str(result["blocked_reason"]))
    plan = result.get("plan")
    if plan:
        _print(json.dumps(plan, indent=2))
    for line in result.get("execution_lines") or []:
        _print(line)
    return int(result.get("exit_code", 1))


def main() -> None:
    raise SystemExit(run_once())


if __name__ == "__main__":
    main()
