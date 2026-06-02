"""Discretionary exit rules (hard exits in main.py are separate)."""

from __future__ import annotations

from typing import Any

from .config import Settings


def unrealized_pct(pos: dict[str, Any]) -> float | None:
    entry = float(pos.get("avg_entry_price") or 0.0)
    px = float(pos.get("current_price_usd") or 0.0)
    if entry <= 0 or px <= 0:
        return None
    return (px - entry) / entry


def discretionary_sell_allowed(
    *,
    pos: dict[str, Any],
    metrics: dict[str, Any] | None,
    settings: Settings,
) -> tuple[bool, str]:
    """
    Block model SELLs in the 'dead zone' (small P/L) where journal data shows
    negative expectancy — let trailing stops and hard exits manage those.
    """
    unreal = unrealized_pct(pos)
    if unreal is None:
        return False, "missing entry/mark price"

    if unreal >= float(settings.sell_take_profit_min_pct):
        return True, f"profit zone ({unreal:.2%})"

    if unreal <= float(settings.sell_stop_min_pct):
        return True, f"loss zone ({unreal:.2%})"

    mom5 = float((metrics or {}).get("mom_5d") or 0.0)
    if mom5 <= float(settings.sell_mom5_break_pct):
        return True, f"momentum broken (mom5={mom5:.2%})"

    dz_lo = float(settings.sell_dead_zone_min_pct)
    dz_hi = float(settings.sell_dead_zone_max_pct)
    if dz_lo < unreal < dz_hi:
        return (
            False,
            f"exit dead zone ({unreal:.2%}) — engine holds; use hard stops/trailing",
        )

    return True, "outside dead zone"
