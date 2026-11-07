from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scalper.api.serializers import chart_payload
from scalper.models import Bar, Quote
from scalper.realtime.cache import CachedBroker
from scalper.realtime.events import EventBus
from scalper.realtime.storage import AnalysisStore


class FakeBroker:
    def __init__(self) -> None:
        self.bar_calls = 0
        self.quote_calls = 0

    async def bars(self, symbol: str, bar_size: str, limit: int) -> list[Bar]:
        self.bar_calls += 1
        return [
            Bar(t=1_700_000_000 + i * 60, open=100, high=102, low=99, close=101, volume=1)
            for i in range(limit)
        ]

    async def quote(self, symbol: str) -> Quote:
        self.quote_calls += 1
        return Quote(symbol, ask=101.0, bid=100.5, price=100.75, market_open=True)

    async def snapshot(self) -> dict[str, Any]:
        return {"equity": 10_000.0}


@pytest.mark.asyncio
async def test_cached_broker_reuses_bar_history() -> None:
    raw = FakeBroker()
    broker = CachedBroker(raw)  # type: ignore[arg-type]
    first = await broker.bars("XAU/USD", "5M", 100)
    second = await broker.bars("XAU/USD", "5M", 50)
    assert len(first) == 100
    assert len(second) == 50
    assert raw.bar_calls == 1


@pytest.mark.asyncio
async def test_refresh_bars_merges_new_data() -> None:
    raw = FakeBroker()
    broker = CachedBroker(raw)  # type: ignore[arg-type]
    await broker.bars("XAU/USD", "1M", 100)
    refreshed = await broker.refresh_bars("XAU/USD", "1M", 3)
    assert len(refreshed) == 100
    assert raw.bar_calls == 2


@pytest.mark.asyncio
async def test_analysis_store_filters(tmp_path: Path) -> None:
    store = AnalysisStore(tmp_path / "analysis.db")
    await store.initialize()
    payload = {
        "timestamp": 1_700_000_000,
        "symbol": "XAU/USD",
        "decision": "WATCH",
        "direction": "LONG",
        "score": {"total": 80, "threshold": 85, "parts": {}},
    }
    await store.append(payload)
    assert await store.latest("XAU/USD") == payload
    history = await store.history(symbol="XAU/USD", min_score=75)
    assert history == [payload]


def test_event_bus_drops_oldest_when_full() -> None:
    bus = EventBus(queue_size=1)
    queue = bus.subscribe()
    bus.publish("one", {"value": 1})
    bus.publish("two", {"value": 2})
    event = queue.get_nowait()
    assert event["type"] == "two"


def test_chart_payload_contains_indicator_series() -> None:
    bars = [
        Bar(t=1_700_000_000 + i * 60, open=100, high=102, low=99, close=101 + i, volume=1)
        for i in range(220)
    ]
    payload = chart_payload(bars, "UTC")
    assert len(payload["bars"]) == 220
    assert len(payload["indicators"]["ema50"]) == 220
    assert len(payload["indicators"]["ema200"]) == 220
    assert len(payload["indicators"]["vwap"]) == 220
