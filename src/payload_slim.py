"""Shrink trading context sent to the LLM (full universe stays in app state)."""

from __future__ import annotations

from typing import Any


def slim_payload_for_model(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop huge fields; keep what the advisor needs for decisions."""
    ctx_syms = list(payload.get("context_symbols") or [])
    bars = payload.get("bars_by_symbol") or {}
    slim_bars = {s: bars[s] for s in ctx_syms if s in bars}
    meta = payload.get("symbol_metadata") or {}
    slim_meta = {s: meta[s] for s in ctx_syms if s in meta}

    quant = payload.get("quant_snapshot") or {}
    sym_metrics = quant.get("symbol_metrics") or []
    ctx_set = {str(s).upper() for s in ctx_syms}
    slim_metrics = [
        m for m in sym_metrics if str(m.get("ticker") or "").upper() in ctx_set
    ]

    positions = payload.get("open_positions") or []
    pos_summary = []
    for p in positions:
        sym = str(p.get("symbol") or "").upper()
        entry = float(p.get("avg_entry_price") or 0.0)
        px = float(p.get("current_price_usd") or 0.0)
        unreal = float(p.get("unrealized_pl_usd") or 0.0)
        unreal_pct = ((px - entry) / entry) if entry > 0 else None
        pos_summary.append(
            {
                "symbol": sym,
                "qty": p.get("qty"),
                "market_value_usd": p.get("market_value_usd"),
                "unrealized_pl_usd": unreal,
                "unrealized_pct": unreal_pct,
                "current_price_usd": px,
            }
        )

    uni = payload.get("full_universe") or []
    return {
        "utc_time": payload.get("utc_time"),
        "alpaca_paper": payload.get("alpaca_paper"),
        "account": payload.get("account"),
        "risk_limits": payload.get("risk_limits"),
        "universe_note": (
            f"Tradable universe size: {len(uni)} symbols. "
            "You may only propose tickers in context_symbols or open_positions."
        ),
        "context_symbols": ctx_syms,
        "open_positions": pos_summary,
        "bars_by_symbol": slim_bars,
        "quant_snapshot": {
            "market_regime": quant.get("market_regime"),
            "symbol_metrics": slim_metrics,
        },
        "recent_news": payload.get("recent_news") or [],
        "learning_feedback": payload.get("learning_feedback"),
        "execution_policy": payload.get("execution_policy"),
        "symbol_metadata": slim_meta,
    }
