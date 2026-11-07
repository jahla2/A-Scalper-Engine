from __future__ import annotations

import asyncio
from datetime import datetime
from time import monotonic, time
from typing import Any

from ..engine import ScalperEngine
from ..models import Bar, Quote
from ..runtime import DailyLossGuard
from ..timeframes import closed_bars
from .cache import CachedBroker
from .events import EventBus
from .storage import AnalysisStore


class MarketSupervisor:
    """Owns conservative MCP polling and broadcasts cached state to the web UI."""

    def __init__(
        self,
        broker: CachedBroker,
        engine: ScalperEngine,
        store: AnalysisStore,
        events: EventBus,
        *,
        symbol: str,
        quote_poll_seconds: float,
        bar_poll_seconds: float,
        account_poll_seconds: float,
        max_daily_drawdown_pct: float,
    ) -> None:
        self.broker = broker
        self.engine = engine
        self.store = store
        self.events = events
        self.selected_symbol = symbol
        self.quote_poll_seconds = quote_poll_seconds
        self.bar_poll_seconds = bar_poll_seconds
        self.account_poll_seconds = account_poll_seconds
        self.guard = DailyLossGuard(max_daily_drawdown_pct)
        self.latest_quote: Quote | None = None
        self.latest_account: dict[str, Any] = {}
        self.latest_analysis: dict[str, dict[str, Any]] = {}
        self.last_error: str | None = None
        self.last_scan_at: int | None = None
        self.last_scan_source: str | None = None
        self.started_at = int(time())
        self._tasks: list[asyncio.Task[None]] = []
        self._last_closed_1m: dict[str, int] = {}
        self._symbol_lock = asyncio.Lock()
        self._scan_lock = asyncio.Lock()
        self._last_manual_scan: dict[str, float] = {}
        self.manual_scan_cooldown_seconds = 3.0

    async def start(self) -> None:
        self.selected_symbol = await self.broker.resolve_symbol(self.selected_symbol)
        await self._bootstrap(self.selected_symbol)
        await self.scan_now(self.selected_symbol, source="startup")
        self._tasks = [
            asyncio.create_task(self._quote_loop(), name="quote-loop"),
            asyncio.create_task(self._bar_loop(), name="bar-loop"),
            asyncio.create_task(self._account_loop(), name="account-loop"),
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def select_symbol(self, query: str) -> str:
        symbol = await self.broker.resolve_symbol(query)
        async with self._symbol_lock:
            self.selected_symbol = symbol
            self._last_closed_1m.pop(symbol, None)
            await self._bootstrap(symbol)
            await self.scan_now(symbol, source="symbol_change")
        self.events.publish("symbol.changed", {"symbol": symbol})
        return symbol

    def update_runtime(
        self,
        *,
        quote_poll_seconds: float | None = None,
        bar_poll_seconds: float | None = None,
        account_poll_seconds: float | None = None,
        max_daily_drawdown_pct: float | None = None,
    ) -> dict[str, float]:
        values = {
            "quote_poll_seconds": quote_poll_seconds,
            "bar_poll_seconds": bar_poll_seconds,
            "account_poll_seconds": account_poll_seconds,
        }
        for name, value in values.items():
            if value is not None and not 0.5 <= value <= 60:
                raise ValueError(f"{name} must be between 0.5 and 60 seconds")
        if max_daily_drawdown_pct is not None and not 0.1 <= max_daily_drawdown_pct <= 20:
            raise ValueError("max_daily_drawdown_pct must be between 0.1 and 20")

        if quote_poll_seconds is not None:
            self.quote_poll_seconds = quote_poll_seconds
        if bar_poll_seconds is not None:
            self.bar_poll_seconds = bar_poll_seconds
        if account_poll_seconds is not None:
            self.account_poll_seconds = account_poll_seconds
        if max_daily_drawdown_pct is not None:
            self.guard.max_drawdown_pct = max_daily_drawdown_pct

        payload = self.runtime_settings()
        self.events.publish("settings.updated", payload)
        return payload

    def runtime_settings(self) -> dict[str, float]:
        return {
            "quote_poll_seconds": self.quote_poll_seconds,
            "bar_poll_seconds": self.bar_poll_seconds,
            "account_poll_seconds": self.account_poll_seconds,
            "max_daily_drawdown_pct": self.guard.max_drawdown_pct,
        }

    async def manual_scan(self, symbol: str | None = None) -> dict[str, Any]:
        selected = symbol or self.selected_symbol
        now_mono = monotonic()
        previous = self._last_manual_scan.get(selected)
        cached = self.latest_analysis.get(selected)
        if previous is not None and cached is not None:
            age = now_mono - previous
            if age < self.manual_scan_cooldown_seconds:
                response = {
                    **cached,
                    "runtime": {
                        **cached.get("runtime", {}),
                        "scan_source": "manual_cached",
                        "scan_cached": True,
                        "scan_cooldown_remaining": round(
                            self.manual_scan_cooldown_seconds - age,
                            2,
                        ),
                    },
                }
                return response
        self._last_manual_scan[selected] = now_mono
        return await self.scan_now(selected, source="manual")

    async def scan_now(
        self,
        symbol: str | None = None,
        *,
        source: str = "system",
    ) -> dict[str, Any]:
        selected = symbol or self.selected_symbol
        async with self._scan_lock:
            now = int(time())
            signal = await self.engine.scan(selected, now)
            snapshot = await self.broker.snapshot()
            equity = float(snapshot.get("equity", 0.0))
            allowed, drawdown = self.guard.update(equity, now)
            quote = await self.broker.quote(selected)
            payload = signal.to_dict()
            payload["runtime"] = {
                "equity": equity,
                "daily_drawdown_pct": drawdown,
                "risk_guard_allowed": allowed,
                "scan_source": source,
                "scan_cached": False,
            }
            payload["market"] = {
                "open": quote.market_open,
                "bid": quote.bid,
                "ask": quote.ask,
                "price": quote.price,
                "spread": quote.spread,
            }
            self.latest_analysis[selected] = payload
            self.last_scan_at = now
            self.last_scan_source = source
            await self.store.append(payload)
            self.events.publish("analysis.updated", payload)
            return payload

    async def _bootstrap(self, symbol: str) -> None:
        await asyncio.gather(
            self.broker.refresh_bars(symbol, "1M", 150),
            self.broker.refresh_bars(symbol, "5M", 300),
            self.broker.refresh_bars(symbol, "15M", 300),
            self.broker.refresh_bars(symbol, "1H", 300),
            self._refresh_quote(symbol),
            self._refresh_account(),
        )

    async def _refresh_quote(self, symbol: str) -> None:
        quote = await self.broker.refresh_quote(symbol)
        self.latest_quote = quote
        self.events.publish("quote.updated", self._quote_payload(quote))

    async def _refresh_account(self) -> None:
        snapshot = dict(await self.broker.refresh_snapshot())
        self.latest_account = snapshot
        self.events.publish("account.updated", snapshot)

    async def _quote_loop(self) -> None:
        delay = self.quote_poll_seconds
        while True:
            try:
                await self._refresh_quote(self.selected_symbol)
                self.last_error = None
                delay = self.quote_poll_seconds
            except Exception as exc:
                self._record_error("quote", exc)
                delay = min(max(delay * 2, self.quote_poll_seconds), 60.0)
            await asyncio.sleep(delay)

    async def _account_loop(self) -> None:
        delay = self.account_poll_seconds
        while True:
            try:
                await self._refresh_account()
                self.last_error = None
                delay = self.account_poll_seconds
            except Exception as exc:
                self._record_error("account", exc)
                delay = min(max(delay * 2, self.account_poll_seconds), 60.0)
            await asyncio.sleep(delay)

    async def _bar_loop(self) -> None:
        delay = self.bar_poll_seconds
        while True:
            try:
                symbol = self.selected_symbol
                bars = await self.broker.refresh_bars(symbol, "1M", 3)
                now = int(time())
                closed = closed_bars(bars, "1M", now)
                if closed:
                    self.events.publish(
                        "bar.updated",
                        {"symbol": symbol, "timeframe": "1M", "bar": self._bar_payload(bars[-1])},
                    )
                    latest = closed[-1].t
                    previous = self._last_closed_1m.get(symbol)
                    if previous is None or latest > previous:
                        self._last_closed_1m[symbol] = latest
                        self._invalidate_boundaries(symbol, latest + 60)
                        await self.scan_now(symbol, source="candle_close")
                self.last_error = None
                delay = self.bar_poll_seconds
            except Exception as exc:
                self._record_error("bars", exc)
                delay = min(max(delay * 2, self.bar_poll_seconds), 60.0)
            await asyncio.sleep(delay)

    def _invalidate_boundaries(self, symbol: str, close_time: int) -> None:
        self.broker.invalidate_bars(symbol, "1M")
        if close_time % 300 == 0:
            self.broker.invalidate_bars(symbol, "5M")
        if close_time % 900 == 0:
            self.broker.invalidate_bars(symbol, "15M")
        if close_time % 3600 == 0:
            self.broker.invalidate_bars(symbol, "1H")

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok" if self.last_error is None else "degraded",
            "selected_symbol": self.selected_symbol,
            "started_at": self.started_at,
            "last_scan_at": self.last_scan_at,
            "last_scan_source": self.last_scan_source,
            "last_error": self.last_error,
            "websocket_clients": self.events.subscriber_count,
            "mcp_requests": self.broker.metrics(),
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "health": self.health(),
            "quote": self._quote_payload(self.latest_quote) if self.latest_quote else None,
            "account": self.latest_account,
            "analysis": self.latest_analysis.get(self.selected_symbol),
        }

    def _record_error(self, source: str, exc: Exception) -> None:
        self.last_error = f"{source}: {exc}"
        self.events.publish(
            "system.error",
            {"source": source, "message": str(exc), "at": int(time())},
        )

    @staticmethod
    def _bar_payload(bar: Bar) -> dict[str, Any]:
        return {
            "time": bar.t,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }

    @staticmethod
    def _quote_payload(quote: Quote) -> dict[str, Any]:
        return {
            "symbol": quote.symbol,
            "bid": quote.bid,
            "ask": quote.ask,
            "price": quote.price,
            "spread": quote.spread,
            "market_open": quote.market_open,
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
