from __future__ import annotations

from typing import Any

import pytest

from scalper.engine import ScalperEngine
from scalper.models import Bar, Quote, SymbolInfo
from scalper.strategy_catalog import DEFAULT_STRATEGY, get_strategy, list_strategies


class FullScanBroker:
    def __init__(self) -> None:
        self.timeframes: list[str] = []

    async def resolve_symbol(self, query: str) -> str:
        return query

    async def symbol_info(self, symbol: str) -> SymbolInfo:
        return SymbolInfo(symbol, 0.01, 100, 0.01, 0.01, 2)

    async def bars(self, symbol: str, timeframe: str, limit: int) -> list[Bar]:
        self.timeframes.append(timeframe)
        seconds = {"1M": 60, "5M": 300, "15M": 900, "1H": 3600}[timeframe]
        return [
            Bar(
                t=1_700_000_000 + i * seconds,
                open=100,
                high=101,
                low=99,
                close=100,
                volume=10,
            )
            for i in range(limit)
        ]

    async def quote(self, symbol: str) -> Quote:
        return Quote(symbol, ask=100.1, bid=100.0, price=100.05, market_open=True)

    async def snapshot(self) -> dict[str, Any]:
        return {"equity": 10_000.0}


@pytest.mark.asyncio
async def test_scan_fetches_all_four_timeframes_even_when_1h_is_neutral() -> None:
    broker = FullScanBroker()
    engine = ScalperEngine(broker)  # type: ignore[arg-type]
    signal = await engine.scan("BTC/USDT", now=1_800_000_000)

    assert set(broker.timeframes) == {"1H", "15M", "5M", "1M"}
    assert signal.regime.direction.value == "NEUTRAL"
    assert signal.setup.reason != "not evaluated"
    assert signal.structure.reason != "not evaluated"
    assert signal.execution.structure != "UNKNOWN" or signal.bias.direction.value == "NEUTRAL"


def test_strategy_catalog_contains_selectable_modes() -> None:
    items = list_strategies()
    ids = {str(item["strategy_id"]) for item in items}
    assert DEFAULT_STRATEGY in ids
    assert {"ichimoku_mtf", "ema_20_50_pullback", "vwap_momentum"} <= ids
    assert get_strategy("ichimoku_mtf").origin.startswith("Japanese-origin")


def test_engine_rejects_unknown_strategy() -> None:
    with pytest.raises(ValueError):
        ScalperEngine(FullScanBroker(), strategy_id="does-not-exist")  # type: ignore[arg-type]
