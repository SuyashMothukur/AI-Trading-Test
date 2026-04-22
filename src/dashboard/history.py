"""Portfolio history DataFrame helpers for the dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ..context import TradingContext


def portfolio_history_df(ctx: TradingContext, period: str, timeframe: str) -> tuple[pd.DataFrame, str | None]:
    try:
        points = ctx.broker.portfolio_history(period=period, timeframe=timeframe)
    except Exception as e:
        return pd.DataFrame(), str(e)
    if not points:
        return pd.DataFrame(), None
    df = pd.DataFrame(points)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    for col in ("equity_usd", "profit_loss_usd", "profit_loss_pct"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values("time")
    if "equity_usd" in df.columns:
        df = df[df["equity_usd"] > 0].copy()
    df = df.dropna(subset=["time", "equity_usd"])
    df = df.drop_duplicates(subset=["time"], keep="last")
    return df, None


def positions_view(positions: list, query: str, sort_key: str) -> pd.DataFrame:
    if not positions:
        return pd.DataFrame()
    df = pd.DataFrame(positions)
    if query:
        q = query.strip().lower()
        df = df[df["symbol"].fillna("").str.lower().str.contains(q)]
    sort_map = {
        "Market value (high to low)": ("market_value_usd", False),
        "Unrealized P/L (high to low)": ("unrealized_pl_usd", False),
        "Symbol (A-Z)": ("symbol", True),
    }
    col, asc = sort_map.get(sort_key, ("market_value_usd", False))
    if col in df.columns:
        df = df.sort_values(col, ascending=asc)
    return df
