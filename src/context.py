from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .broker_alpaca import AccountView, AlpacaBroker
from .config import Settings, kill_switch_active
from .learning import build_learning_snapshot, evaluate_pending_actions
from .quant import build_quant_snapshot
from .risk import daily_loss_tripped, position_map
from .state import DailyState, ensure_session_start_equity, utc_now_iso
from .symbols_context import candidate_pool_for_bars, rank_symbols_for_context
from .universe import resolve_universe_with_metadata


@dataclass
class TradingContext:
    settings: Settings
    broker: AlpacaBroker
    universe: list[str]
    account: AccountView
    positions: list[dict[str, Any]]
    pmap: dict[str, dict[str, Any]]
    daily_state: DailyState
    user_payload: dict[str, Any]
    bars_warning: str | None
    news_warning: str | None
    learning_update: dict[str, Any] | None
    blocked_reason: str | None


def gather_trading_context(s: Settings) -> tuple[TradingContext | None, str | None]:
    if kill_switch_active():
        return None, "STOP_TRADING file is present in the project root."

    uni, meta = resolve_universe_with_metadata(s.trade_universe)
    broker = AlpacaBroker(s.alpaca_api_key, s.alpaca_secret_key, paper=s.alpaca_paper)
    acct = broker.account()
    positions = broker.positions()
    pmap = position_map(positions)

    dstate = ensure_session_start_equity(acct.equity_usd)
    blocked: str | None = None
    if daily_loss_tripped(
        dstate.session_start_equity_usd, acct.equity_usd, s.max_daily_loss_usd
    ):
        blocked = (
            "Daily loss limit tripped vs session-start equity — "
            "no new orders until the next session state reset."
        )

    pos_syms = [p["symbol"] for p in positions]
    pool_cap = min(
        len(uni),
        max(s.max_context_symbols * s.context_candidate_multiplier, s.max_context_symbols + 10),
    )
    candidate_syms = candidate_pool_for_bars(uni, pos_syms, pool_cap)

    learning_update: dict[str, Any] | None = None
    learning_snapshot = {"global": {}, "symbol_priors": [], "notes": "Unavailable"}
    try:
        learning_update = evaluate_pending_actions(
            broker=broker,
            eval_delay_hours=s.learning_eval_delay_hours,
        )
        learning_snapshot = build_learning_snapshot(s.learning_min_samples)
    except Exception:
        pass

    bars: dict[str, Any] = {}
    bars_warning: str | None = None
    ctx_syms = candidate_syms[: s.max_context_symbols]
    try:
        bars = broker.recent_daily_bars(candidate_syms, days=14)
        ctx_syms = rank_symbols_for_context(
            candidates=candidate_syms,
            bars_by_symbol=bars,
            learning_feedback=learning_snapshot,
            open_position_symbols=pos_syms,
            limit=s.max_context_symbols,
            weak_buy_blocklist=set(s.weak_buy_blocklist),
            auto_blocklist_min_samples=s.auto_blocklist_min_samples,
            auto_blocklist_avg_below=s.auto_blocklist_avg_below,
        )
    except Exception as e:
        bars_warning = str(e)

    news_warning: str | None = None
    news_items: list[dict[str, Any]] = []
    try:
        news_items = broker.latest_news(
            symbols=ctx_syms[: s.news_context_symbols],
            limit=s.news_headlines_limit,
        )
    except Exception as e:
        news_warning = str(e)

    user_payload = {
        "utc_time": utc_now_iso(),
        "alpaca_paper": s.alpaca_paper,
        "account": {
            "equity_usd": acct.equity_usd,
            "buying_power_usd": acct.buying_power_usd,
            "cash_usd": acct.cash_usd,
        },
        "risk_limits": {
            "max_order_notional_usd": s.max_order_notional_usd,
            "max_position_notional_usd": s.max_position_notional_usd,
            "max_orders_per_day": s.max_orders_per_day,
            "orders_placed_today": dstate.orders_placed,
            "session_start_equity_usd": dstate.session_start_equity_usd,
            "max_daily_loss_usd": s.max_daily_loss_usd,
        },
        "universe_note": (
            "Full tradable list is `full_universe`. "
            "`bars_by_symbol` may only cover `context_symbols` this cycle."
        ),
        "full_universe": uni,
        "symbol_metadata": meta,
        "context_symbols": ctx_syms,
        "open_positions": positions,
        "bars_by_symbol": bars,
        "quant_snapshot": build_quant_snapshot(bars),
        "recent_news": news_items,
        "learning_feedback": learning_snapshot,
        "execution_policy": {
            "min_confidence_execute": s.min_confidence_execute,
            "max_buys_per_cycle": s.max_buys_per_cycle,
            "max_plan_actions": s.max_plan_actions,
            "bullish_only_buys": s.bullish_only_buys,
            "weak_buy_blocklist": sorted(
                set(s.weak_buy_blocklist)
                | {
                    str(r.get("ticker") or "").upper()
                    for r in (learning_snapshot.get("symbol_priors") or [])
                    if int(r.get("samples") or 0) >= s.auto_blocklist_min_samples
                    and r.get("avg_return_pct") is not None
                    and float(r["avg_return_pct"]) < s.auto_blocklist_avg_below
                }
            ),
            "symbol_cooldown_hours": s.symbol_cooldown_hours,
            "min_mom5_for_buy": s.min_mom5_for_buy,
            "min_mom10_for_buy": s.min_mom10_for_buy,
            "require_trend_alignment": s.require_trend_alignment,
            "sell_dead_zone": [s.sell_dead_zone_min_pct, s.sell_dead_zone_max_pct],
            "risk_per_trade_pct": s.risk_per_trade_pct,
        },
    }

    return (
        TradingContext(
            settings=s,
            broker=broker,
            universe=uni,
            account=acct,
            positions=positions,
            pmap=pmap,
            daily_state=dstate,
            user_payload=user_payload,
            bars_warning=bars_warning,
            news_warning=news_warning,
            learning_update=learning_update,
            blocked_reason=blocked,
        ),
        None,
    )
