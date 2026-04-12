from __future__ import annotations

import csv
from io import StringIO

import httpx

SP500_CSV = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
    "master/data/constituents.csv"
)


def fetch_sp500_symbols(timeout: float = 30.0) -> list[str]:
    """Returns S&P 500 tickers (large-cap US equities), from a public constituents CSV."""
    r = httpx.get(SP500_CSV, timeout=timeout)
    r.raise_for_status()
    reader = csv.DictReader(StringIO(r.text))
    out: list[str] = []
    for row in reader:
        sym = (row.get("Symbol") or "").strip().upper()
        if sym:
            out.append(sym)
    return sorted(set(out))


def resolve_universe(explicit: list[str] | None) -> list[str]:
    if explicit:
        return sorted({t.upper() for t in explicit})
    return fetch_sp500_symbols()
