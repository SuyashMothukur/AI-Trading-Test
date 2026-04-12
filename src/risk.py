from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RiskDecision:
    ok: bool
    reason: str


def daily_loss_tripped(
    session_start_equity: float | None, current_equity: float, max_daily_loss_usd: float
) -> bool:
    if session_start_equity is None:
        return False
    return current_equity < session_start_equity - max_daily_loss_usd


def validate_buy(
    *,
    ticker: str,
    universe: set[str],
    notional: float,
    max_order_notional: float,
    current_position_value: float,
    max_position_notional: float,
    buying_power: float,
) -> RiskDecision:
    t = ticker.upper()
    if t not in universe:
        return RiskDecision(False, f"{t} not in approved universe.")
    if notional <= 0:
        return RiskDecision(False, "Buy size must be positive.")
    if notional > max_order_notional:
        return RiskDecision(
            False, f"Order ${notional:.2f} exceeds MAX_ORDER_NOTIONAL_USD."
        )
    if current_position_value + notional > max_position_notional + 1e-6:
        return RiskDecision(
            False,
            f"Would exceed MAX_POSITION_NOTIONAL_USD for {t} "
            f"({current_position_value + notional:.2f} > {max_position_notional}).",
        )
    if notional > buying_power + 1e-6:
        return RiskDecision(False, "Insufficient buying power for this buy.")
    return RiskDecision(True, "ok")


def validate_sell(
    *,
    ticker: str,
    universe: set[str],
    qty: float,
    available_qty: float,
) -> RiskDecision:
    t = ticker.upper()
    if t not in universe:
        return RiskDecision(False, f"{t} not in approved universe.")
    if qty <= 0:
        return RiskDecision(False, "Sell qty must be positive.")
    if qty > available_qty + 1e-8:
        return RiskDecision(
            False,
            f"Sell qty {qty} exceeds available {available_qty} for {t}.",
        )
    return RiskDecision(True, "ok")


def position_map(positions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {p["symbol"].upper(): p for p in positions}
