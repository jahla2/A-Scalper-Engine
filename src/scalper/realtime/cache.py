from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Mapping
from time import monotonic
from typing import Any

from ..broker import Account, PrimeXBTBroker
from ..models import Bar, Quote, SymbolInfo


class CachedBroker:
    """Read-through cache around PrimeXBTBroker for UI and strategy consumers."""

    def __init__(
        self,
        broker: PrimeXBTBroker,
        *,
        quote_ttl: float = 1.5,
        snapshot_ttl: float = 5.0,
        search_ttl: float = 30.0,
        max_bars_per_series: int = 1000,
    ) -> None:
        self._broker = broker
        self._quote_ttl = quote_ttl
        self._snapshot_ttl = snapshot_ttl
        self._search_ttl = search_ttl
        self._max_bars = max_bars_per_series
        self._resolved_symbols: dict[str, str] = {}
        self._symbol_info: dict[str, SymbolInfo] = {}
        self._searches: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._search_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._bars: dict[tuple[str, str], list[Bar]] = {}
        self._bar_locks: defaultdict[tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)
        self._quotes: dict[str, tuple[float, Quote]] = {}
        self._snapshot: tuple[float, Mapping[str, Any]] | None = None
        self._metrics = {
            "bar_cache_hits": 0,
            "bar_requests": 0,
            "quote_cache_hits": 0,
            "quote_requests": 0,
            "snapshot_cache_hits": 0,
            "snapshot_requests": 0,
            "search_cache_hits": 0,
            "search_requests": 0,
        }

    async def account(self) -> Account:
        return await self._broker.account()

    async def resolve_symbol(self, query: str) -> str:
        cached = self._resolved_symbols.get(query)
        if cached:
            return cached
        value = await self._broker.resolve_symbol(query)
        self._resolved_symbols[query] = value
        self._resolved_symbols[value] = value
        return value

    async def search_symbols(self, query: str) -> list[dict[str, Any]]:
        key = query.strip().lower()
        if not key:
            return []

        now = monotonic()
        cached = self._searches.get(key)
        if cached and cached[0] > now:
            self._metrics["search_cache_hits"] += 1
            return [dict(item) for item in cached[1]]

        async with self._search_locks[key]:
            cached = self._searches.get(key)
            if cached and cached[0] > monotonic():
                self._metrics["search_cache_hits"] += 1
                return [dict(item) for item in cached[1]]

            self._metrics["search_requests"] += 1
            items = await self._broker.search_symbols(query.strip())
            copied = [dict(item) for item in items]
            self._searches[key] = (monotonic() + self._search_ttl, copied)
            return [dict(item) for item in copied]

    async def symbol_info(self, symbol: str) -> SymbolInfo:
        cached = self._symbol_info.get(symbol)
        if cached:
            return cached
        value = await self._broker.symbol_info(symbol)
        self._symbol_info[symbol] = value
        return value

    async def bars(self, symbol: str, bar_size: str, limit: int) -> list[Bar]:
        key = (symbol, bar_size)
        cached = self._bars.get(key)
        if cached and len(cached) >= limit:
            self._metrics["bar_cache_hits"] += 1
            return list(cached[-limit:])
        async with self._bar_locks[key]:
            cached = self._bars.get(key)
            if cached and len(cached) >= limit:
                self._metrics["bar_cache_hits"] += 1
                return list(cached[-limit:])
            self._metrics["bar_requests"] += 1
            fetched = await self._broker.bars(symbol, bar_size, limit)
            self._bars[key] = self._merge_bars(cached or [], fetched)
            return list(self._bars[key][-limit:])

    async def refresh_bars(self, symbol: str, bar_size: str, limit: int) -> list[Bar]:
        key = (symbol, bar_size)
        async with self._bar_locks[key]:
            self._metrics["bar_requests"] += 1
            fetched = await self._broker.bars(symbol, bar_size, limit)
            self._bars[key] = self._merge_bars(self._bars.get(key, []), fetched)
            return list(self._bars[key])

    def invalidate_bars(self, symbol: str, bar_size: str) -> None:
        self._bars.pop((symbol, bar_size), None)

    async def quote(self, symbol: str) -> Quote:
        now = monotonic()
        cached = self._quotes.get(symbol)
        if cached and cached[0] > now:
            self._metrics["quote_cache_hits"] += 1
            return cached[1]
        return await self.refresh_quote(symbol)

    async def refresh_quote(self, symbol: str) -> Quote:
        self._metrics["quote_requests"] += 1
        value = await self._broker.quote(symbol)
        self._quotes[symbol] = (monotonic() + self._quote_ttl, value)
        return value

    async def snapshot(self) -> Mapping[str, Any]:
        now = monotonic()
        if self._snapshot and self._snapshot[0] > now:
            self._metrics["snapshot_cache_hits"] += 1
            return self._snapshot[1]
        return await self.refresh_snapshot()

    async def refresh_snapshot(self) -> Mapping[str, Any]:
        self._metrics["snapshot_requests"] += 1
        value = await self._broker.snapshot()
        self._snapshot = (monotonic() + self._snapshot_ttl, value)
        return value

    async def has_symbol_exposure(self, symbol: str) -> bool:
        return await self._broker.has_symbol_exposure(symbol)

    async def preview_order(self, **kwargs: Any) -> Mapping[str, Any]:
        return await self._broker.preview_order(**kwargs)

    async def place_previewed_order(self, preview: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._broker.place_previewed_order(preview)

    def metrics(self) -> dict[str, int]:
        return dict(self._metrics)

    def _merge_bars(self, current: list[Bar], incoming: list[Bar]) -> list[Bar]:
        merged = {bar.t: bar for bar in current}
        merged.update({bar.t: bar for bar in incoming})
        ordered = [merged[timestamp] for timestamp in sorted(merged)]
        return ordered[-self._max_bars :]
