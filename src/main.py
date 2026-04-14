from __future__ import annotations

import json
from typing import Any

from .ai_advisor import propose_actions
from .config import Settings, load_settings, validate_order_execution_allowed
from .context import TradingContext, gather_trading_context
from .decision_engine import evaluate_action_guardrails
from .learning import record_cycle_and_actions
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

    actions = plan.get("actions") or []
    submitted = 0
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
            )
            if not g_ok:
                lines.append(f"GUARDRAIL BLOCK {ticker}: {g_reason}")
                continue
            n = act.get("notional_usd")
            if n is None:
                lines.append(f"Skip BUY {ticker}: need notional_usd.")
                continue
            notional = float(n)
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
            broker.market_buy_notional(ticker, notional)
            bump_orders_placed(1)
            submitted += 1
            acct = broker.account()

        elif side == "sell":
            g_ok, g_reason = evaluate_action_guardrails(
                action=act,
                learning_feedback=ctx.user_payload.get("learning_feedback") or {},
                quant_snapshot=ctx.user_payload.get("quant_snapshot") or {},
                min_samples=s.learning_min_samples,
            )
            if not g_ok:
                lines.append(f"GUARDRAIL BLOCK {ticker}: {g_reason}")
                continue
            sq = _sell_qty_for_action(act, pmap.get(ticker))
            if sq is None or sq <= 0:
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
            broker.market_sell_qty(ticker, sq)
            bump_orders_placed(1)
            submitted += 1
            positions = broker.positions()
            pmap = position_map(positions)

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
