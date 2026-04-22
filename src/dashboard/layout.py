"""Two-column overview layout orchestration."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from ..context import TradingContext
from .history import positions_view
from .metrics_bar import TopMetricsBar
from .positions_table import PositionsTable
from .run_health import RunHealthPanel
from .trading_chart import TradingChart


class DashboardLayout:
    """Primary 70 / 30 terminal layout for the Overview tab."""

    @staticmethod
    def render_overview_body(
        ctx: TradingContext,
        settings: Any,
        *,
        hist_df: pd.DataFrame,
        hist_err: str | None,
    ) -> None:
        TopMetricsBar.render(ctx, hist_df, hist_err=hist_err)

        left, right = st.columns([13, 7], gap="small")

        with left:
            TradingChart.render(ctx)

        with right:
            RunHealthPanel.render(ctx, settings)

        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown(
            "<div class='panel-head'><div><p class='panel-title'>Open positions</p>"
            "<p class='panel-sub'>Live book</p></div></div>",
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
            pos_df = positions_view(ctx.positions, search, sort_choice)
            PositionsTable.render(pos_df)
        else:
            st.caption("No open positions.")
        st.markdown("</div>", unsafe_allow_html=True)
