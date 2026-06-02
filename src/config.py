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
    # Recovery controls
    bullish_only_buys: bool
    weak_buy_blocklist: list[str]
    # Dashboard: compare live equity to this funded / starting baseline (USD).
    initial_equity_usd: float
    # Churn control: minimum hours between BUY proposals on the same ticker.
    symbol_cooldown_hours: int
    # Auto-add tickers to buy blocklist when learning prior is weak enough.
    auto_blocklist_min_samples: int
    auto_blocklist_avg_below: float
    # Buys require 5D momentum above this threshold (0 = non-negative only).
    min_mom5_for_buy: float
    # Fetch this many symbol candidates before quant-ranking down to max_context_symbols.
    context_candidate_multiplier: int
    # Cap model plan size and new buys per cycle.
    max_plan_actions: int
    max_buys_per_cycle: int
    # Force exit when position is this far underwater and momentum is weak.
    underwater_exit_pct: float
    # Pause all buys when rolling expectancy is below this (requires enough samples).
    block_buys_roll_exp_below: float
    block_buys_roll_min_samples: int
    # Trend filters (momentum bots: align 5D + 10D before entry).
    min_mom10_for_buy: float
    require_trend_alignment: bool
    # Discretionary SELL dead zone (journal: small exits have negative expectancy).
    sell_dead_zone_min_pct: float
    sell_dead_zone_max_pct: float
    sell_take_profit_min_pct: float
    sell_stop_min_pct: float
    sell_mom5_break_pct: float
    # Risk per trade + ATR stops (industry standard 1–2% risk, 2–3x ATR stop).
    risk_per_trade_pct: float
    use_atr_stops: bool
    atr_stop_mult: float
    use_fractional_kelly: bool
    max_buys_bullish: int
    max_buys_non_bullish: int


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


def _csv_symbols(v: str | None) -> list[str]:
    if not v or not v.strip():
        return []
    return [s.strip().upper() for s in v.split(",") if s.strip()]


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
        bullish_only_buys=_bool(os.getenv("BULLISH_ONLY_BUYS"), default=False),
        weak_buy_blocklist=_csv_symbols(os.getenv("WEAK_BUY_BLOCKLIST")),
        initial_equity_usd=_float(os.getenv("INITIAL_EQUITY_USD"), 100_000.0),
        symbol_cooldown_hours=_int(os.getenv("SYMBOL_COOLDOWN_HOURS"), 48),
        auto_blocklist_min_samples=_int(os.getenv("AUTO_BLOCKLIST_MIN_SAMPLES"), 5),
        auto_blocklist_avg_below=_float(os.getenv("AUTO_BLOCKLIST_AVG_BELOW"), -0.005),
        min_mom5_for_buy=_float(os.getenv("MIN_MOM5_FOR_BUY"), 0.0),
        context_candidate_multiplier=_int(os.getenv("CONTEXT_CANDIDATE_MULTIPLIER"), 4),
        max_plan_actions=_int(os.getenv("MAX_PLAN_ACTIONS"), 10),
        max_buys_per_cycle=_int(os.getenv("MAX_BUYS_PER_CYCLE"), 2),
        underwater_exit_pct=_float(os.getenv("UNDERWATER_EXIT_PCT"), 0.035),
        block_buys_roll_exp_below=_float(os.getenv("BLOCK_BUYS_ROLL_EXP_BELOW"), -0.008),
        block_buys_roll_min_samples=_int(os.getenv("BLOCK_BUYS_ROLL_MIN_SAMPLES"), 15),
        min_mom10_for_buy=_float(os.getenv("MIN_MOM10_FOR_BUY"), 0.0),
        require_trend_alignment=_bool(os.getenv("REQUIRE_TREND_ALIGNMENT"), default=True),
        sell_dead_zone_min_pct=_float(os.getenv("SELL_DEAD_ZONE_MIN_PCT"), -0.015),
        sell_dead_zone_max_pct=_float(os.getenv("SELL_DEAD_ZONE_MAX_PCT"), 0.025),
        sell_take_profit_min_pct=_float(os.getenv("SELL_TAKE_PROFIT_MIN_PCT"), 0.03),
        sell_stop_min_pct=_float(os.getenv("SELL_STOP_MIN_PCT"), -0.02),
        sell_mom5_break_pct=_float(os.getenv("SELL_MOM5_BREAK_PCT"), -0.008),
        risk_per_trade_pct=_float(os.getenv("RISK_PER_TRADE_PCT"), 0.01),
        use_atr_stops=_bool(os.getenv("USE_ATR_STOPS"), default=True),
        atr_stop_mult=_float(os.getenv("ATR_STOP_MULT"), 2.5),
        use_fractional_kelly=_bool(os.getenv("USE_FRACTIONAL_KELLY"), default=True),
        max_buys_bullish=_int(os.getenv("MAX_BUYS_BULLISH"), 2),
        max_buys_non_bullish=_int(os.getenv("MAX_BUYS_NON_BULLISH"), 1),
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
