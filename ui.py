"""
Run from repo root:
  .venv/bin/streamlit run ui.py
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from src.config import kill_switch_active, load_settings, project_root
from src.context import TradingContext, gather_trading_context
from src.dashboard.history import portfolio_history_df
from src.dashboard.layout import DashboardLayout
from src.dashboard.styles import inject_chart_chrome_last, inject_dashboard_styles
from src.dashboard.vega_chrome_nuke import inject_vega_chrome_nuke
from src.decision_engine import evaluate_action_guardrails
from src.learning import build_learning_report
from src.main import execute_plan, propose_plan
from src.risk import validate_buy, validate_sell
from src.universe import fetch_sp500_constituents


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
            settings=ctx.settings,
            min_avg_volume_10d=ctx.settings.min_avg_volume_10d,
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


def _latest_postmortem() -> dict[str, Any] | None:
    d = project_root() / "data" / "reports"
    if not d.exists():
        return None
    files = sorted(d.glob("postmortem_*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _format_uptime(total_seconds: float) -> str:
    s = max(0, int(total_seconds))
    if s >= 86400:
        d, rem = divmod(s, 86400)
        h, rem2 = divmod(rem, 3600)
        m, sec = divmod(rem2, 60)
        return f"{d}d {h}h {m:02d}m {sec:02d}s"
    if s >= 3600:
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        return f"{h}h {m:02d}m {sec:02d}s"
    if s >= 60:
        m, sec = divmod(s, 60)
        return f"{m}m {sec:02d}s"
    return f"{s}s"


@st.fragment(run_every=1)
def _session_clock_fragment() -> None:
    """Live local time + session uptime (since this browser tab loaded the app)."""
    elapsed = time.time() - float(st.session_state.ui_session_started_at)
    now = datetime.now().astimezone()
    st.markdown(
        "<div class='session-clock'>"
        f"<span class='session-clock-time'>{escape(now.strftime('%a %b %d  %H:%M:%S'))}</span>"
        "<span class='session-clock-sub'>"
        "Session uptime · <span class='session-clock-up'>"
        f"{escape(_format_uptime(elapsed))}</span>"
        "</span></div>",
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="AI Trading Pro", layout="wide")
inject_dashboard_styles()
if "ui_session_started_at" not in st.session_state:
    st.session_state.ui_session_started_at = time.time()
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

st.markdown(
    "<div class='dash-brand'><h1>AI Trading Terminal</h1>"
    f"<span>Universe {len(ctx.universe):,} symbols · "
    f"{'Paper' if settings.alpaca_paper else 'Live'} · "
    f"{'Execution on' if settings.execute_trades else 'Execution off'}</span></div>",
    unsafe_allow_html=True,
)

_sp_l, _sp_c, _sp_r = st.columns([1, 2.4, 1])
with _sp_c:
    _session_clock_fragment()

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
    c_eq1, c_eq2, c_eq3, c_eq4 = st.columns(4, gap="small")
    with c_eq1:
        period = st.selectbox(
            "Window",
            ["1W", "1M", "3M", "6M", "1A"],
            index=1,
            key="dash_eq_period",
            label_visibility="collapsed",
        )
    with c_eq2:
        timeframe = st.selectbox(
            "TF",
            ["1D", "1H", "15Min"],
            index=0,
            key="dash_eq_tf",
            label_visibility="collapsed",
        )
    hist_df, hist_err = portfolio_history_df(ctx, period, timeframe)
    with c_eq3:
        if hist_err is None and not hist_df.empty:
            export_df = hist_df.copy()
            export_df["time"] = export_df["time"].dt.strftime("%Y-%m-%d %H:%M:%S%z")
            st.download_button(
                "Export",
                data=export_df.to_csv(index=False).encode("utf-8"),
                file_name=f"equity_history_{period}_{timeframe}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.button("Export", disabled=True, use_container_width=True)
    with c_eq4:
        if st.button("Refresh", use_container_width=True, key="dash_eq_refresh"):
            st.rerun()

    DashboardLayout.render_overview_body(
        ctx,
        settings,
        hist_df=hist_df,
        hist_err=hist_err,
    )

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

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Expectancy/action", f"{(float(g.get('expectancy_pct') or 0)*100):.2f}%")
    pf = g.get("profit_factor")
    e2.metric("Profit factor", "-" if pf is None else f"{float(pf):.2f}")
    pr = g.get("payoff_ratio")
    e3.metric("Payoff ratio", "-" if pr is None else f"{float(pr):.2f}")
    e4.metric(
        "Avg win / Avg loss",
        f"{(float(g.get('avg_win_pct') or 0)*100):.2f}% / -{(float(g.get('avg_loss_pct_abs') or 0)*100):.2f}%"
        if g.get("avg_win_pct") is not None and g.get("avg_loss_pct_abs") is not None
        else "-",
    )

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

    b1, b2, b3 = st.columns(3)
    with b1:
        st.subheader("By side")
        st.dataframe(
            pd.DataFrame(report.get("by_side") or []),
            use_container_width=True,
            hide_index=True,
        )
    with b2:
        st.subheader("By regime")
        st.dataframe(
            pd.DataFrame(report.get("by_regime") or []),
            use_container_width=True,
            hide_index=True,
        )
    with b3:
        st.subheader("By horizon")
        st.dataframe(
            pd.DataFrame(report.get("by_horizon") or []),
            use_container_width=True,
            hide_index=True,
        )

    pm = _latest_postmortem()
    st.subheader("Latest post-mortem")
    if pm:
        st.json(pm)
    else:
        st.caption("No post-mortem report yet.")

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

# After all elements: highest CSS cascade priority for chart chrome (toolbar + vega ⋯).
inject_chart_chrome_last()
# DOM removal in parent document (when Streamlit’s styles block CSS-only fixes).
inject_vega_chrome_nuke()
