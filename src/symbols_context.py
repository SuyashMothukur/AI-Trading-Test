from __future__ import annotations

from datetime import date
from typing import Any

from .quant import symbol_metrics


def _prior_map(learning_feedback: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in (learning_feedback or {}).get("symbol_priors") or []:
        t = str(row.get("ticker") or "").upper()
        if t:
            out[t] = row
    return out


def candidate_pool_for_bars(
    universe: list[str],
    open_position_symbols: list[str],
    limit: int,
) -> list[str]:
    """Wider symbol set to fetch bars before quant ranking."""
    pos = sorted({s.upper() for s in open_position_symbols})
    if limit <= len(pos):
        return pos[:limit]
    rest = [s for s in universe if s.upper() not in set(pos)]
    cap_rest = max(0, limit - len(pos))
    if cap_rest == 0:
        return pos[:limit]
    n_chunks = max(1, (len(rest) + cap_rest - 1) // cap_rest)
    start_idx = (date.today().toordinal() % n_chunks) * cap_rest
    batch = rest[start_idx : start_idx + cap_rest]
    return pos + batch


def rank_symbols_for_context(
    *,
    candidates: list[str],
    bars_by_symbol: dict[str, list[dict[str, Any]]],
    learning_feedback: dict[str, Any] | None,
    open_position_symbols: list[str],
    limit: int,
    weak_buy_blocklist: set[str] | None = None,
    auto_blocklist_min_samples: int = 5,
    auto_blocklist_avg_below: float = -0.005,
) -> list[str]:
    """
    Rank candidates by momentum/liquidity; penalize chronic losers from learning.
    Always includes all open positions first.
    """
    pos = sorted({s.upper() for s in open_position_symbols})
    metrics = symbol_metrics(bars_by_symbol)
    priors = _prior_map(learning_feedback)
    manual_block = weak_buy_blocklist or set()

    scored: list[tuple[float, str]] = []
    for sym in candidates:
        su = sym.upper()
        if su in pos:
            continue
        m = metrics.get(su)
        if not m:
            continue
        mom5 = float(m.get("mom_5d") or 0.0)
        mom10 = float(m.get("mom_10d") or 0.0)
        vol = float(m.get("vol_10d") or 0.0)
        liq = float(m.get("avg_volume_10d") or 0.0)
        score = mom5 * 2.5 + mom10 * 1.2 - vol * 3.0
        if mom5 > 0 and mom10 > 0:
            score += 0.9
        elif mom5 < 0 or mom10 < 0:
            score -= 1.4
        if liq < 300_000:
            score -= 0.5
        if su in manual_block:
            score -= 5.0
        pri = priors.get(su)
        if pri:
            n = int(pri.get("samples") or 0)
            avg = float(pri.get("avg_return_pct") or 0.0)
            wr = float(pri.get("win_rate") or 0.0)
            if n >= auto_blocklist_min_samples and avg < auto_blocklist_avg_below:
                score -= 4.0
            elif n >= 5 and wr < 0.38 and avg <= 0:
                score -= 3.0
            elif n >= 3 and avg < 0:
                score -= 1.5
            elif avg > 0.003 and wr >= 0.45:
                score += 1.6
            elif avg > 0.003:
                score += 0.8
            elif n >= 5:
                score += wr * 1.2
        scored.append((score, su))

    scored.sort(key=lambda x: x[0], reverse=True)
    ranked_rest = [s for _, s in scored]
    out = list(pos)
    for s in ranked_rest:
        if s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out[:limit]


def symbols_for_context(
    universe: list[str], open_position_symbols: list[str], limit: int
) -> list[str]:
    """Legacy rotating slice (used when ranking is skipped)."""
    return candidate_pool_for_bars(universe, open_position_symbols, limit)
