"""Primary OHLCV + volume trading chart (Altair)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import altair as alt
import pandas as pd
import streamlit as st

from .vega_streamlit import disable_vega_embed_actions

if TYPE_CHECKING:
    from ..context import TradingContext


def _default_symbol(ctx: TradingContext) -> str:
    if ctx.positions:
        best = max(
            ctx.positions,
            key=lambda p: float((p or {}).get("market_value_usd") or 0.0),
        )
        return str((best or {}).get("symbol") or "AAPL").upper()
    if ctx.universe:
        return str(ctx.universe[0]).upper()
    return "AAPL"


def _symbol_choices(ctx: TradingContext) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for p in ctx.positions or []:
        s = str((p or {}).get("symbol") or "").upper()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    for s in ctx.universe or []:
        u = str(s).upper()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    if not out:
        out = ["AAPL"]
    return out


def _bars_to_df(raw: list[dict]) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    df["dt"] = pd.to_datetime(df["t"], utc=True)
    for c in ("o", "h", "l", "c", "v"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["dt", "o", "h", "l", "c"])
    df["body_low"] = df[["o", "c"]].min(axis=1)
    df["body_high"] = df[["o", "c"]].max(axis=1)
    df["bull"] = df["c"] >= df["o"]
    return df


def _price_y_domain(df: pd.DataFrame) -> tuple[float, float]:
    lo = float(df[["l", "o", "c"]].min().min())
    hi = float(df[["h", "o", "c"]].max().max())
    span = max(hi - lo, 1e-9)
    pad = max(span * 0.035, abs(hi) * 0.0012)
    return lo - pad, hi + pad


def build_trading_chart_figure(df: pd.DataFrame, *, last_price: float | None) -> alt.Chart | None:
    if df.empty or len(df) < 2:
        return None

    bull = "#22c55e"
    bear = "#f43f5e"
    bull_vol = "#16a34a"
    bear_vol = "#dc2626"
    color_cond = alt.condition(alt.datum.bull, alt.value(bull), alt.value(bear))
    vol_color = alt.condition(alt.datum.bull, alt.value(bull_vol), alt.value(bear_vol))

    p0, p1 = _price_y_domain(df)

    x_enc = alt.X(
        "dt:T",
        axis=alt.Axis(
            format="%m/%d %H:%M" if (df["dt"].max() - df["dt"].min()).days <= 4 else "%b %d",
            grid=True,
            tickCount=7,
            labelFlush=True,
            labelOverlap=True,
        ),
        title=None,
    )

    hover = alt.selection_point(on="pointermove", nearest=True, fields=["dt"], empty=False)

    y_axis_r = alt.Axis(
        orient="right",
        title=None,
        grid=True,
        tickCount=6,
        gridColor="rgba(100,130,170,0.12)",
        domainColor="rgba(100,130,170,0.22)",
        tickColor="rgba(100,130,170,0.22)",
        labelColor="#8b9ab8",
    )

    wick = (
        alt.Chart(df)
        .mark_rule(size=1)
        .encode(
            x=x_enc,
            y=alt.Y("l:Q", scale=alt.Scale(domain=[p0, p1], nice=False, zero=False), axis=y_axis_r),
            y2="h:Q",
            color=color_cond,
            tooltip=[
                alt.Tooltip("dt:T", title="Time", format="%Y-%m-%d %H:%M UTC"),
                alt.Tooltip("o:Q", title="Open", format=",.2f"),
                alt.Tooltip("h:Q", title="High", format=",.2f"),
                alt.Tooltip("l:Q", title="Low", format=",.2f"),
                alt.Tooltip("c:Q", title="Close", format=",.2f"),
                alt.Tooltip("v:Q", title="Volume", format=",.0f"),
            ],
        )
    )

    body = (
        alt.Chart(df)
        .mark_bar(size=5)
        .encode(
            x=x_enc,
            y=alt.Y("body_low:Q", axis=None),
            y2="body_high:Q",
            color=color_cond,
            tooltip=[
                alt.Tooltip("dt:T", title="Time", format="%Y-%m-%d %H:%M UTC"),
                alt.Tooltip("o:Q", title="Open", format=",.2f"),
                alt.Tooltip("h:Q", title="High", format=",.2f"),
                alt.Tooltip("l:Q", title="Low", format=",.2f"),
                alt.Tooltip("c:Q", title="Close", format=",.2f"),
                alt.Tooltip("v:Q", title="Volume", format=",.0f"),
            ],
        )
    )

    hover_pts = (
        alt.Chart(df)
        .mark_point(size=80, opacity=0)
        .encode(
            x=x_enc,
            y=alt.Y("c:Q", axis=None),
        )
        .add_params(hover)
    )

    v_rule = (
        alt.Chart(df)
        .transform_filter(hover)
        .mark_rule(color="rgba(200, 215, 245, 0.22)", strokeWidth=1)
        .encode(x="dt:T")
    )

    h_rule = (
        alt.Chart(df)
        .transform_filter(hover)
        .mark_rule(color="rgba(200, 215, 245, 0.18)", strokeWidth=1)
        .encode(y=alt.Y("c:Q", axis=None))
    )

    price_layers: list[alt.Chart] = [wick, body, hover_pts, v_rule, h_rule]

    if last_price is not None and last_price > 0:
        last_df = pd.DataFrame({"y": [float(last_price)]})
        price_layers.append(
            alt.Chart(last_df)
            .mark_rule(color="#38bdf8", strokeDash=[5, 4], strokeWidth=1)
            .encode(y=alt.Y("y:Q", axis=None))
        )

    last_row = df.tail(1)
    price_layers.append(
        alt.Chart(last_row)
        .mark_text(align="right", dx=-8, dy=-6, color="#bae6fd", fontSize=11, fontWeight="bold")
        .encode(
            x=x_enc,
            y=alt.Y("c:Q", axis=None),
            text=alt.Text("c:Q", format=",.2f"),
        )
    )

    price_chart = alt.layer(*price_layers).properties(height=275)

    vol_y_axis = alt.Axis(
        orient="right",
        title=None,
        grid=False,
        tickCount=5,
        format=",.0f",
        labelColor="#8b9ab8",
        domainColor="rgba(100,130,170,0.22)",
        tickColor="rgba(100,130,170,0.22)",
    )

    vol = (
        alt.Chart(df)
        .mark_bar(size=5, binSpacing=0)
        .encode(
            x=x_enc,
            y=alt.Y("v:Q", axis=vol_y_axis, title=None, scale=alt.Scale(domainMin=0, nice=True)),
            color=vol_color,
            tooltip=[
                alt.Tooltip("dt:T", title="Time", format="%Y-%m-%d %H:%M UTC"),
                alt.Tooltip("v:Q", title="Volume", format=",.0f"),
            ],
        )
        .properties(height=70)
    )

    chart = (
        alt.vconcat(price_chart, vol, spacing=3)
        .properties(background="transparent")
        .resolve_scale(x="shared", y="independent", color="independent")
        .configure_axis(
            gridColor="rgba(100,130,170,0.1)",
            domainColor="rgba(100,130,170,0.22)",
            tickColor="rgba(100,130,170,0.22)",
            labelColor="#8b9ab8",
            titleColor="#7c8ca8",
        )
        .configure_view(clip=True, strokeWidth=0)
    )
    return disable_vega_embed_actions(chart)


class TradingChart:
    """Price + volume panel for the overview dashboard."""

    TF_OPTIONS = ("1H", "1D", "1W", "1M")

    @staticmethod
    def render(ctx: TradingContext) -> None:
        choices = _symbol_choices(ctx)
        default = _default_symbol(ctx)
        if "dash_chart_symbol" not in st.session_state or st.session_state["dash_chart_symbol"] not in choices:
            st.session_state["dash_chart_symbol"] = default if default in choices else choices[0]

        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown(
            "<div class='panel-head'><div><p class='panel-title'>Price action</p>"
            "<p class='panel-sub'>Live OHLCV · hover for crosshair</p></div></div>",
            unsafe_allow_html=True,
        )

        t1, t2 = st.columns([1.15, 1], vertical_alignment="center")
        with t1:
            try:
                idx = choices.index(st.session_state["dash_chart_symbol"])
            except ValueError:
                idx = 0
            sym = st.selectbox(
                "Symbol",
                choices,
                index=idx,
                key="dash_chart_symbol_select",
                label_visibility="collapsed",
            )
            st.session_state["dash_chart_symbol"] = sym
        with t2:
            tf_raw = st.pills(
                "Timeframe",
                list(TradingChart.TF_OPTIONS),
                default=st.session_state.get("dash_chart_tf", "1D"),
                key="dash_chart_tf",
                label_visibility="collapsed",
            )
        if isinstance(tf_raw, list):
            tf = tf_raw[0] if tf_raw else "1D"
        else:
            tf = (tf_raw or "1D") if tf_raw is not None else "1D"

        bars: list[dict] = []
        err: str | None = None
        try:
            bars, err = ctx.broker.ui_chart_bars(sym, tf)
        except Exception as e:  # pragma: no cover
            err = str(e)

        if err:
            st.markdown(f"<div class='chart-empty'>Could not load bars: {err}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        df = _bars_to_df(bars)
        last_px = float(df["c"].iloc[-1]) if not df.empty else None
        fig = build_trading_chart_figure(df, last_price=last_px)
        if fig is None:
            st.markdown("<div class='chart-empty'>Not enough bars to plot yet.</div>", unsafe_allow_html=True)
        else:
            st.altair_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
