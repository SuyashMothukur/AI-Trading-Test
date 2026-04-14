"""
Run from repo root:
  .venv/bin/streamlit run ui.py
"""

from __future__ import annotations

import json
import time
from html import escape
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from src.config import kill_switch_active, load_settings, project_root
from src.context import TradingContext, gather_trading_context
from src.decision_engine import evaluate_action_guardrails
from src.learning import build_learning_report
from src.main import execute_plan, propose_plan
from src.risk import validate_buy, validate_sell
from src.universe import fetch_sp500_constituents


def _inject_style() -> None:
    st.markdown(
        """
        <style>
          :root {
            --bg-main: #070d1c;
            --bg-soft: #0b142a;
            --bg-card: rgba(16, 27, 50, 0.82);
            --bg-card-alt: rgba(14, 24, 45, 0.78);
            --text-primary: #e8eefc;
            --text-secondary: #9ba9c2;
            --line-soft: rgba(122, 149, 196, 0.24);
            --line-strong: rgba(143, 172, 224, 0.38);
            --good: #34d399;
            --bad: #fb7185;
            --accent: #60a5fa;
            --radius-lg: 16px;
            --radius-md: 12px;
          }
          .stApp {
            background:
              radial-gradient(1200px 420px at 15% -12%, rgba(59,130,246,0.14) 0%, rgba(59,130,246,0) 60%),
              radial-gradient(900px 300px at 98% 0%, rgba(14,165,233,0.08) 0%, rgba(14,165,233,0) 65%),
              linear-gradient(180deg, #070d1c 0%, #060b16 100%);
            color: var(--text-primary);
          }
          .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
          .dashboard-title {
            margin: 0 0 10px 0;
            font-size: 1.12rem;
            font-weight: 650;
            letter-spacing: 0.01em;
            color: #d8e4ff;
          }
          .summary-card {
            background: linear-gradient(180deg, var(--bg-card) 0%, rgba(12, 21, 40, 0.88) 100%);
            border: 1px solid var(--line-soft);
            border-radius: var(--radius-lg);
            padding: 14px 15px;
            min-height: 102px;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.02), 0 8px 22px rgba(2,8,23,0.28);
          }
          .summary-label {
            font-size: 0.76rem;
            letter-spacing: 0.02em;
            font-weight: 580;
            color: var(--text-secondary);
            margin-bottom: 10px;
          }
          .summary-value {
            font-size: 1.8rem;
            line-height: 1.08;
            font-weight: 700;
            color: #eef4ff;
            margin-bottom: 8px;
          }
          .summary-sub {
            font-size: 0.78rem;
            color: #8ea0be;
          }
          .status-pill {
            display: inline-block;
            padding: 4px 9px;
            border-radius: 999px;
            font-size: 0.68rem;
            letter-spacing: 0.02em;
            font-weight: 650;
            margin-left: 7px;
            vertical-align: middle;
          }
          .status-on {
            background: rgba(52, 211, 153, 0.16);
            color: #8ff1cb;
            border: 1px solid rgba(52, 211, 153, 0.38);
          }
          .status-off {
            background: rgba(251, 113, 133, 0.14);
            color: #fda4af;
            border: 1px solid rgba(251, 113, 133, 0.34);
          }
          .dashboard-card {
            background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-card-alt) 100%);
            border: 1px solid var(--line-soft);
            border-radius: var(--radius-lg);
            padding: 14px 16px;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.02), 0 8px 22px rgba(2,8,23,0.25);
          }
          .section-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
            gap: 10px;
          }
          .section-title {
            margin: 0;
            font-size: 1.1rem;
            font-weight: 640;
            letter-spacing: 0.01em;
            color: #e4eeff;
          }
          .section-subtle {
            color: #90a0bc;
            font-size: 0.74rem;
            letter-spacing: 0.02em;
          }
          .toolbar-label {
            font-size: 0.875rem;
            line-height: 1.25rem;
            min-height: 1.25rem;
            margin-bottom: 0.32rem;
            visibility: hidden;
          }
          .stats-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
            margin-bottom: 8px;
          }
          .stat-chip {
            border: 1px solid rgba(122, 149, 196, 0.30);
            border-radius: 10px;
            background: rgba(11, 20, 39, 0.72);
            padding: 8px 10px;
          }
          .chip-label {
            font-size: 0.67rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #8294b1;
          }
          .chip-value {
            margin-top: 2px;
            font-size: 0.96rem;
            font-weight: 650;
            color: #e5eeff;
          }
          .chip-positive {color: #89e7c4;}
          .chip-negative {color: #fda4af;}
          .chart-empty {
            border: 1px dashed rgba(122, 149, 196, 0.38);
            border-radius: 12px;
            padding: 24px 16px;
            text-align: center;
            color: #8ea0be;
            background: rgba(8, 14, 28, 0.56);
          }
          .health-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 9px;
          }
          .health-item {
            border: 1px solid rgba(122, 149, 196, 0.28);
            border-radius: 10px;
            padding: 9px 10px;
            background: rgba(10, 18, 34, 0.68);
          }
          .health-key {
            font-size: 0.67rem;
            color: #8797b3;
            letter-spacing: 0.03em;
            text-transform: uppercase;
          }
          .health-value {
            margin-top: 4px;
            font-size: 1.02rem;
            font-weight: 640;
            color: #e2ecff;
            word-break: break-word;
          }
          .tone-good {color: #7ce5bf;}
          .tone-neutral {color: #d7e3fb;}
          .tone-warn {color: #fbbf24;}
          .table-wrap {
            border: 1px solid rgba(122, 149, 196, 0.28);
            border-radius: 12px;
            overflow: hidden;
            margin-top: 8px;
          }
          table.positions {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.86rem;
          }
          table.positions th {
            text-align: left;
            padding: 9px 10px;
            background: rgba(13, 21, 41, 0.86);
            color: #95a6c3;
            font-weight: 610;
            border-bottom: 1px solid rgba(122, 149, 196, 0.24);
          }
          table.positions td {
            padding: 10px;
            border-bottom: 1px solid rgba(122, 149, 196, 0.14);
            color: #dce8ff;
          }
          table.positions tr:last-child td {border-bottom: none;}
          .num {text-align: right;}
          .symbol-cell {font-weight: 620; letter-spacing: 0.01em;}
          .pl-pos {color: #7ce5bf; font-weight: 620;}
          .pl-neg {color: #fda4af; font-weight: 620;}
          .pl-flat {color: #c7d6f3; font-weight: 620;}
          [data-baseweb="tab-list"] {
            gap: 8px;
            padding: 6px;
            background: rgba(10, 18, 35, 0.72);
            border: 1px solid rgba(122, 149, 196, 0.24);
            border-radius: 12px;
            margin: 8px 0 14px 0;
          }
          button[role="tab"] {
            border-radius: 9px !important;
            height: 34px !important;
            padding: 0 12px !important;
            color: #9eb0cc !important;
            border: 1px solid transparent !important;
            background: transparent !important;
            font-size: 0.84rem !important;
            font-weight: 600 !important;
          }
          button[role="tab"][aria-selected="true"] {
            color: #e8f0ff !important;
            background: rgba(96, 165, 250, 0.16) !important;
            border-color: rgba(96, 165, 250, 0.42) !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
          }
          [data-baseweb="select"] > div {
            min-height: 38px;
            border-radius: 10px;
            background: rgba(12, 21, 39, 0.72);
            border: 1px solid rgba(122, 149, 196, 0.30);
          }
          [data-baseweb="select"] span {
            color: #e1ebff;
            font-size: 0.86rem;
          }
          .trace-box {
            border: 1px solid rgba(122, 149, 196, 0.28);
            border-radius: 12px;
            padding: 10px 12px;
            background: rgba(10, 18, 34, 0.72);
            margin-bottom: 8px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _sell_qty_for_action(act: dict[str, Any], pos: dict[str, Any] | None) -> float | None:
    if pos is None:
        return None
    avail = float(pos.get("qty_available") or 0.0)
    if avail <= 0:
        return None
    q = act.get("qty")
    if q is not None and float(q) > 0:
        return min(float(q), avail)
    n = act.get("notional_usd")
    px = float(pos.get("current_price_usd") or 0.0)
    if n is not None and px > 0:
        return min(avail, float(n) / px)
    return avail


def _preview_verdicts(ctx: TradingContext, plan: dict[str, Any]) -> list[dict[str, Any]]:
    s = ctx.settings
    uni_set = set(ctx.universe)
    out: list[dict[str, Any]] = []
    for act in plan.get("actions") or []:
        side = (act.get("side") or "hold").lower()
        ticker = (act.get("ticker") or "").upper()
        if not ticker:
            continue
        verdict = "hold"
        reason = "No order for hold action."
        g_ok, g_reason = evaluate_action_guardrails(
            action=act,
            learning_feedback=ctx.user_payload.get("learning_feedback") or {},
            quant_snapshot=ctx.user_payload.get("quant_snapshot") or {},
            min_samples=ctx.settings.learning_min_samples,
        )
        if not g_ok:
            verdict, reason = "blocked", f"Guardrail: {g_reason}"
            out.append(
                {
                    "ticker": ticker,
                    "side": side,
                    "confidence": act.get("confidence_0_to_1"),
                    "notional_usd": act.get("notional_usd"),
                    "risk": act.get("risk"),
                    "horizon": act.get("horizon"),
                    "verdict": verdict,
                    "reason": reason,
                }
            )
            continue
        if side == "buy":
            n = act.get("notional_usd")
            if n is None:
                verdict, reason = "blocked", "Missing notional_usd."
            else:
                d = validate_buy(
                    ticker=ticker,
                    universe=uni_set,
                    notional=float(n),
                    max_order_notional=s.max_order_notional_usd,
                    current_position_value=float(ctx.pmap.get(ticker, {}).get("market_value_usd") or 0.0),
                    max_position_notional=s.max_position_notional_usd,
                    buying_power=ctx.account.buying_power_usd,
                )
                verdict, reason = ("ok", "Would submit") if d.ok else ("blocked", d.reason)
        elif side == "sell":
            sq = _sell_qty_for_action(act, ctx.pmap.get(ticker))
            if sq is None or sq <= 0:
                verdict, reason = "blocked", "No position or sellable qty."
            else:
                d = validate_sell(
                    ticker=ticker,
                    universe=uni_set,
                    qty=sq,
                    available_qty=float(ctx.pmap[ticker]["qty_available"]),
                )
                verdict, reason = ("ok", "Would submit") if d.ok else ("blocked", d.reason)

        out.append(
            {
                "ticker": ticker,
                "side": side,
                "confidence": act.get("confidence_0_to_1"),
                "notional_usd": act.get("notional_usd"),
                "risk": act.get("risk"),
                "horizon": act.get("horizon"),
                "verdict": verdict,
                "reason": reason,
            }
        )
    return out


@st.cache_data(ttl=1800)
def _company_catalog(explicit_universe: tuple[str, ...]) -> pd.DataFrame:
    if explicit_universe:
        rows = [{"symbol": s.upper(), "name": "Custom universe", "sector": "Custom"} for s in explicit_universe]
        return pd.DataFrame(rows)
    return pd.DataFrame(fetch_sp500_constituents())


def _history_df(ctx: TradingContext, period: str, timeframe: str) -> pd.DataFrame:
    points = ctx.broker.portfolio_history(period=period, timeframe=timeframe)
    if not points:
        return pd.DataFrame()
    df = pd.DataFrame(points)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    for col in ["equity_usd", "profit_loss_usd", "profit_loss_pct"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values("time")
    # Remove placeholder zeros that make chart look broken.
    if "equity_usd" in df:
        df = df[df["equity_usd"] > 0].copy()
    df = df.dropna(subset=["time", "equity_usd"])
    # Keep the latest point when broker history returns duplicate timestamps.
    df = df.drop_duplicates(subset=["time"], keep="last")
    return df


def _fmt_currency(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"${float(value):,.2f}"


def _fmt_signed_currency(value: float | int | None) -> str:
    if value is None:
        return "-"
    f = float(value)
    return f"+${abs(f):,.2f}" if f >= 0 else f"-${abs(f):,.2f}"


def _fmt_percent(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:+.2f}%"


def _summary_card(label: str, value: str, sub: str = "", status: str | None = None) -> str:
    status_html = ""
    if status:
        tone = "status-on" if status.lower() in {"enabled", "paper", "active", "live"} else "status-off"
        status_html = f"<span class='status-pill {tone}'>{escape(status)}</span>"
    return (
        "<div class='summary-card'>"
        f"<div class='summary-label'>{escape(label)}</div>"
        f"<div class='summary-value'>{escape(value)}{status_html}</div>"
        f"<div class='summary-sub'>{escape(sub)}</div>"
        "</div>"
    )


def _health_item(label: str, value: str, tone: str = "neutral") -> str:
    tone_cls = {"good": "tone-good", "warn": "tone-warn", "neutral": "tone-neutral"}.get(tone, "tone-neutral")
    return (
        "<div class='health-item'>"
        f"<div class='health-key'>{escape(label)}</div>"
        f"<div class='health-value {tone_cls}'>{escape(value)}</div>"
        "</div>"
    )


def _positions_table_html(df: pd.DataFrame) -> str:
    if df.empty:
        return "<div class='chart-empty'>No open positions match the current filters.</div>"
    headers = [
        "Symbol",
        "Qty",
        "Available",
        "Market Value",
        "Avg Entry",
        "Current Price",
        "Unrealized P/L",
    ]
    rows: list[str] = []
    for _, row in df.iterrows():
        pl = float(row.get("unrealized_pl_usd") or 0.0)
        pl_cls = "pl-pos" if pl > 0 else "pl-neg" if pl < 0 else "pl-flat"
        rows.append(
            "<tr>"
            f"<td class='symbol-cell'>{escape(str(row.get('symbol', '-')))}</td>"
            f"<td class='num'>{float(row.get('qty') or 0.0):,.4f}</td>"
            f"<td class='num'>{float(row.get('qty_available') or 0.0):,.4f}</td>"
            f"<td class='num'>{_fmt_currency(row.get('market_value_usd'))}</td>"
            f"<td class='num'>{_fmt_currency(row.get('avg_entry_price'))}</td>"
            f"<td class='num'>{_fmt_currency(row.get('current_price_usd'))}</td>"
            f"<td class='num {pl_cls}'>{_fmt_signed_currency(pl)}</td>"
            "</tr>"
        )
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join(rows)
    return f"<div class='table-wrap'><table class='positions'><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>"


def _render_equity_chart(df: pd.DataFrame, compare_mode: str = "None") -> None:
    if df.empty or len(df) < 2:
        st.markdown(
            "<div class='chart-empty'>Not enough non-zero history points yet. The chart will become more informative as additional cycles complete.</div>",
            unsafe_allow_html=True,
        )
        return
    plot_df = df.copy()
    y_title = "Equity (USD)"
    y_fmt = ",.2f"
    if compare_mode == "Vs start (USD)":
        start_eq = float(plot_df["equity_usd"].iloc[0] or 0.0)
        plot_df["plot_value"] = plot_df["equity_usd"] - start_eq
        y_title = "Change vs Start (USD)"
    elif compare_mode == "Vs start (%)":
        start_eq = float(plot_df["equity_usd"].iloc[0] or 0.0)
        if start_eq <= 0:
            plot_df["plot_value"] = 0.0
        else:
            plot_df["plot_value"] = ((plot_df["equity_usd"] / start_eq) - 1.0) * 100.0
        y_title = "Change vs Start (%)"
        y_fmt = ".2f"
    else:
        plot_df["plot_value"] = plot_df["equity_usd"]

    y_min = float(plot_df["plot_value"].min())
    y_max = float(plot_df["plot_value"].max())
    spread = max(y_max - y_min, 0.0)
    if spread < 0.01:
        # Flat series: use a tight pad so the line stays readable.
        pad = max(abs(y_max) * 0.0004, 5.0)
    else:
        pad = max(spread * 0.18, 1.0)
    domain_min = y_min - pad
    domain_max = y_max + pad
    base = alt.Chart(df).encode(
        x=alt.X("time:T", title=None, axis=alt.Axis(orient="bottom", labelPadding=8, tickCount=8, grid=False)),
        y=alt.Y(
            "plot_value:Q",
            title=y_title,
            scale=alt.Scale(domain=[domain_min, domain_max], zero=False, nice=False),
            axis=alt.Axis(grid=True),
        ),
        tooltip=[
            alt.Tooltip("time:T", title="Time"),
            alt.Tooltip("plot_value:Q", title=y_title, format=y_fmt),
            alt.Tooltip("equity_usd:Q", title="Equity", format=",.2f"),
            alt.Tooltip("profit_loss_usd:Q", title="P/L", format=",.2f"),
            alt.Tooltip("profit_loss_pct:Q", title="P/L %", format=".2%"),
        ],
    )
    line_width = 3.2 if spread < 0.01 else 2.8
    line = base.mark_line(color="#7DD3FC", strokeWidth=line_width)
    markers = base.mark_point(color="#BAE6FD", filled=True, size=54 if spread < 0.01 else 34, opacity=0.92)
    layers: list[Any] = [line, markers]
    if compare_mode != "None":
        baseline = alt.Chart(pd.DataFrame({"y": [0.0]})).mark_rule(
            color="rgba(148,163,184,0.55)",
            strokeDash=[4, 3],
        ).encode(y="y:Q")
        layers.insert(0, baseline)
    chart = alt.layer(*layers).properties(height=340)
    chart = chart.configure_view(strokeOpacity=0).configure_axis(
        gridColor="rgba(122, 149, 196, 0.14)",
        domainColor="rgba(122, 149, 196, 0.34)",
        tickColor="rgba(122, 149, 196, 0.30)",
        labelColor="#9fb0cc",
        titleColor="#aebed8",
    )
    st.altair_chart(chart, use_container_width=True)


def _history_stats(df: pd.DataFrame, positions: list[dict[str, Any]]) -> dict[str, str]:
    if df.empty:
        return {
            "Total return": "-",
            "Daily return": "-",
            "Unrealized P/L": _fmt_signed_currency(sum(float((p or {}).get("unrealized_pl_usd") or 0.0) for p in positions)),
            "Max drawdown": "-",
        }
    start = float(df["equity_usd"].iloc[0] or 0.0)
    latest = float(df["equity_usd"].iloc[-1] or 0.0)
    total_ret = ((latest / start) - 1) if start > 0 else 0.0
    if len(df) > 1:
        prev = float(df["equity_usd"].iloc[-2] or latest)
        daily_ret = ((latest / prev) - 1) if prev > 0 else 0.0
    else:
        daily_ret = 0.0
    eq = df["equity_usd"].astype(float)
    roll_max = eq.cummax()
    drawdown = ((eq - roll_max) / roll_max).min() if not roll_max.empty else 0.0
    unrealized = sum(float((p or {}).get("unrealized_pl_usd") or 0.0) for p in positions)
    return {
        "Total return": _fmt_percent(total_ret),
        "Daily return": _fmt_percent(daily_ret),
        "Unrealized P/L": _fmt_signed_currency(unrealized),
        "Max drawdown": _fmt_percent(float(drawdown)),
    }


def _stats_strip_html(stats: dict[str, str]) -> str:
    chips: list[str] = []
    for key, value in stats.items():
        tone = ""
        if value.startswith("+"):
            tone = "chip-positive"
        elif value.startswith("-"):
            tone = "chip-negative"
        chips.append(
            "<div class='stat-chip'>"
            f"<div class='chip-label'>{escape(key)}</div>"
            f"<div class='chip-value {tone}'>{escape(value)}</div>"
            "</div>"
        )
    return f"<div class='stats-strip'>{''.join(chips)}</div>"


def _positions_view(positions: list[dict[str, Any]], query: str, sort_key: str) -> pd.DataFrame:
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


def _render_trace(trace: list[dict[str, str]]) -> None:
    st.subheader("AI cycle trace")
    if not trace:
        st.caption("Run a cycle to view step-by-step trace.")
        return
    for item in trace:
        st.markdown(
            f"<div class='trace-box'><b>{item['step']}</b><br/>{item['detail']}</div>",
            unsafe_allow_html=True,
        )


def _scheduler_state() -> dict[str, Any] | None:
    p = project_root() / "data" / "runtime_scheduler.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


st.set_page_config(page_title="AI Trading Pro", layout="wide")
_inject_style()
settings = load_settings()

if not settings.alpaca_api_key or not settings.alpaca_secret_key:
    st.error("Add ALPACA_API_KEY and ALPACA_SECRET_KEY to .env.")
    st.stop()
if not settings.openai_api_key:
    st.error("Add OPENAI_API_KEY to .env.")
    st.stop()

ctx, gather_err = gather_trading_context(settings)
if gather_err or ctx is None:
    st.error(gather_err or "Failed to build trading context.")
    st.stop()

st.markdown("<div class='dashboard-title'>Portfolio Operations Dashboard</div>", unsafe_allow_html=True)

summary_cols = st.columns(5)
summary_cards = [
    _summary_card(
        label="Broker mode",
        value="Paper" if settings.alpaca_paper else "Live",
        sub="Connected account mode",
        status="Paper" if settings.alpaca_paper else "Live",
    ),
    _summary_card(
        label="Execution",
        value="Enabled" if settings.execute_trades else "Disabled",
        sub="Order placement control",
        status="Enabled" if settings.execute_trades else "Disabled",
    ),
    _summary_card(
        label="Equity",
        value=_fmt_currency(ctx.account.equity_usd),
        sub="Net liquidation value",
    ),
    _summary_card(
        label="Buying power",
        value=_fmt_currency(ctx.account.buying_power_usd),
        sub="Available for new exposure",
    ),
    _summary_card(
        label="Universe",
        value=f"{len(ctx.universe):,}",
        sub="Symbols in active scope",
    ),
]
for c, card in zip(summary_cols, summary_cards):
    c.markdown(card, unsafe_allow_html=True)

if ctx.bars_warning:
    st.warning(f"Market data: {ctx.bars_warning}")
if ctx.news_warning:
    st.warning(f"News: {ctx.news_warning}")
if kill_switch_active():
    st.error("Kill switch STOP_TRADING is active.")
if ctx.blocked_reason:
    st.error(ctx.blocked_reason)

can_trade = ctx.blocked_reason is None

overview_tab, cycle_tab, learning_tab, universe_tab, raw_tab = st.tabs(
    ["Overview", "AI Cycle", "Learning Report", "All Companies", "Raw Data"]
)

with overview_tab:
    left, right = st.columns([2, 1])
    with left:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.markdown(
            "<div class='section-head'><h3 class='section-title'>Equity performance</h3>"
            "<div class='section-subtle'>Trend + key risk stats</div></div>",
            unsafe_allow_html=True,
        )
        p1, p2, p3, p4, p5 = st.columns([0.9, 0.9, 1.25, 0.7, 0.6])
        period = p1.selectbox("History period", ["1W", "1M", "3M", "6M", "1A"], index=1)
        timeframe = p2.selectbox("History timeframe", ["1D", "1H", "15Min"], index=0)
        compare_mode = p3.selectbox(
            "Compare",
            ["None", "Vs start (USD)", "Vs start (%)"],
            index=0,
            help="Overlay performance versus the beginning of the selected window.",
        )
        p4.markdown("<div class='toolbar-label'>Actions</div>", unsafe_allow_html=True)
        p5.markdown("<div class='toolbar-label'>Actions</div>", unsafe_allow_html=True)
        refresh_clicked = p5.button("Refresh", use_container_width=True)
        if refresh_clicked:
            st.rerun()
        try:
            hist_df = _history_df(ctx, period, timeframe)
            with p4:
                if not hist_df.empty:
                    export_df = hist_df.copy()
                    export_df["time"] = export_df["time"].dt.strftime("%Y-%m-%d %H:%M:%S%z")
                    st.download_button(
                        "Export CSV",
                        data=export_df.to_csv(index=False).encode("utf-8"),
                        file_name=f"equity_history_{period}_{timeframe}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                else:
                    st.button("Export CSV", disabled=True, use_container_width=True)
            stats = _history_stats(hist_df, ctx.positions)
            st.markdown(_stats_strip_html(stats), unsafe_allow_html=True)
            _render_equity_chart(hist_df, compare_mode=compare_mode)
            if not hist_df.empty:
                st.caption(f"Range P/L in selected window: {_fmt_signed_currency(hist_df['profit_loss_usd'].iloc[-1])}")
        except Exception as e:
            st.warning(f"Could not fetch history: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.markdown(
            "<div class='section-head'><h3 class='section-title'>Run health</h3>"
            "<div class='section-subtle'>Operational snapshot</div></div>",
            unsafe_allow_html=True,
        )
        sched = _scheduler_state()
        resolved = (ctx.user_payload.get("learning_feedback") or {}).get("global", {}).get("resolved_actions")
        regime = ((ctx.user_payload.get("quant_snapshot") or {}).get("market_regime") or {}).get("regime")
        health_html = (
            "<div class='health-grid'>"
            + _health_item("Orders placed today", str(ctx.daily_state.orders_placed), "good" if ctx.daily_state.orders_placed > 0 else "neutral")
            + _health_item("News items in cycle", str(len(ctx.user_payload.get("recent_news") or [])))
            + _health_item("Market regime", str(regime or "Unknown"), "warn" if str(regime).lower() == "volatile" else "neutral")
            + _health_item("Scheduler runs today", str((sched or {}).get("runs_today") or 0))
            + _health_item("Last scheduler reason", str((sched or {}).get("last_reason") or "Not available"))
            + _health_item("Resolved learning actions", str(resolved or 0))
            + "</div>"
        )
        st.markdown(health_html, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-head'><h3 class='section-title'>Open positions</h3>"
        "<div class='section-subtle'>Live holdings and P/L exposure</div></div>",
        unsafe_allow_html=True,
    )
    f1, f2 = st.columns([1.4, 1])
    search = f1.text_input("Search positions", placeholder="Filter by symbol")
    sort_choice = f2.selectbox(
        "Sort by",
        ["Market value (high to low)", "Unrealized P/L (high to low)", "Symbol (A-Z)"],
        index=0,
    )
    if ctx.positions:
        pos_df = _positions_view(ctx.positions, search, sort_choice)
        st.markdown(_positions_table_html(pos_df), unsafe_allow_html=True)
    else:
        st.caption("No open positions.")
    st.markdown("</div>", unsafe_allow_html=True)

with cycle_tab:
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Run AI cycle", type="primary", use_container_width=True, disabled=not can_trade):
            trace: list[dict[str, str]] = []
            start = time.perf_counter()
            with st.status("Running AI cycle", expanded=True) as status:
                status.write("Refreshing context...")
                ctx_run, err = gather_trading_context(settings)
                if err or ctx_run is None:
                    st.session_state["plan_error"] = err or "Context error"
                    st.session_state.pop("last_plan", None)
                    status.update(label="Cycle failed", state="error")
                else:
                    trace.append({"step": "1) Context", "detail": f"symbols={len(ctx_run.user_payload.get('context_symbols', []))}, positions={len(ctx_run.positions)}"})
                    trace.append({"step": "2) Learning+News", "detail": f"news={len(ctx_run.user_payload.get('recent_news') or [])}, resolved_actions={(ctx_run.user_payload.get('learning_feedback') or {}).get('global', {}).get('resolved_actions')}"})
                    try:
                        plan = propose_plan(ctx_run)
                        verdicts = _preview_verdicts(ctx_run, plan)
                        st.session_state["last_plan"] = plan
                        st.session_state["preview_verdicts"] = verdicts
                        st.session_state["plan_error"] = None
                        counts = pd.Series([v["side"] for v in verdicts]).value_counts().to_dict()
                        trace.append({"step": "3) Model output", "detail": f"counts={counts}"})
                        blocked = sum(1 for v in verdicts if v["verdict"] == "blocked")
                        trace.append({"step": "4) Risk pre-check", "detail": f"blocked_actions={blocked}"})
                        trace.append({"step": "5) Runtime", "detail": f"elapsed={time.perf_counter()-start:.2f}s"})
                        st.session_state["cycle_trace"] = trace
                        status.update(label="Cycle complete", state="complete")
                    except Exception as e:
                        st.session_state["plan_error"] = str(e)
                        status.update(label="Cycle failed", state="error")

        if st.session_state.get("plan_error"):
            st.error(st.session_state["plan_error"])
        _render_trace(st.session_state.get("cycle_trace", []))

    with c2:
        if st.button("Execute latest plan", use_container_width=True, disabled=not can_trade):
            plan = st.session_state.get("last_plan")
            if not plan:
                st.warning("Run AI cycle first.")
            else:
                ctx_fresh, err2 = gather_trading_context(settings)
                if err2 or ctx_fresh is None:
                    st.error(err2 or "Could not refresh context.")
                else:
                    st.session_state["exec_log"] = execute_plan(ctx_fresh, plan)

        if st.session_state.get("exec_log"):
            st.subheader("Execution log")
            st.text("\n".join(st.session_state["exec_log"]))

    st.subheader("Action transparency")
    verdicts = st.session_state.get("preview_verdicts", [])
    if verdicts:
        st.dataframe(pd.DataFrame(verdicts), use_container_width=True, hide_index=True)
    else:
        st.caption("No actions yet.")

with learning_tab:
    report = build_learning_report(min_samples=settings.learning_min_samples)
    g = report.get("global", {})
    a, b, c, d = st.columns(4)
    a.metric("Resolved actions", int(g.get("resolved_actions") or 0))
    b.metric("Pending actions", int(g.get("pending_actions") or 0))
    c.metric("Win rate", f"{(float(g.get('win_rate') or 0)*100):.1f}%")
    d.metric("Avg return/action", f"{(float(g.get('avg_return_pct') or 0)*100):.2f}%")

    t1, t2 = st.columns(2)
    with t1:
        st.subheader("Top symbols")
        top = report.get("top_symbols") or []
        st.dataframe(pd.DataFrame(top), use_container_width=True, hide_index=True)
    with t2:
        st.subheader("Weak symbols")
        worst = report.get("worst_symbols") or []
        st.dataframe(pd.DataFrame(worst), use_container_width=True, hide_index=True)

    st.subheader("Recent resolved actions")
    recent = report.get("recent_resolved_actions") or []
    if recent:
        view = pd.DataFrame(recent)[["resolved_ts", "ticker", "side", "confidence_0_to_1", "realized_return_pct", "rationale"]]
        st.dataframe(view, use_container_width=True, hide_index=True)
    else:
        st.caption("No resolved actions yet. Let cycles run for at least the evaluation delay window.")

with universe_tab:
    explicit = tuple(settings.trade_universe or [])
    companies = _company_catalog(explicit)
    f1, f2 = st.columns([2, 1])
    q = f1.text_input("Search symbol/company", placeholder="AAPL or Apple")
    sectors = sorted(companies["sector"].dropna().unique().tolist()) if "sector" in companies else []
    selected = f2.multiselect("Sector", sectors)
    shown = companies.copy()
    if q:
        ql = q.lower().strip()
        shown = shown[shown["symbol"].str.lower().str.contains(ql) | shown["name"].str.lower().str.contains(ql)]
    if selected and "sector" in shown:
        shown = shown[shown["sector"].isin(selected)]
    st.caption(f"Showing {len(shown):,} of {len(companies):,}")
    st.dataframe(shown, use_container_width=True, height=560, hide_index=True)

with raw_tab:
    st.code(json.dumps(ctx.user_payload, indent=2), language="json")
