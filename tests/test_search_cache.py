import pytest

from scalper.realtime.cache import CachedBroker


class SearchBroker:
    def __init__(self) -> None:
        self.calls = 0

    async def search_symbols(self, query: str) -> list[dict[str, str]]:
        self.calls += 1
        return [{"symbol": "BTC/USDT", "description": "Bitcoin / Tether"}]


@pytest.mark.asyncio
async def test_symbol_search_is_normalized_and_cached() -> None:
    raw = SearchBroker()
    broker = CachedBroker(raw, search_ttl=30)  # type: ignore[arg-type]

    first = await broker.search_symbols("BTC")
    second = await broker.search_symbols(" btc ")

    assert first == second
    assert raw.calls == 1
    assert broker.metrics()["search_requests"] == 1
    assert broker.metrics()["search_cache_hits"] == 1
