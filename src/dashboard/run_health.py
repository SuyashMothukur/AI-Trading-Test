"""Scheduler + execution health, quick actions, activity feed."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Any

import streamlit as st

from ..config import project_root
from ..scheduler import (
    scheduler_set_enabled,
    scheduler_status,
    start_scheduler_process,
    stop_scheduler_process,
)
from .formatting import fmt_currency, fmt_percent_plain, fmt_signed_currency

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
    def render(ctx: TradingContext, settings: Any) -> None:
        sched_info = scheduler_status()
        sched = sched_info.get("state") or {}
        g = (ctx.user_payload.get("learning_feedback") or {}).get("global") or {}
        wr = g.get("win_rate")
        wr_f = float(wr) if wr is not None else None

        start = ctx.daily_state.session_start_equity_usd
        daily_pnl = float(ctx.account.equity_usd) - float(start) if start else None
        d_tone = "dot-good" if (daily_pnl or 0) > 0 else "dot-bad" if (daily_pnl or 0) < 0 else "dot-neutral"

        n_pos = len(ctx.positions or [])
        last_run = _fmt_ts(str(sched.get("last_run_ts") or ""))

        sr_txt = fmt_percent_plain(wr_f, decimals=1) if wr_f is not None else "—"
        sr_tone = "dot-good" if wr_f is not None and wr_f >= 0.5 else "dot-warn" if wr_f is not None else "dot-neutral"

        st.markdown("<div class='panel run-health-stack'>", unsafe_allow_html=True)
        st.markdown(
            "<div class='panel-head run-health-head'><div><p class='panel-title'>Run health</p>"
            "<p class='panel-sub'>Live ops pulse</p></div></div>",
            unsafe_allow_html=True,
        )

        if daily_pnl is None:
            daily_cell = escape("—")
        elif daily_pnl > 0:
            daily_cell = f"<span class='pl-pos'>{escape(fmt_signed_currency(daily_pnl))}</span>"
        elif daily_pnl < 0:
            daily_cell = f"<span class='pl-neg'>{escape(fmt_signed_currency(daily_pnl))}</span>"
        else:
            daily_cell = escape(fmt_signed_currency(daily_pnl))
        st.markdown(
            "<div class='health-cards'>"
            f"<div class='health-card'><div class='row'><span class='health-k'>Daily P/L</span>"
            f"<span class='health-dot {d_tone}'></span></div>"
            f"<div class='health-v'>{daily_cell}</div></div>"
            f"<div class='health-card'><div class='row'><span class='health-k'>Open positions</span>"
            f"<span class='health-dot dot-neutral'></span></div>"
            f"<div class='health-v'>{n_pos}</div></div>"
            f"<div class='health-card'><div class='row'><span class='health-k'>Last run</span>"
            f"<span class='health-dot dot-neutral'></span></div>"
            f"<div class='health-v' style='font-size:0.82rem'>{escape(last_run)}</div></div>"
            f"<div class='health-card'><div class='row'><span class='health-k'>Win rate</span>"
            f"<span class='health-dot {sr_tone}'></span></div>"
            f"<div class='health-v'>{escape(sr_txt)}</div></div>"
            "</div>",
            unsafe_allow_html=True,
        )

        exec_on = bool(getattr(settings, "execute_trades", False))
        sched_on = bool(sched.get("enabled", True))
        proc_on = bool(sched_info.get("running"))
        mode = "Paper" if settings.alpaca_paper else "Live"
        st.markdown(
            "<div class='status-line'>"
            f"<span><b>Bot</b> {'<span class=\"pill pill-on\">ON</span>' if exec_on else '<span class=\"pill pill-off\">EXEC OFF</span>'}</span>"
            f"<span><b>Mode</b> {escape(mode)}</span>"
            f"<span><b>Scheduler</b> {'<span class=\"pill pill-on\">RUNNING</span>' if proc_on else '<span class=\"pill pill-warn\">STOPPED</span>'} "
            f"{'· auto' if sched_on else '· auto paused'}</span>"
            f"<span><b>Equity</b> {escape(fmt_currency(ctx.account.equity_usd))}</span>"
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
