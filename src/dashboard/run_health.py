"""Scheduler + execution health, quick actions, activity feed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Any

import streamlit as st

from ..broker_alpaca import AccountView
from ..config import project_root
from ..scheduler import (
    scheduler_set_enabled,
    scheduler_status,
    start_scheduler_process,
    stop_scheduler_process,
)
from .formatting import fmt_currency, fmt_signed_currency

if TYPE_CHECKING:
    from ..context import TradingContext


def _tail_jsonl(path: Path, n: int = 10) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _fmt_ts(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%m-%d %H:%M UTC")
    except ValueError:
        return iso[:16]


class RunHealthPanel:
    @staticmethod
    def render(
        ctx: TradingContext,
        settings: Any,
        *,
        account: AccountView | None = None,
        positions: list[dict[str, Any]] | None = None,
    ) -> None:
        acct = account or ctx.account
        pos = positions if positions is not None else ctx.positions

        sched_info = scheduler_status()
        sched = sched_info.get("state") or {}
        start = ctx.daily_state.session_start_equity_usd
        session_pnl = float(acct.equity_usd) - float(start) if start else None
        d_tone = "dot-good" if (session_pnl or 0) > 0 else "dot-bad" if (session_pnl or 0) < 0 else "dot-neutral"

        baseline = float(getattr(settings, "initial_equity_usd", 0) or 0)
        net_pnl = float(acct.equity_usd) - baseline if baseline > 0 else None

        n_pos = len(pos or [])
        last_run = _fmt_ts(str(sched.get("last_run_ts") or ""))

        pulse_sub = "Live ops pulse · ~2s broker sync" if account is not None else "Live ops pulse"

        st.markdown("<div class='panel run-health-stack'>", unsafe_allow_html=True)
        st.markdown(
            "<div class='panel-head run-health-head'><div><p class='panel-title'>Run health</p>"
            f"<p class='panel-sub'>{escape(pulse_sub)}</p></div></div>",
            unsafe_allow_html=True,
        )

        if session_pnl is None:
            session_cell = escape("—")
        elif session_pnl > 0:
            session_cell = f"<span class='pl-pos'>{escape(fmt_signed_currency(session_pnl))}</span>"
        elif session_pnl < 0:
            session_cell = f"<span class='pl-neg'>{escape(fmt_signed_currency(session_pnl))}</span>"
        else:
            session_cell = escape(fmt_signed_currency(session_pnl))

        if net_pnl is None:
            net_cell = escape("—")
        elif net_pnl > 0:
            net_cell = f"<span class='pl-pos'>{escape(fmt_signed_currency(net_pnl))}</span>"
        elif net_pnl < 0:
            net_cell = f"<span class='pl-neg'>{escape(fmt_signed_currency(net_pnl))}</span>"
        else:
            net_cell = escape(fmt_signed_currency(net_pnl))
        net_tone = "dot-good" if (net_pnl or 0) > 0 else "dot-bad" if (net_pnl or 0) < 0 else "dot-neutral"

        st.markdown(
            "<div class='health-cards'>"
            f"<div class='health-card'><div class='row'><span class='health-k'>Net P/L</span>"
            f"<span class='health-dot {net_tone}'></span></div>"
            f"<div class='health-v'>{net_cell}</div></div>"
            f"<div class='health-card'><div class='row'><span class='health-k'>Session P/L</span>"
            f"<span class='health-dot {d_tone}'></span></div>"
            f"<div class='health-v'>{session_cell}</div></div>"
            f"<div class='health-card'><div class='row'><span class='health-k'>Open positions</span>"
            f"<span class='health-dot dot-neutral'></span></div>"
            f"<div class='health-v'>{n_pos}</div></div>"
            f"<div class='health-card'><div class='row'><span class='health-k'>Last run</span>"
            f"<span class='health-dot dot-neutral'></span></div>"
            f"<div class='health-v' style='font-size:0.82rem'>{escape(last_run)}</div></div>"
            "</div>",
            unsafe_allow_html=True,
        )

        exec_on = bool(getattr(settings, "execute_trades", False))
        sched_on = bool(sched.get("enabled", True))
        proc_on = bool(sched_info.get("running"))
        mode = "Paper" if settings.alpaca_paper else "Live"
        net_span = (
            f"<span><b>Net P/L</b> {escape(fmt_signed_currency(net_pnl))}</span>"
            if net_pnl is not None
            else ""
        )
        st.markdown(
            "<div class='status-line'>"
            f"<span><b>Bot</b> {'<span class=\"pill pill-on\">ON</span>' if exec_on else '<span class=\"pill pill-off\">EXEC OFF</span>'}</span>"
            f"<span><b>Mode</b> {escape(mode)}</span>"
            f"<span><b>Scheduler</b> {'<span class=\"pill pill-on\">RUNNING</span>' if proc_on else '<span class=\"pill pill-warn\">STOPPED</span>'} "
            f"{'· auto' if sched_on else '· auto paused'}</span>"
            f"<span><b>Equity</b> {escape(fmt_currency(acct.equity_usd))}</span>"
            f"{net_span}"
            "</div>",
            unsafe_allow_html=True,
        )

        st.caption("Quick actions")
        a1, a2, a3, a4 = st.columns(4)
        if a1.button("Start", use_container_width=True, disabled=proc_on):
            start_scheduler_process()
            st.rerun()
        if a2.button("Stop", use_container_width=True, disabled=not proc_on):
            stop_scheduler_process()
            st.rerun()
        toggle_enabled = sched_on
        if a3.button("Pause auto" if toggle_enabled else "Resume auto", use_container_width=True):
            scheduler_set_enabled(not toggle_enabled)
            st.rerun()
        if a4.button("Reset UI", use_container_width=True, help="Clear cached plan / trace in this browser session"):
            for k in ("last_plan", "plan_error", "cycle_trace", "preview_verdicts", "exec_log"):
                st.session_state.pop(k, None)
            st.rerun()

        st.markdown("<p class='panel-sub' style='margin:8px 0 4px 0'>Recent activity</p>", unsafe_allow_html=True)
        rows = _tail_jsonl(project_root() / "data" / "journal" / "actions.jsonl", 12)
        if not rows:
            st.markdown("<div class='activity-feed'>No journal entries yet.</div>", unsafe_allow_html=True)
        else:
            parts: list[str] = []
            for r in reversed(rows):
                ts = escape(str(r.get("ts") or r.get("time") or "")[:19])
                side = escape(str(r.get("side") or r.get("action") or "—"))
                sym = escape(str(r.get("ticker") or r.get("symbol") or "—"))
                parts.append(f"<div><span class='t'>{ts}</span>{side} · <b>{sym}</b></div>")
            st.markdown("<div class='activity-feed'>" + "".join(parts) + "</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
