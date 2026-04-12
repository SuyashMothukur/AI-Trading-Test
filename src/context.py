from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .broker_alpaca import AccountView, AlpacaBroker
from .config import Settings, kill_switch_active
from .risk import daily_loss_tripped, position_map
from .state import DailyState, ensure_session_start_equity, utc_now_iso
from .symbols_context import symbols_for_context
from .universe import resolve_universe


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
    blocked_reason: str | None


def gather_trading_context(s: Settings) -> tuple[TradingContext | None, str | None]:
    if kill_switch_active():
        return None, "STOP_TRADING file is present in the project root."

    uni = resolve_universe(s.trade_universe)
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
    ctx_syms = symbols_for_context(uni, pos_syms, s.max_context_symbols)
    bars: dict[str, Any] = {}
    bars_warning: str | None = None
    try:
        bars = broker.recent_daily_bars(ctx_syms, days=14)
    except Exception as e:
        bars_warning = str(e)

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
        "context_symbols": ctx_syms,
        "open_positions": positions,
        "bars_by_symbol": bars,
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
            blocked_reason=blocked,
        ),
        None,
    )
