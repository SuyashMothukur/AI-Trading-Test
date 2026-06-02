"""Normalize and cap model plans before guardrails / execution."""

from __future__ import annotations

from typing import Any

_SIDE_RANK = {"sell": 0, "buy": 1, "hold": 2}


def _act_side(act: dict[str, Any]) -> str:
    return str(act.get("side") or act.get("action") or "hold").lower()


def _conf(act: dict[str, Any]) -> float:
    try:
        v = act.get("confidence_0_to_1")
        if v is None:
            v = act.get("confidence")
        return float(v or 0.0)
    except (TypeError, ValueError):
        return 0.0


def normalize_plan(
    plan: dict[str, Any],
    position_map: dict[str, dict[str, Any]],
    *,
    max_actions: int = 10,
    max_buys: int = 3,
    regime: str | None = None,
    max_buys_bullish: int | None = None,
    max_buys_non_bullish: int | None = None,
) -> dict[str, Any]:
    """Dedupe tickers, drop invalid sells, cap size, sort sells before buys."""
    reg = (regime or "unknown").lower()
    if max_buys_bullish is not None and max_buys_non_bullish is not None:
        max_buys = max_buys_bullish if reg == "bullish" else max_buys_non_bullish

    actions = list(plan.get("actions") or [])
    if not actions:
        return plan

    pmap = {str(k).upper(): v for k, v in (position_map or {}).items()}
    by_ticker: dict[str, dict[str, Any]] = {}

    for act in actions:
        if not isinstance(act, dict):
            continue
        sym = str(act.get("ticker") or "").upper()
        if not sym:
            continue
        side = _act_side(act)
        if side not in _SIDE_RANK:
            side = "hold"
        act = {**act, "side": side}

        if side == "sell" and sym not in pmap:
            continue

        prev = by_ticker.get(sym)
        if prev is None:
            by_ticker[sym] = act
            continue
        prev_side = _act_side(prev)
        if _SIDE_RANK.get(side, 9) < _SIDE_RANK.get(prev_side, 9):
            by_ticker[sym] = act
        elif _SIDE_RANK.get(side, 9) == _SIDE_RANK.get(prev_side, 9) and _conf(act) > _conf(prev):
            by_ticker[sym] = act

    merged = list(by_ticker.values())
    merged.sort(
        key=lambda a: (
            _SIDE_RANK.get(_act_side(a), 9),
            -_conf(a),
        )
    )

    sells = [a for a in merged if _act_side(a) == "sell"]
    buys = [a for a in merged if _act_side(a) == "buy"][:max_buys]
    rest = [a for a in merged if _act_side(a) not in ("sell", "buy")]
    capped = (sells + buys + rest)[:max_actions]

    out = dict(plan)
    out["actions"] = capped
    return out
