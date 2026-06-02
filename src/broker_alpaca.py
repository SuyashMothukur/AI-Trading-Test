from __future__ import annotations

from decimal import ROUND_DOWN, Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from alpaca.data.enums import DataFeed
from alpaca.data.requests import NewsRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import GetPortfolioHistoryRequest, MarketOrderRequest


@dataclass
class AccountView:
    equity_usd: float
    buying_power_usd: float
    cash_usd: float


def _f(x: Any) -> float:
    if x is None:
        return 0.0
    return float(x)


class AlpacaBroker:
    def __init__(self, api_key: str, secret_key: str, paper: bool) -> None:
        self._trade = TradingClient(api_key, secret_key, paper=paper)
        self._data = StockHistoricalDataClient(api_key, secret_key)
        self._news = NewsClient(api_key, secret_key)

    def account(self) -> AccountView:
        a = self._trade.get_account()
        return AccountView(
            equity_usd=_f(a.equity),
            buying_power_usd=_f(a.buying_power),
            cash_usd=_f(a.cash),
        )

    def positions(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in self._trade.get_all_positions():
            qty_avail = p.qty_available if p.qty_available is not None else p.qty
            out.append(
                {
                    "symbol": p.symbol,
                    "qty": _f(p.qty),
                    "qty_available": _f(qty_avail),
                    "market_value_usd": _f(p.market_value),
                    "avg_entry_price": _f(p.avg_entry_price),
                    "current_price_usd": _f(p.current_price),
                    "unrealized_pl_usd": _f(p.unrealized_pl),
                }
            )
        return out

    def recent_daily_bars(
        self, symbols: list[str], days: int = 10
    ) -> dict[str, list[dict[str, Any]]]:
        if not symbols:
            return {}
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=max(days, 2))
        merged: dict[str, list[dict[str, Any]]] = {}
        chunk_size = 50
        # Prefer IEX feed (works on lower-cost tiers) and gracefully fall back.
        candidate_feeds: list[DataFeed | None] = [DataFeed.IEX, DataFeed.DELAYED_SIP, None]
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i : i + chunk_size]
            last_err: Exception | None = None
            barset = None
            for feed in candidate_feeds:
                try:
                    req = StockBarsRequest(
                        symbol_or_symbols=chunk,
                        timeframe=TimeFrame.Day,
                        start=start,
                        end=end,
                        feed=feed,
                    )
                    barset = self._data.get_stock_bars(req)
                    break
                except Exception as e:  # pragma: no cover - network/API fallback
                    last_err = e
            if barset is None:
                raise RuntimeError(f"Failed to fetch bars for chunk: {last_err}") from last_err
            for sym, bars in barset.data.items():
                key = str(sym).upper()
                merged[key] = [
                    {
                        "t": b.timestamp.isoformat(),
                        "o": b.open,
                        "h": b.high,
                        "l": b.low,
                        "c": b.close,
                        "v": b.volume,
                    }
                    for b in bars[-10:]
                ]
        return merged

    def latest_mark_prices(self, symbols: list[str]) -> dict[str, float]:
        """
        Best-effort reference prices for live MTM vs a past decision_price.
        Uses open-position current_price when available, else last completed hourly bar close,
        else last daily bar close.
        """
        want = sorted({str(s or "").strip().upper() for s in symbols if str(s or "").strip()})
        if not want:
            return {}
        out: dict[str, float] = {}
        for p in self._trade.get_all_positions():
            sym = str(p.symbol or "").upper()
            if sym in want:
                px = _f(p.current_price)
                if px > 0:
                    out[sym] = px
        missing = [s for s in want if s not in out or out.get(s, 0) <= 0]
        if not missing:
            return out

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        candidate_feeds: list[DataFeed | None] = [DataFeed.IEX, DataFeed.DELAYED_SIP, None]
        chunk_size = 50
        for i in range(0, len(missing), chunk_size):
            chunk = missing[i : i + chunk_size]
            barset = None
            last_err: Exception | None = None
            for feed in candidate_feeds:
                try:
                    req = StockBarsRequest(
                        symbol_or_symbols=chunk,
                        timeframe=TimeFrame.Hour,
                        start=start,
                        end=end,
                        feed=feed,
                    )
                    barset = self._data.get_stock_bars(req)
                    break
                except Exception as e:  # pragma: no cover - network/API fallback
                    last_err = e
            if barset is None or not getattr(barset, "data", None):
                continue
            for sym, bars in barset.data.items():
                sym_u = str(sym).upper()
                bl = list(bars)
                if not bl:
                    continue
                c = _f(bl[-1].close)
                if c > 0:
                    out[sym_u] = c

        still = [s for s in want if s not in out or out.get(s, 0) <= 0]
        if still:
            try:
                daily = self.recent_daily_bars(still, days=10)
            except Exception:
                daily = {}
            for sym in still:
                bars = daily.get(sym) or []
                if not bars:
                    continue
                c = _f(bars[-1].get("c"))
                if c > 0:
                    out[str(sym).upper()] = c
        return {k: v for k, v in out.items() if k in want and v > 0}

    def ui_chart_bars(self, symbol: str, ui_timeframe: str) -> tuple[list[dict[str, Any]], str | None]:
        """
        OHLCV bars for the Streamlit trading chart.
        ui_timeframe: 1H | 1D | 1W | 1M (mapped to Alpaca bar sizes).
        """
        sym = (symbol or "").strip().upper()
        if not sym:
            return [], "Missing symbol"

        tf_map: dict[str, tuple[TimeFrame, timedelta]] = {
            "1H": (TimeFrame.Hour, timedelta(days=21)),
            "1D": (TimeFrame.Day, timedelta(days=420)),
            "1W": (TimeFrame.Week, timedelta(days=365 * 6)),
            "1M": (TimeFrame.Month, timedelta(days=365 * 12)),
        }
        tf, lookback = tf_map.get(ui_timeframe, tf_map["1D"])
        end = datetime.now(timezone.utc)
        start = end - lookback

        candidate_feeds: list[DataFeed | None] = [DataFeed.IEX, DataFeed.DELAYED_SIP, None]
        last_err: Exception | None = None
        barset = None
        for feed in candidate_feeds:
            try:
                req = StockBarsRequest(
                    symbol_or_symbols=sym,
                    timeframe=tf,
                    start=start,
                    end=end,
                    feed=feed,
                )
                barset = self._data.get_stock_bars(req)
                break
            except Exception as e:  # pragma: no cover - network/API fallback
                last_err = e
        if barset is None:
            return [], (str(last_err) if last_err else "No bar data")

        bars_list: list[Any] = []
        if hasattr(barset, "data") and barset.data:
            if sym in barset.data:
                bars_list = list(barset.data[sym])
            else:
                for k, v in barset.data.items():
                    if str(k).upper() == sym:
                        bars_list = list(v)
                        break
                if not bars_list:
                    try:
                        bars_list = list(next(iter(barset.data.values())))
                    except StopIteration:
                        bars_list = []

        out = [
            {
                "t": b.timestamp.isoformat(),
                "o": float(b.open),
                "h": float(b.high),
                "l": float(b.low),
                "c": float(b.close),
                "v": float(b.volume or 0.0),
            }
            for b in bars_list
        ]
        return out, None

    def portfolio_history(
        self, period: str = "1M", timeframe: str = "1D"
    ) -> list[dict[str, Any]]:
        """Returns account equity points for charting."""
        req = GetPortfolioHistoryRequest(period=period, timeframe=timeframe)
        history = self._trade.get_portfolio_history(req)
        out: list[dict[str, Any]] = []
        pct = history.profit_loss_pct or []
        for i, ts in enumerate(history.timestamp):
            out.append(
                {
                    "time": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                    "equity_usd": float(history.equity[i]),
                    "profit_loss_usd": float(history.profit_loss[i]),
                    "profit_loss_pct": float(pct[i]) if i < len(pct) and pct[i] is not None else None,
                }
            )
        return out

    def account_fills(
        self,
        *,
        symbol: str | None = None,
        after: datetime | None = None,
        until: datetime | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Raw account FILL activities from Trading API.
        Used by learning to score outcomes from execution prices when possible.
        """
        params: dict[str, Any] = {
            "direction": "asc",
            "page_size": max(1, min(int(page_size), 100)),
        }
        if after is not None:
            params["after"] = after.astimezone(timezone.utc).isoformat()
        if until is not None:
            params["until"] = until.astimezone(timezone.utc).isoformat()
        if symbol:
            params["symbol"] = symbol.upper()

        raw = self._trade.get("/account/activities/FILL", params)
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for r in raw:
            if not isinstance(r, dict):
                continue
            out.append(
                {
                    "id": r.get("id"),
                    "symbol": str(r.get("symbol") or "").upper(),
                    "side": str(r.get("side") or "").lower(),
                    "price": _f(r.get("price")),
                    "qty": _f(r.get("qty")),
                    "transaction_time": r.get("transaction_time"),
                    "order_id": r.get("order_id"),
                }
            )
        return out

    def latest_news(
        self, symbols: list[str], limit: int = 20
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        req = NewsRequest(
            symbols=",".join(symbols[:30]) if symbols else None,
            limit=max(1, min(limit, 50)),
            include_content=False,
        )
        news_set = self._news.get_news(req)
        items = (news_set.data or {}).get("news", []) if hasattr(news_set, "data") else []
        if not items and symbols:
            # Fall back to broad market headlines if symbol-specific call is empty.
            news_set = self._news.get_news(
                NewsRequest(limit=max(1, min(limit, 50)), include_content=False)
            )
            items = (news_set.data or {}).get("news", []) if hasattr(news_set, "data") else []
        out: list[dict[str, Any]] = []
        for n in items[:limit]:
            out.append(
                {
                    "id": n.id,
                    "headline": n.headline,
                    "summary": n.summary,
                    "source": n.source,
                    "created_at": n.created_at.isoformat(),
                    "symbols": n.symbols,
                    "url": n.url,
                }
            )
        return out

    def market_buy_notional(self, symbol: str, notional_usd: float) -> Any:
        order = MarketOrderRequest(
            symbol=symbol,
            notional=round(notional_usd, 2),
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
        return self._trade.submit_order(order_data=order)

    def market_sell_qty(self, symbol: str, qty: float) -> Any:
        safe_qty = float(
            Decimal(str(max(qty, 0.0))).quantize(
                Decimal("0.000001"), rounding=ROUND_DOWN
            )
        )
        order = MarketOrderRequest(
            symbol=symbol,
            qty=safe_qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        return self._trade.submit_order(order_data=order)
