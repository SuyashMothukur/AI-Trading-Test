from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from .config import project_root


@dataclass
class DailyState:
    day: str
    orders_placed: int
    session_start_equity_usd: float | None

    @staticmethod
    def empty_today() -> DailyState:
        today = date.today().isoformat()
        return DailyState(
            day=today, orders_placed=0, session_start_equity_usd=None
        )


def _state_path() -> Path:
    return project_root() / "data" / "runtime_state.json"


def load_daily_state() -> DailyState:
    p = _state_path()
    if not p.exists():
        return DailyState.empty_today()
    data = json.loads(p.read_text(encoding="utf-8"))
    st = DailyState(
        day=data.get("day", ""),
        orders_placed=int(data.get("orders_placed", 0)),
        session_start_equity_usd=(
            float(data["session_start_equity_usd"])
            if data.get("session_start_equity_usd") is not None
            else None
        ),
    )
    today = date.today().isoformat()
    if st.day != today:
        return DailyState.empty_today()
    return st


def save_daily_state(st: DailyState) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(st), indent=2), encoding="utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def bump_orders_placed(count: int = 1) -> DailyState:
    st = load_daily_state()
    st.orders_placed += count
    save_daily_state(st)
    return st


def ensure_session_start_equity(equity_usd: float) -> DailyState:
    st = load_daily_state()
    if st.session_start_equity_usd is None:
        st.session_start_equity_usd = equity_usd
        save_daily_state(st)
    return st
