from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import project_root
from .learning import load_actions


def _reports_dir() -> Path:
    p = project_root() / "data" / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _in_day(ts: str | None, day: str) -> bool:
    if not ts:
        return False
    return ts[:10] == day


def write_daily_postmortem(
    *,
    execution_lines: list[str],
    day: str | None = None,
) -> Path:
    d = day or _today_utc()
    rows = load_actions()
    today_rows = [r for r in rows if _in_day(r.get("ts"), d)]
    resolved_today = [r for r in today_rows if r.get("status") == "resolved"]
    pending_today = [r for r in today_rows if r.get("status") == "pending"]

    wins = sum(
        1
        for r in resolved_today
        if float(r.get("realized_return_pct") or 0.0) > 0
    )
    avg_ret = (
        sum(float(r.get("realized_return_pct") or 0.0) for r in resolved_today)
        / len(resolved_today)
        if resolved_today
        else None
    )
    payload: dict[str, Any] = {
        "day_utc": d,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "actions_logged_today": len(today_rows),
        "resolved_today": len(resolved_today),
        "pending_today": len(pending_today),
        "win_rate_today": (wins / len(resolved_today)) if resolved_today else None,
        "avg_return_today": avg_ret,
        "execution_lines_last_cycle": execution_lines,
        "top_mistakes": [
            "High-confidence losses should be reviewed for overfitting to news.",
            "Repeated losses in same symbol/sector should be downweighted.",
        ],
    }
    out_path = _reports_dir() / f"postmortem_{d}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path

