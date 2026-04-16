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
                merged[sym] = [
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
