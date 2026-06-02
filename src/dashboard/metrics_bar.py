"""Top summary strip: equity, net P/L vs baseline, unrealized, session P/L, buying power, win rate."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from ..broker_alpaca import AccountView
from ..context import TradingContext
from .formatting import fmt_currency, fmt_percent, fmt_percent_plain, fmt_signed_currency


def _signed_html(value: float) -> str:
    tone = "tone-up" if value > 0 else "tone-down" if value < 0 else ""
    sc = fmt_signed_currency(value)
    if not tone:
        return escape(sc)
    return f'<span class="{tone}">{escape(sc)}</span>'


class TopMetricsBar:
    @staticmethod
    def _open_unrealized(positions: list[dict[str, Any]]) -> float:
        return sum(float((p or {}).get("unrealized_pl_usd") or 0.0) for p in (positions or []))

    @staticmethod
    def _vs_baseline_pnl(equity_now: float, baseline_usd: float) -> tuple[float, float]:
        base = float(baseline_usd)
        if base <= 0:
            return 0.0, 0.0
        pnl = float(equity_now) - base
        return pnl, pnl / base

    @staticmethod
    def _session_pnl(ctx: TradingContext, equity_now: float) -> tuple[str, str]:
        start = ctx.daily_state.session_start_equity_usd
        if start is None or start <= 0:
            return "—", "Set when the app first loads each UTC day"
        pnl = float(equity_now) - float(start)
        return _signed_html(pnl), f"Since today’s first snapshot ({fmt_currency(start)})"

    @staticmethod
    def _pnl_banner_html(net_pnl: float, baseline_usd: float, net_pct: float) -> str:
        base_txt = escape(fmt_currency(baseline_usd))
        pnl_txt = escape(fmt_signed_currency(net_pnl))
        pct_txt = escape(fmt_percent(net_pct, decimals=2))
        if abs(net_pnl) < 0.005:
            state, cls = "Flat", "pnl-banner-flat"
            headline = f"About even with your {base_txt} baseline"
        elif net_pnl > 0:
            state, cls = "Winning", "pnl-banner-gain"
            headline = f"Up {pnl_txt} ({pct_txt}) vs {base_txt} baseline"
        else:
            state, cls = "Losing", "pnl-banner-loss"
            headline = f"Down {pnl_txt} ({pct_txt}) vs {base_txt} baseline"
        return (
            f"<div class='pnl-banner {cls}'>"
            f"<span class='pnl-banner-state'>{escape(state)}</span>"
            f"<span class='pnl-banner-headline'>{headline}</span>"
            f"</div>"
        )

    @staticmethod
    def render(
        ctx: TradingContext,
        hist_df: pd.DataFrame,
        hist_err: str | None = None,
        *,
        account: AccountView | None = None,
        positions: list[dict[str, Any]] | None = None,
    ) -> None:
        del hist_df, hist_err

        g = (ctx.user_payload.get("learning_feedback") or {}).get("global") or {}
        wr = g.get("win_rate_ex_breakeven") or g.get("win_rate")
        win = fmt_percent_plain(float(wr), decimals=1) if wr is not None else "—"

        acct = account or ctx.account
        pos = positions if positions is not None else ctx.positions
        eq_now = float(acct.equity_usd)
        baseline = float(ctx.settings.initial_equity_usd)
        net_pnl, net_pct = TopMetricsBar._vs_baseline_pnl(eq_now, baseline)
        unreal = TopMetricsBar._open_unrealized(pos)

        live_tick = datetime.now(timezone.utc).strftime("%H:%M:%S")
        tick_suffix = "" if account is None else f" · {live_tick} UTC"

        if net_pnl > 0.005:
            net_tile_cls = "metric-tile metric-tile-pnl-gain"
        elif net_pnl < -0.005:
            net_tile_cls = "metric-tile metric-tile-pnl-loss"
        else:
            net_tile_cls = "metric-tile"

        net_sub = f"Equity {fmt_currency(eq_now)} − baseline {fmt_currency(baseline)}{tick_suffix}"
        net_val = (
            f"{_signed_html(net_pnl)} "
            f'<span class="pnl-pct-chip">{escape(fmt_percent(net_pct, decimals=2))}</span>'
        )

        banner = TopMetricsBar._pnl_banner_html(net_pnl, baseline, net_pct)
        sess_html, sess_sub = TopMetricsBar._session_pnl(ctx, eq_now)
        sess_sub = f"{sess_sub}{tick_suffix}"

        tiles = [
            ("Net P/L", net_val, net_sub, net_tile_cls),
            ("Equity", escape(fmt_currency(acct.equity_usd)), f"Net liquidation{tick_suffix}", "metric-tile glow-equity"),
            ("Open unrealized", _signed_html(unreal), f"Open positions mark-to-market{tick_suffix}", "metric-tile"),
            ("Session P/L", sess_html, sess_sub, "metric-tile"),
            ("Buying power", escape(fmt_currency(acct.buying_power_usd)), f"Deployable{tick_suffix}", "metric-tile"),
            ("Win rate", escape(win), "Learning journal (not account P/L)", "metric-tile"),
        ]
        inner = "".join(
            f"<div class='{cls}'><span class='k'>{escape(title)}</span>"
            f"<div class='v'>{val}</div><div class='sub'>{escape(sub)}</div></div>"
            for title, val, sub, cls in tiles
        )

        st.markdown(f"{banner}<div class='metric-strip'>{inner}</div>", unsafe_allow_html=True)
