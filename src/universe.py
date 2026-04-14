from __future__ import annotations

import csv
from io import StringIO

import httpx

SP500_CSV = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
    "master/data/constituents.csv"
)


def fetch_sp500_constituents(timeout: float = 30.0) -> list[dict[str, str]]:
    """Returns S&P 500 constituents with symbol and company metadata."""
    r = httpx.get(SP500_CSV, timeout=timeout)
    r.raise_for_status()
    reader = csv.DictReader(StringIO(r.text))
    out: list[dict[str, str]] = []
    for row in reader:
        symbol = (row.get("Symbol") or "").strip().upper()
        if not symbol:
            continue
        out.append(
            {
                "symbol": symbol,
                "name": (row.get("Name") or "").strip(),
                "sector": (row.get("Sector") or "").strip(),
            }
        )
    return sorted(out, key=lambda r: r["symbol"])


def fetch_sp500_symbols(timeout: float = 30.0) -> list[str]:
    """Returns S&P 500 tickers (large-cap US equities), from a public constituents CSV."""
    return [row["symbol"] for row in fetch_sp500_constituents(timeout=timeout)]


def resolve_universe(explicit: list[str] | None) -> list[str]:
    if explicit:
        return sorted({t.upper() for t in explicit})
    return fetch_sp500_symbols()
