from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import project_root


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _journal_dir() -> Path:
    p = project_root() / "data" / "journal"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cycles_path() -> Path:
    return _journal_dir() / "cycles.jsonl"


def _actions_path() -> Path:
    return _journal_dir() / "actions.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    payload = "\n".join(json.dumps(r, separators=(",", ":")) for r in rows)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _last_close_from_payload(payload: dict[str, Any], ticker: str) -> float | None:
    bars = (payload.get("bars_by_symbol") or {}).get(ticker) or []
    if not bars:
        return None
    close = bars[-1].get("c")
    if close is None:
        return None
    return float(close)


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def record_cycle_and_actions(
    *,
    payload: dict[str, Any],
    plan: dict[str, Any],
    model: str,
) -> str:
    cycle_id = str(uuid.uuid4())
    now_iso = _now().isoformat()
    _append_jsonl(
        _cycles_path(),
        {
            "cycle_id": cycle_id,
            "ts": now_iso,
            "model": model,
            "context_symbols_count": len(payload.get("context_symbols") or []),
            "positions_count": len(payload.get("open_positions") or []),
            "action_count": len(plan.get("actions") or []),
            "payload": payload,
            "plan": plan,
        },
    )
    quant_map = {
        str(x.get("ticker") or "").upper(): x
        for x in (payload.get("quant_snapshot") or {}).get("symbol_metrics", [])
    }
    sector_map = payload.get("symbol_metadata") or {}
    regime = ((payload.get("quant_snapshot") or {}).get("market_regime") or {}).get(
        "regime"
    )
    for act in plan.get("actions") or []:
        ticker = str(act.get("ticker") or "").upper()
        side = str(act.get("side") or "hold").lower()
        if not ticker or side == "hold":
            continue
        _append_jsonl(
            _actions_path(),
            {
                "action_id": str(uuid.uuid4()),
                "cycle_id": cycle_id,
                "ts": now_iso,
                "ticker": ticker,
                "side": side,
                "notional_usd": act.get("notional_usd"),
                "qty": act.get("qty"),
                "confidence_0_to_1": act.get("confidence_0_to_1"),
                "horizon": act.get("horizon"),
                "risk": act.get("risk"),
                "decision_price": _last_close_from_payload(payload, ticker),
                "sector": (sector_map.get(ticker) or {}).get("sector", "Unknown"),
                "regime_at_decision": regime,
                "mom_5d_at_decision": (quant_map.get(ticker) or {}).get("mom_5d"),
                "vol_10d_at_decision": (quant_map.get(ticker) or {}).get("vol_10d"),
                "status": "pending",
                "resolved_ts": None,
                "realized_return_pct": None,
                "rationale": act.get("rationale"),
            },
        )
    return cycle_id


def evaluate_pending_actions(
    *,
    broker: Any,
    eval_delay_hours: int,
) -> dict[str, Any]:
    rows = _read_jsonl(_actions_path())
    if not rows:
        return {"resolved": 0, "pending": 0}
    now = _now()
    resolved = 0
    pending = 0
    for row in rows:
        if row.get("status") != "pending":
            continue
        pending += 1
        created = _parse_ts(row.get("ts"))
        px0 = row.get("decision_price")
        ticker = str(row.get("ticker") or "").upper()
        if not created or px0 is None or px0 <= 0 or not ticker:
            continue
        if now < created + timedelta(hours=eval_delay_hours):
            continue
        try:
            bars = broker.recent_daily_bars([ticker], days=7).get(ticker) or []
        except Exception:
            continue
        if not bars:
            continue
        latest = float(bars[-1]["c"])
        raw_ret = (latest - float(px0)) / float(px0)
        if str(row.get("side")) == "sell":
            raw_ret = -raw_ret
        row["realized_return_pct"] = raw_ret
        row["status"] = "resolved"
        row["resolved_ts"] = now.isoformat()
        resolved += 1
    _write_jsonl(_actions_path(), rows)
    return {"resolved": resolved, "pending": sum(1 for r in rows if r.get("status") == "pending")}


def build_learning_snapshot(min_samples: int) -> dict[str, Any]:
    rows = _read_jsonl(_actions_path())
    resolved = [r for r in rows if r.get("status") == "resolved" and r.get("realized_return_pct") is not None]
    if not resolved:
        return {
            "global": {"resolved_actions": 0, "avg_return_pct": None, "win_rate": None},
            "symbol_priors": [],
            "notes": "No resolved action outcomes yet.",
        }
    global_avg = sum(float(r["realized_return_pct"]) for r in resolved) / len(resolved)
    wins = sum(1 for r in resolved if float(r["realized_return_pct"]) > 0)

    by_symbol: dict[str, list[float]] = defaultdict(list)
    for r in resolved:
        by_symbol[str(r["ticker"]).upper()].append(float(r["realized_return_pct"]))

    priors: list[dict[str, Any]] = []
    for sym, vals in by_symbol.items():
        n = len(vals)
        avg = sum(vals) / n
        win = sum(1 for v in vals if v > 0) / n
        priors.append(
            {
                "ticker": sym,
                "samples": n,
                "avg_return_pct": avg,
                "win_rate": win,
                "confidence": "high" if n >= max(min_samples * 2, 6) else ("medium" if n >= min_samples else "low"),
            }
        )
    priors.sort(key=lambda x: (x["confidence"], x["avg_return_pct"]), reverse=True)
    return {
        "global": {
            "resolved_actions": len(resolved),
            "avg_return_pct": global_avg,
            "win_rate": wins / len(resolved),
        },
        "symbol_priors": priors[:40],
        "notes": "Use high/medium priors as soft ranking hints, never as hard guarantees.",
    }


def load_actions(limit: int | None = None) -> list[dict[str, Any]]:
    rows = _read_jsonl(_actions_path())
    rows.sort(key=lambda r: r.get("ts", ""), reverse=True)
    if limit is not None:
        return rows[:limit]
    return rows


def build_learning_report(min_samples: int = 3) -> dict[str, Any]:
    rows = load_actions()
    resolved = [
        r
        for r in rows
        if r.get("status") == "resolved" and r.get("realized_return_pct") is not None
    ]
    pending = [r for r in rows if r.get("status") == "pending"]
    snapshot = build_learning_snapshot(min_samples)
    priors = snapshot.get("symbol_priors") or []
    top = sorted(priors, key=lambda r: r.get("avg_return_pct", -9), reverse=True)[:10]
    worst = sorted(priors, key=lambda r: r.get("avg_return_pct", 9))[:10]
    recent_resolved = sorted(
        resolved,
        key=lambda r: r.get("resolved_ts") or r.get("ts") or "",
        reverse=True,
    )[:25]

    returns = [float(r.get("realized_return_pct") or 0.0) for r in resolved]
    wins_only = [r for r in returns if r > 0]
    losses_only = [r for r in returns if r < 0]
    avg_win = (sum(wins_only) / len(wins_only)) if wins_only else None
    avg_loss_abs = (
        abs(sum(losses_only) / len(losses_only)) if losses_only else None
    )
    win_rate = (
        (len(wins_only) / len(returns))
        if returns
        else None
    )
    expectancy = None
    if win_rate is not None and avg_win is not None and avg_loss_abs is not None:
        expectancy = win_rate * avg_win - (1.0 - win_rate) * avg_loss_abs
    gross_win = sum(wins_only) if wins_only else None
    gross_loss_abs = abs(sum(losses_only)) if losses_only else None
    profit_factor = None
    if gross_win is not None and gross_loss_abs:
        profit_factor = gross_win / gross_loss_abs
    payoff_ratio = None
    if avg_win is not None and avg_loss_abs:
        payoff_ratio = avg_win / avg_loss_abs if avg_loss_abs > 0 else None

    def _bucket_stats(rows_in: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        buckets: dict[str, list[float]] = defaultdict(list)
        for r in rows_in:
            k = str(r.get(key) or "unknown")
            buckets[k].append(float(r.get("realized_return_pct") or 0.0))
        out: list[dict[str, Any]] = []
        for k, vals in buckets.items():
            wins = sum(1 for v in vals if v > 0)
            out.append(
                {
                    key: k,
                    "samples": len(vals),
                    "avg_return_pct": (sum(vals) / len(vals)) if vals else None,
                    "win_rate": (wins / len(vals)) if vals else None,
                }
            )
        return sorted(out, key=lambda x: x.get("avg_return_pct") or -9, reverse=True)
    return {
        "global": {
            **(snapshot.get("global") or {}),
            "pending_actions": len(pending),
            "total_logged_actions": len(rows),
            "avg_win_pct": avg_win,
            "avg_loss_pct_abs": avg_loss_abs,
            "expectancy_pct": expectancy,
            "profit_factor": profit_factor,
            "payoff_ratio": payoff_ratio,
        },
        "top_symbols": top,
        "worst_symbols": worst,
        "recent_resolved_actions": recent_resolved,
        "by_side": _bucket_stats(resolved, "side"),
        "by_regime": _bucket_stats(resolved, "regime_at_decision"),
        "by_horizon": _bucket_stats(resolved, "horizon"),
    }

