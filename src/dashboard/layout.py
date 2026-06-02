"""Two-column overview layout orchestration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd
import streamlit as st

from ..broker_alpaca import AccountView
from ..context import TradingContext
from .history import positions_view
from .metrics_bar import TopMetricsBar
from .positions_table import PositionsTable
from .run_health import RunHealthPanel
from .trading_chart import TradingChart


def _live_top_metrics(ctx: TradingContext, hist_df: pd.DataFrame, hist_err: str | None) -> None:
    try:
        acct = ctx.broker.account()
        pos = ctx.broker.positions()
        st.session_state["_dash_live_account"] = acct
        st.session_state["_dash_live_positions"] = pos
    except Exception:
        TopMetricsBar.render(ctx, hist_df, hist_err=hist_err)
        return
    TopMetricsBar.render(ctx, hist_df, hist_err=hist_err, account=acct, positions=pos)


@st.fragment(run_every=timedelta(seconds=2))
def _live_top_metrics_fragment(ctx: TradingContext) -> None:
    raw_df = st.session_state.get("_dash_hist_df")
    hist_df = raw_df if isinstance(raw_df, pd.DataFrame) else pd.DataFrame()
    hist_err = st.session_state.get("_dash_hist_err")
    hist_err_str = hist_err if isinstance(hist_err, str) else (str(hist_err) if hist_err else None)
    _live_top_metrics(ctx, hist_df, hist_err_str)


@st.fragment(run_every=timedelta(seconds=2))
def _live_run_health_fragment(ctx: TradingContext, settings: Any) -> None:
    acct = st.session_state.get("_dash_live_account")
    pos = st.session_state.get("_dash_live_positions")
    if not isinstance(acct, AccountView):
        acct = None
    if not isinstance(pos, list):
        pos = None
    RunHealthPanel.render(ctx, settings, account=acct, positions=pos)


class DashboardLayout:
    """Primary 70 / 30 terminal layout for the Overview tab."""

    @staticmethod
    def render_overview_body(ctx: TradingContext, settings: Any) -> None:
        _live_top_metrics_fragment(ctx)

        left, right = st.columns([13, 7], gap="small")

        with left:
            TradingChart.render(ctx)

        with right:
            _live_run_health_fragment(ctx, settings)

        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown(
            "<div class='panel-head'><div><p class='panel-title'>Open positions</p>"
            "<p class='panel-sub'>Refresh page or top strip ticker for latest marks</p></div></div>",
            unsafe_allow_html=True,
        )
        f1, f2 = st.columns([1.25, 0.75], gap="small")
        with f1:
            search = st.text_input("Filter", placeholder="Symbol", key="dash_pos_filter", label_visibility="collapsed")
        with f2:
            sort_choice = st.selectbox(
                "Sort",
                ["Market value (high to low)", "Unrealized P/L (high to low)", "Symbol (A-Z)"],
                key="dash_pos_sort",
                label_visibility="collapsed",
            )
        if ctx.positions:
            PositionsTable.render(positions_view(ctx.positions, search, sort_choice))
        else:
            st.caption("No open positions.")
        st.markdown("</div>", unsafe_allow_html=True)
