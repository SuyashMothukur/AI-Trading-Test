"""
Run from repo root:
  .venv/bin/streamlit run ui.py
"""

from __future__ import annotations

import json

import streamlit as st

from src.config import kill_switch_active, load_settings
from src.context import gather_trading_context
from src.main import execute_plan, propose_plan

st.set_page_config(page_title="AI Trading", layout="wide")
st.title("Trading dashboard")

settings = load_settings()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Alpaca", "Paper" if settings.alpaca_paper else "LIVE")
k2.metric("Execute orders", "On" if settings.execute_trades else "Off")
k3.metric("Kill switch", "ACTIVE" if kill_switch_active() else "inactive")
k4.metric(
    "Live money ack",
    "OK" if settings.real_money_ack == "YES_I_ACCEPT_LOSS_RISK" else "not set",
)

if not settings.alpaca_api_key or not settings.alpaca_secret_key:
    st.error("Add **ALPACA_API_KEY** and **ALPACA_SECRET_KEY** to `.env`.")
    st.stop()

if not settings.openai_api_key:
    st.error("Add **OPENAI_API_KEY** to `.env` for AI plans.")
    st.stop()

ctx, gather_err = gather_trading_context(settings)
if gather_err:
    st.warning(gather_err)
    st.stop()
assert ctx is not None

a1, a2, a3 = st.columns(3)
a1.metric("Equity (USD)", f"{ctx.account.equity_usd:,.2f}")
a2.metric("Buying power", f"{ctx.account.buying_power_usd:,.2f}")
a3.metric("Cash", f"{ctx.account.cash_usd:,.2f}")

st.subheader("Open positions")
if ctx.positions:
    st.dataframe(ctx.positions, use_container_width=True, hide_index=True)
else:
    st.caption("No open positions.")

if ctx.bars_warning:
    st.warning(f"Market data: {ctx.bars_warning}")

can_trade = ctx.blocked_reason is None
if ctx.blocked_reason:
    st.error(ctx.blocked_reason)

st.divider()
left, right = st.columns(2)

with left:
    if st.button(
        "Run AI plan",
        type="primary",
        use_container_width=True,
        disabled=not can_trade,
    ):
        with st.spinner("Calling model…"):
            try:
                st.session_state["last_plan"] = propose_plan(ctx)
                st.session_state["plan_error"] = None
            except Exception as e:
                st.session_state["plan_error"] = str(e)
                st.session_state.pop("last_plan", None)

    if st.session_state.get("plan_error"):
        st.error(st.session_state["plan_error"])

    plan = st.session_state.get("last_plan")
    if plan is not None:
        st.subheader("Latest plan (JSON)")
        st.code(json.dumps(plan, indent=2), language="json")

with right:
    st.caption(
        "Execution uses your `.env` gates: **EXECUTE_TRADES**, "
        "**REAL_MONEY_ACK** (live only), and risk limits."
    )
    if st.button(
        "Execute latest plan",
        use_container_width=True,
        disabled=not can_trade,
    ):
        plan = st.session_state.get("last_plan")
        if not plan:
            st.warning("Run **Run AI plan** first.")
        else:
            ctx_fresh, e2 = gather_trading_context(settings)
            if e2 or ctx_fresh is None:
                st.error(e2 or "Could not refresh context.")
            elif ctx_fresh.blocked_reason:
                st.error(ctx_fresh.blocked_reason)
            else:
                lines = execute_plan(ctx_fresh, plan)
                st.session_state["exec_log"] = lines

    log = st.session_state.get("exec_log")
    if log:
        st.subheader("Execution log")
        st.text("\n".join(log))
