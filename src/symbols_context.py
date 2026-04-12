from __future__ import annotations

from datetime import date


def symbols_for_context(
    universe: list[str], open_position_symbols: list[str], limit: int
) -> list[str]:
    """Include all open positions plus a rotating slice of the wider universe."""
    pos = sorted({s.upper() for s in open_position_symbols})
    if len(pos) >= limit:
        return pos[:limit]
    rest = [s for s in universe if s.upper() not in set(pos)]
    cap_rest = max(0, limit - len(pos))
    if cap_rest == 0:
        return pos[:limit]
    n_chunks = max(1, (len(rest) + cap_rest - 1) // cap_rest)
    start_idx = (date.today().toordinal() % n_chunks) * cap_rest
    batch = rest[start_idx : start_idx + cap_rest]
    return pos + batch
