"""Top summary strip: equity, buying power, daily P/L, return, realized (est.), win rate."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

from .formatting import fmt_currency, fmt_percent, fmt_percent_plain, fmt_signed_currency

if TYPE_CHECKING:
    from ..context import TradingContext


class TopMetricsBar:
    @staticmethod
    def _window_total_return(hist_df: pd.DataFrame) -> tuple[str, str]:
        if hist_df is None or hist_df.empty or len(hist_df) < 2:
            return "—", "Selected history window"
        s = float(pd.to_numeric(hist_df["equity_usd"].iloc[0], errors="coerce") or 0.0)
        e = float(pd.to_numeric(hist_df["equity_usd"].iloc[-1], errors="coerce") or 0.0)
        if s <= 0:
            return "—", "Selected history window"
        r = (e / s) - 1.0
        tone = "tone-up" if r >= 0 else "tone-down"
        return f'<span class="{tone}">{escape(fmt_percent(r, decimals=2))}</span>', "History window (portfolio chart)"

    @staticmethod
    def _daily_session_pnl(ctx: TradingContext) -> tuple[str, str]:
        start = ctx.daily_state.session_start_equity_usd
        if start is None or start <= 0:
            return "—", "Baseline after first equity snapshot today"
        pnl = float(ctx.account.equity_usd) - float(start)
        tone = "tone-up" if pnl >= 0 else "tone-down" if pnl < 0 else ""
        sc = fmt_signed_currency(pnl)
        val = f'<span class="{tone}">{escape(sc)}</span>' if tone else escape(sc)
        return val, "Session vs start-of-day equity"

    @staticmethod
    def _realized_profit_est(
        ctx: TradingContext,
        hist_df: pd.DataFrame,
        hist_err: str | None,
    ) -> tuple[str, str]:
        """
        Closed-book estimate for the selected history window:
        (end equity − start equity) − open unrealized P/L. Not tax-lot realized.
        """
        if hist_err:
            return "—", "Equity history unavailable"
        if hist_df is None or hist_df.empty or len(hist_df) < 2:
            return "—", "Need 2+ points in selected window"
        positions = ctx.positions or []
        unreal = sum(float((p or {}).get("unrealized_pl_usd") or 0.0) for p in positions)
        s = float(pd.to_numeric(hist_df["equity_usd"].iloc[0], errors="coerce") or 0.0)
        e = float(pd.to_numeric(hist_df["equity_usd"].iloc[-1], errors="coerce") or 0.0)
        if s <= 0:
            return "—", "Invalid start equity in window"
        realized_est = (e - s) - unreal
        tone = "tone-up" if realized_est > 0 else "tone-down" if realized_est < 0 else ""
        sc = fmt_signed_currency(realized_est)
        val = f'<span class="{tone}">{escape(sc)}</span>' if tone else escape(sc)
        return val, "Window Δ equity − open unrealized (estimate)"

    @staticmethod
    def render(ctx: TradingContext, hist_df: pd.DataFrame, hist_err: str | None = None) -> None:
        g = (ctx.user_payload.get("learning_feedback") or {}).get("global") or {}
        wr = g.get("win_rate")
        win = fmt_percent_plain(float(wr), decimals=1) if wr is not None else "—"

        tr_html, tr_sub = TopMetricsBar._window_total_return(hist_df)
        d_html, d_sub = TopMetricsBar._daily_session_pnl(ctx)
        rp_html, rp_sub = TopMetricsBar._realized_profit_est(ctx, hist_df, hist_err)

        tiles = [
            ("Equity", escape(fmt_currency(ctx.account.equity_usd)), "Net liquidation", "metric-tile glow-equity"),
            ("Buying power", escape(fmt_currency(ctx.account.buying_power_usd)), "Deployable", "metric-tile"),
            ("Daily P/L", d_html, d_sub, "metric-tile"),
            ("Total return", tr_html, tr_sub, "metric-tile"),
            ("Realized (est.)", rp_html, rp_sub, "metric-tile"),
            ("Win rate", escape(win), "Resolved actions (learning)", "metric-tile"),
        ]
        inner = "".join(
            f"<div class='{cls}'><span class='k'>{escape(title)}</span>"
            f"<div class='v'>{val}</div><div class='sub'>{escape(sub)}</div></div>"
            for title, val, sub, cls in tiles
        )
        st.markdown(f"<div class='metric-strip'>{inner}</div>", unsafe_allow_html=True)
