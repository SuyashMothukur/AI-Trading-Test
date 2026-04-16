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


def resolve_universe_with_metadata(
    explicit: list[str] | None,
) -> tuple[list[str], dict[str, dict[str, str]]]:
    if explicit:
        syms = sorted({t.upper() for t in explicit})
        meta = {
            s: {"symbol": s, "name": "Custom universe", "sector": "Custom"}
            for s in syms
        }
        return syms, meta
    rows = fetch_sp500_constituents()
    syms = [r["symbol"] for r in rows]
    meta = {r["symbol"]: r for r in rows}
    return syms, meta
