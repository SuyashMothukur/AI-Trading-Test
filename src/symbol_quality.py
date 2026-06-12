"""Symbol-level quality scoring from journal outcomes + live quant."""

from __future__ import annotations

from typing import Any

from .config import Settings


def top_winners(
    learning_feedback: dict[str, Any],
    *,
    min_samples: int = 5,
    min_avg_return_pct: float = 0.003,
    min_win_rate: float = 0.45,
    limit: int = 15,
) -> list[str]:
    rows = learning_feedback.get("symbol_priors") or []
    picks: list[tuple[float, str]] = []
    for row in rows:
        sym = str(row.get("ticker") or "").upper()
        if not sym:
            continue
        n = int(row.get("samples") or 0)
        avg = row.get("avg_return_pct")
        wr = row.get("win_rate")
        if n < min_samples or avg is None or wr is None:
            continue
        a, w = float(avg), float(wr)
        if a >= min_avg_return_pct and w >= min_win_rate:
            picks.append((a * 100 + w * 2.0, sym))
    picks.sort(reverse=True)
    return [s for _, s in picks[:limit]]


def chronic_losers(
    learning_feedback: dict[str, Any],
    *,
    min_samples: int = 5,
    max_avg_return_pct: float = -0.002,
    max_win_rate: float = 0.35,
) -> list[str]:
    out: list[str] = []
    for row in learning_feedback.get("symbol_priors") or []:
        sym = str(row.get("ticker") or "").upper()
        n = int(row.get("samples") or 0)
        avg = row.get("avg_return_pct")
        wr = row.get("win_rate")
        if not sym or n < min_samples or avg is None or wr is None:
            continue
        if float(avg) <= max_avg_return_pct or float(wr) < max_win_rate:
            out.append(sym)
    return sorted(set(out))


def evaluate_buy_quality(
    *,
    ticker: str,
    action: dict[str, Any],
    metrics: dict[str, Any] | None,
    prior: dict[str, Any] | None,
    regime: str,
    settings: Settings,
    top_winner_set: set[str],
) -> tuple[bool, str]:
    """Extra buy filters tuned for higher win rate."""
    horizon = str(action.get("horizon") or "swing").lower()
    if settings.block_intraday_buys and horizon == "intraday":
        return False, "intraday buys blocked (low historical win rate)"

    if regime in {"choppy", "bearish"}:
        conf = float(action.get("confidence_0_to_1") or 0.0)
        need = float(settings.choppy_min_confidence)
        if conf < need:
            return (
                False,
                f"{regime} regime needs confidence >= {need:.2f} (got {conf:.2f})",
            )

    if prior:
        n = int(prior.get("samples") or 0)
        wr = prior.get("win_rate")
        avg = prior.get("avg_return_pct")
        if (
            n >= settings.min_symbol_samples_for_win_filter
            and wr is not None
            and float(wr) < float(settings.min_symbol_win_rate)
            and (avg is None or float(avg) <= 0)
        ):
            return (
                False,
                f"symbol win rate {float(wr):.1%} below {settings.min_symbol_win_rate:.1%} "
                f"(samples={n})",
            )

    if metrics:
        mom5 = float(metrics.get("mom_5d") or 0.0)
        mom10 = float(metrics.get("mom_10d") or 0.0)
        if settings.require_trend_alignment and not metrics.get("trend_aligned"):
            return False, "5D/10D trend not aligned"
        if mom5 < float(settings.min_mom5_for_buy):
            return False, f"5D momentum {mom5:.2%} below {settings.min_mom5_for_buy:.2%}"
        if mom10 < float(settings.min_mom10_for_buy):
            return False, f"10D momentum {mom10:.2%} below {settings.min_mom10_for_buy:.2%}"
        # Unknown names without history need stronger momentum.
        if not prior and ticker not in top_winner_set:
            if mom5 < float(settings.min_mom5_for_new_symbols):
                return (
                    False,
                    f"new symbol needs mom5 >= {settings.min_mom5_for_new_symbols:.2%}",
                )

    return True, "passes quality gate"
