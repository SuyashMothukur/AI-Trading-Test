from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest


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
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i : i + chunk_size]
            req = StockBarsRequest(
                symbol_or_symbols=chunk,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
            )
            barset = self._data.get_stock_bars(req)
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

    def market_buy_notional(self, symbol: str, notional_usd: float) -> Any:
        order = MarketOrderRequest(
            symbol=symbol,
            notional=round(notional_usd, 2),
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
        return self._trade.submit_order(order_data=order)

    def market_sell_qty(self, symbol: str, qty: float) -> Any:
        order = MarketOrderRequest(
            symbol=symbol,
            qty=round(qty, 6),
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        return self._trade.submit_order(order_data=order)
