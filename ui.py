"""
Run from repo root:
  .venv/bin/streamlit run ui.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from src.config import kill_switch_active, load_settings, project_root
from src.context import TradingContext, gather_trading_context
from src.learning import build_learning_report
from src.main import execute_plan, propose_plan
from src.risk import validate_buy, validate_sell
from src.universe import fetch_sp500_constituents


def _inject_style() -> None:
    st.markdown(
        """
        <style>
          .stApp {background: linear-gradient(180deg, #0A1020 0%, #090F1A 100%);} 
          [data-testid="stMetric"] {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(148,163,184,0.20);
            border-radius: 14px;
            padding: 10px 14px;
          }
          .section-card {
            border: 1px solid rgba(148,163,184,0.20);
            border-radius: 14px;
            padding: 12px 14px;
            background: rgba(255,255,255,0.02);
          }
          .trace-box {
            border: 1px solid rgba(148,163,184,0.25);
            border-radius: 10px;
            padding: 9px 11px;
            background: rgba(148,163,184,0.06);
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
    df = df.sort_values("time")
    # Remove placeholder zeros that make chart look broken.
    if "equity_usd" in df:
        df = df[df["equity_usd"] > 0].copy()
    return df


def _render_equity_chart(df: pd.DataFrame) -> None:
    st.subheader("Overall equity curve")
    if df.empty or len(df) < 2:
        st.caption("Not enough non-zero history points yet for a smooth curve.")
        return
    y_min = float(df["equity_usd"].min())
    y_max = float(df["equity_usd"].max())
    pad = max((y_max - y_min) * 0.15, 1)
    chart = (
        alt.Chart(df)
        .mark_line(strokeWidth=3, color="#60A5FA")
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y("equity_usd:Q", title="Equity (USD)", scale=alt.Scale(domain=[y_min - pad, y_max + pad], zero=False)),
            tooltip=[
                alt.Tooltip("time:T", title="Time"),
                alt.Tooltip("equity_usd:Q", title="Equity", format=",.2f"),
                alt.Tooltip("profit_loss_usd:Q", title="P/L", format=",.2f"),
                alt.Tooltip("profit_loss_pct:Q", title="P/L %", format=".2%"),
            ],
        )
        .properties(height=360)
    )
    st.altair_chart(chart, use_container_width=True)
    st.caption(f"Range P/L: ${float(df['profit_loss_usd'].iloc[-1]):,.2f}")


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

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Broker mode", "Paper" if settings.alpaca_paper else "LIVE")
m2.metric("Execution", "Enabled" if settings.execute_trades else "Disabled")
m3.metric("Equity", f"${ctx.account.equity_usd:,.2f}")
m4.metric("Buying power", f"${ctx.account.buying_power_usd:,.2f}")
m5.metric("Universe", f"{len(ctx.universe):,}")

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
        p1, p2 = st.columns(2)
        period = p1.selectbox("History period", ["1W", "1M", "3M", "6M", "1A"], index=1)
        timeframe = p2.selectbox("History timeframe", ["1D", "1H", "15Min"], index=0)
        try:
            hist_df = _history_df(ctx, period, timeframe)
            _render_equity_chart(hist_df)
        except Exception as e:
            st.warning(f"Could not fetch history: {e}")

    with right:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("Run health")
        sched = _scheduler_state()
        st.write(
            {
                "orders_placed_today": ctx.daily_state.orders_placed,
                "resolved_learning_actions": (ctx.user_payload.get("learning_feedback") or {}).get("global", {}).get("resolved_actions"),
                "news_items_in_cycle": len(ctx.user_payload.get("recent_news") or []),
                "scheduler_last_reason": None if not sched else sched.get("last_reason"),
                "scheduler_runs_today": None if not sched else sched.get("runs_today"),
            }
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.subheader("Open positions")
    if ctx.positions:
        st.dataframe(pd.DataFrame(ctx.positions), use_container_width=True, hide_index=True)
    else:
        st.caption("No open positions.")

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
