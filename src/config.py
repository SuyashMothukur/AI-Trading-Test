from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_paper: bool
    openai_api_key: str
    openai_model: str
    real_money_ack: str
    execute_trades: bool
    max_order_notional_usd: float
    max_position_notional_usd: float
    max_daily_loss_usd: float
    max_orders_per_day: int
    max_context_symbols: int
    learning_eval_delay_hours: int
    learning_min_samples: int
    news_headlines_limit: int
    news_context_symbols: int
    scheduler_poll_minutes: int
    scheduler_confidence_threshold: float
    scheduler_max_extra_runs_per_day: int
    scheduler_min_gap_minutes: int
    hard_exits_enabled: bool
    stop_loss_pct: float
    take_profit_pct: float
    trailing_stop_pct: float
    trailing_activation_pct: float
    max_hold_days: int
    max_sector_exposure_pct: float
    min_avg_volume_10d: float
    regime_mult_bullish: float
    regime_mult_choppy: float
    regime_mult_bearish: float
    scheduler_enabled: bool
    alert_webhook_url: str
    alert_on_failure: bool
    trade_universe: list[str] | None
    # Execution: minimum model confidence (raised dynamically by regime / learning).
    min_confidence_execute: float
    # Inverse-vol sizing for buys: scale notional so high-vol names take less risk per trade.
    vol_target_daily: float
    vol_target_mult_min: float
    vol_target_mult_max: float
    # When many resolved actions show negative global avg, raise confidence floor slightly.
    learning_derisk_min_resolved: int
    learning_derisk_avg_below: float
    learning_derisk_floor_add: float


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _float(v: str | None, default: float) -> float:
    if v is None or v.strip() == "":
        return default
    return float(v)


def _int(v: str | None, default: int) -> int:
    if v is None or v.strip() == "":
        return default
    return int(v)


def load_settings() -> Settings:
    raw_uni = os.getenv("TRADE_UNIVERSE", "").strip()
    universe = (
        [t.strip().upper() for t in raw_uni.split(",") if t.strip()]
        if raw_uni
        else None
    )
    return Settings(
        alpaca_api_key=os.getenv("ALPACA_API_KEY", "").strip(),
        alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY", "").strip(),
        alpaca_paper=_bool(os.getenv("ALPACA_PAPER"), default=True),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        real_money_ack=os.getenv("REAL_MONEY_ACK", "").strip(),
        execute_trades=_bool(os.getenv("EXECUTE_TRADES"), default=False),
        max_order_notional_usd=_float(os.getenv("MAX_ORDER_NOTIONAL_USD"), 500.0),
        max_position_notional_usd=_float(os.getenv("MAX_POSITION_NOTIONAL_USD"), 5000.0),
        max_daily_loss_usd=_float(os.getenv("MAX_DAILY_LOSS_USD"), 1000.0),
        max_orders_per_day=_int(os.getenv("MAX_ORDERS_PER_DAY"), 20),
        max_context_symbols=_int(os.getenv("MAX_CONTEXT_SYMBOLS"), 40),
        learning_eval_delay_hours=_int(os.getenv("LEARNING_EVAL_DELAY_HOURS"), 24),
        learning_min_samples=_int(os.getenv("LEARNING_MIN_SAMPLES"), 3),
        news_headlines_limit=_int(os.getenv("NEWS_HEADLINES_LIMIT"), 20),
        news_context_symbols=_int(os.getenv("NEWS_CONTEXT_SYMBOLS"), 12),
        scheduler_poll_minutes=_int(os.getenv("SCHEDULER_POLL_MINUTES"), 30),
        scheduler_confidence_threshold=_float(
            os.getenv("SCHEDULER_CONFIDENCE_THRESHOLD"), 0.9
        ),
        scheduler_max_extra_runs_per_day=_int(
            os.getenv("SCHEDULER_MAX_EXTRA_RUNS_PER_DAY"), 3
        ),
        scheduler_min_gap_minutes=_int(os.getenv("SCHEDULER_MIN_GAP_MINUTES"), 90),
        hard_exits_enabled=_bool(os.getenv("HARD_EXITS_ENABLED"), default=True),
        stop_loss_pct=_float(os.getenv("STOP_LOSS_PCT"), 0.06),
        take_profit_pct=_float(os.getenv("TAKE_PROFIT_PCT"), 0.12),
        trailing_stop_pct=_float(os.getenv("TRAILING_STOP_PCT"), 0.05),
        trailing_activation_pct=_float(os.getenv("TRAILING_ACTIVATION_PCT"), 0.03),
        max_hold_days=_int(os.getenv("MAX_HOLD_DAYS"), 15),
        max_sector_exposure_pct=_float(os.getenv("MAX_SECTOR_EXPOSURE_PCT"), 0.35),
        min_avg_volume_10d=_float(os.getenv("MIN_AVG_VOLUME_10D"), 500000.0),
        regime_mult_bullish=_float(os.getenv("REGIME_MULT_BULLISH"), 1.0),
        regime_mult_choppy=_float(os.getenv("REGIME_MULT_CHOPPY"), 0.6),
        regime_mult_bearish=_float(os.getenv("REGIME_MULT_BEARISH"), 0.35),
        scheduler_enabled=_bool(os.getenv("SCHEDULER_ENABLED"), default=True),
        alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL", "").strip(),
        alert_on_failure=_bool(os.getenv("ALERT_ON_FAILURE"), default=False),
        trade_universe=universe,
        min_confidence_execute=_float(os.getenv("MIN_CONFIDENCE_EXECUTE"), 0.55),
        vol_target_daily=_float(os.getenv("VOL_TARGET_DAILY"), 0.015),
        vol_target_mult_min=_float(os.getenv("VOL_TARGET_MULT_MIN"), 0.35),
        vol_target_mult_max=_float(os.getenv("VOL_TARGET_MULT_MAX"), 1.3),
        learning_derisk_min_resolved=_int(os.getenv("LEARNING_DERISK_MIN_RESOLVED"), 24),
        learning_derisk_avg_below=_float(os.getenv("LEARNING_DERISK_AVG_BELOW"), -0.004),
        learning_derisk_floor_add=_float(os.getenv("LEARNING_DERISK_FLOOR_ADD"), 0.05),
    )


def project_root() -> Path:
    return _ROOT


def kill_switch_active() -> bool:
    return (project_root() / "STOP_TRADING").exists()


def validate_order_execution_allowed(s: Settings) -> list[str]:
    """Blocks live-money order submission unless explicit env gates are set."""
    errors: list[str] = []
    if not s.alpaca_api_key or not s.alpaca_secret_key:
        errors.append("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY.")
    if not s.execute_trades:
        return errors
    if s.alpaca_paper:
        return errors
    if s.real_money_ack != "YES_I_ACCEPT_LOSS_RISK":
        errors.append(
            "Live orders blocked: set REAL_MONEY_ACK=YES_I_ACCEPT_LOSS_RISK in .env."
        )
    return errors
