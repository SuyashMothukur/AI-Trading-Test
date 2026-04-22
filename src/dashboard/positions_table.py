"""Compact open-positions table."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from .formatting import fmt_currency, fmt_signed_currency


class PositionsTable:
    @staticmethod
    def _html(df: pd.DataFrame) -> str:
        if df.empty:
            return "<div class='chart-empty'>No open positions match the current filters.</div>"
        headers = [
            "Symbol",
            "Qty",
            "Avail",
            "Value",
            "Entry",
            "Last",
            "uP/L",
        ]
        rows: list[str] = []
        for _, row in df.iterrows():
            pl = float(row.get("unrealized_pl_usd") or 0.0)
            pl_cls = "pl-pos" if pl > 0 else "pl-neg" if pl < 0 else "pl-flat"
            rows.append(
                "<tr>"
                f"<td class='symbol-cell'>{escape(str(row.get('symbol', '-')))}</td>"
                f"<td class='num'>{float(row.get('qty') or 0.0):,.3f}</td>"
                f"<td class='num'>{float(row.get('qty_available') or 0.0):,.3f}</td>"
                f"<td class='num'>{escape(fmt_currency(row.get('market_value_usd')))}</td>"
                f"<td class='num'>{escape(fmt_currency(row.get('avg_entry_price')))}</td>"
                f"<td class='num'>{escape(fmt_currency(row.get('current_price_usd')))}</td>"
                f"<td class='num {pl_cls}'>{escape(fmt_signed_currency(pl))}</td>"
                "</tr>"
            )
        th = "".join(f"<th>{escape(h)}</th>" for h in headers)
        body = "".join(rows)
        return (
            "<div class='table-wrap'><table class='positions'>"
            f"<thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>"
        )

    @staticmethod
    def render(df: pd.DataFrame) -> None:
        st.markdown(PositionsTable._html(df), unsafe_allow_html=True)
