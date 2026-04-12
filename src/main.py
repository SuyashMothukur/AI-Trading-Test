from __future__ import annotations

import json
from typing import Any

from .ai_advisor import propose_actions
from .config import load_settings, validate_order_execution_allowed
from .context import TradingContext, gather_trading_context
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
    return propose_actions(
        api_key=s.openai_api_key,
        model=s.openai_model,
        user_payload=ctx.user_payload,
    )


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


def run_once() -> int:
    s = load_settings()
    if not s.alpaca_api_key or not s.alpaca_secret_key:
        _print("Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env.")
        return 1
    if not s.openai_api_key:
        _print("Set OPENAI_API_KEY in .env.")
        return 1

    ctx, err = gather_trading_context(s)
    if err:
        _print(err)
        return 1
    assert ctx is not None

    if ctx.bars_warning:
        _print(f"Market data warning (continuing with less context): {ctx.bars_warning}")

    if ctx.blocked_reason:
        _print(ctx.blocked_reason)
        return 0

    try:
        plan = propose_plan(ctx)
    except Exception as e:
        _print(f"Model error: {e}")
        return 1

    _print(json.dumps(plan, indent=2))

    for line in execute_plan(ctx, plan):
        _print(line)

    return 0


def main() -> None:
    raise SystemExit(run_once())


if __name__ == "__main__":
    main()
