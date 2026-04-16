from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import project_root


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path() -> Path:
    p = project_root() / "data" / "position_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_position_state() -> dict[str, Any]:
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_position_state(state: dict[str, Any]) -> None:
    _path().write_text(json.dumps(state, indent=2), encoding="utf-8")


def sync_position_state(
    *,
    positions: list[dict[str, Any]],
    symbol_metadata: dict[str, dict[str, str]],
) -> dict[str, Any]:
    state = load_position_state()
    active = {str(p.get("symbol") or "").upper() for p in positions}
    state = {k: v for k, v in state.items() if k in active}

    for p in positions:
        sym = str(p.get("symbol") or "").upper()
        if not sym:
            continue
        px = float(p.get("current_price_usd") or p.get("avg_entry_price") or 0.0)
        if sym not in state:
            state[sym] = {
                "opened_at": _now_iso(),
                "high_watermark": px,
                "sector": (symbol_metadata.get(sym) or {}).get("sector", "Unknown"),
            }
        else:
            hw = float(state[sym].get("high_watermark") or px)
            state[sym]["high_watermark"] = max(hw, px)
            if "sector" not in state[sym]:
                state[sym]["sector"] = (
                    (symbol_metadata.get(sym) or {}).get("sector", "Unknown")
                )
    save_position_state(state)
    return state

