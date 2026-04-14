from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_settings, project_root
from .main import run_cycle


def _state_path() -> Path:
    p = project_root() / "data" / "runtime_scheduler.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _load_state() -> dict[str, Any]:
    p = _state_path()
    if not p.exists():
        return {
            "day": _today(),
            "runs_today": 0,
            "extra_runs_today": 0,
            "last_run_ts": None,
            "last_max_confidence": 0.0,
            "last_reason": None,
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "day": _today(),
            "runs_today": 0,
            "extra_runs_today": 0,
            "last_run_ts": None,
            "last_max_confidence": 0.0,
            "last_reason": None,
        }


def _save_state(st: dict[str, Any]) -> None:
    _state_path().write_text(json.dumps(st, indent=2), encoding="utf-8")


def _minutes_since(ts: str | None) -> float:
    if not ts:
        return 1e9
    try:
        then = datetime.fromisoformat(ts)
    except ValueError:
        return 1e9
    return (datetime.now(timezone.utc) - then).total_seconds() / 60.0


def run_scheduler_forever() -> None:
    print("Scheduler started.", flush=True)
    while True:
        s = load_settings()
        st = _load_state()
        today = _today()
        if st.get("day") != today:
            st = {
                "day": today,
                "runs_today": 0,
                "extra_runs_today": 0,
                "last_run_ts": st.get("last_run_ts"),
                "last_max_confidence": st.get("last_max_confidence", 0.0),
                "last_reason": st.get("last_reason"),
            }

        reason: str | None = None
        if int(st.get("runs_today", 0)) < 1:
            reason = "daily_minimum"
        else:
            max_conf = float(st.get("last_max_confidence") or 0.0)
            gap_ok = _minutes_since(st.get("last_run_ts")) >= s.scheduler_min_gap_minutes
            extra_ok = int(st.get("extra_runs_today", 0)) < s.scheduler_max_extra_runs_per_day
            if (
                max_conf >= s.scheduler_confidence_threshold
                and gap_ok
                and extra_ok
            ):
                reason = "high_confidence_follow_up"

        if reason:
            print(f"[{_now_iso()}] Triggering cycle: {reason}", flush=True)
            result = run_cycle(s)
            if not result.get("ok"):
                print(f"[{_now_iso()}] Cycle failed: {result.get('error')}", flush=True)
            else:
                st["runs_today"] = int(st.get("runs_today", 0)) + 1
                if reason != "daily_minimum":
                    st["extra_runs_today"] = int(st.get("extra_runs_today", 0)) + 1
                st["last_max_confidence"] = float(result.get("max_confidence") or 0.0)
                st["last_run_ts"] = _now_iso()
                st["last_reason"] = reason
                print(
                    f"[{_now_iso()}] Cycle complete. max_confidence={st['last_max_confidence']:.3f}",
                    flush=True,
                )
                for line in result.get("warnings") or []:
                    print(f"[warn] {line}", flush=True)
                for line in result.get("execution_lines") or []:
                    print(f"[exec] {line}", flush=True)
            _save_state(st)
        else:
            _save_state(st)
            print(
                f"[{_now_iso()}] No run needed. runs_today={st.get('runs_today', 0)} "
                f"last_conf={float(st.get('last_max_confidence') or 0):.3f}",
                flush=True,
            )

        sleep_s = max(60, int(s.scheduler_poll_minutes * 60))
        time.sleep(sleep_s)

