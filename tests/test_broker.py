import asyncio

import pytest

from scalper.broker import OrderError, PrimeXBTBroker, SymbolError


class FakeCaller:
    def __init__(self, demo: bool = True) -> None:
        self.demo = demo
        self.calls: list[tuple[str, dict]] = []

    async def call(self, name: str, args: dict):
        self.calls.append((name, dict(args)))
        if name.endswith("list_accounts"):
            return {
                "accounts": [
                    {
                        "accountId": "D1" if self.demo else "L1",
                        "currency": "USD",
                        "demo": self.demo,
                        "positionMode": "HEDGE",
                        "balance": 1000,
                        "equity": 1000,
                        "availableMargin": 900,
                    }
                ]
            }
        if name.endswith("find_symbol"):
            return {
                "structuredContent": {
                    "symbols": [
                        {"symbol": "XAU/USD"},
                        {"symbol": "XAU/USD.24"},
                    ]
                }
            }
        if name.endswith("get_symbol"):
            return {
                "symbol": "XAU/USD",
                "minQty": 0.01,
                "maxQty": 100,
                "qtyStep": 0.01,
                "minPriceStep": 0.01,
                "priceScale": 2,
            }
        if name.endswith("preview_order"):
            return {"ticket": "ticket-1", "errors": [], "warnings": []}
        if name.endswith("place_order"):
            return {"status": "FILLED"}
        raise AssertionError(f"unexpected tool {name}")


def test_resolve_symbol_requires_exact_match() -> None:
    async def run() -> None:
        broker = PrimeXBTBroker(FakeCaller())
        assert await broker.resolve_symbol("XAU/USD") == "XAU/USD"
        with pytest.raises(SymbolError):
            await broker.resolve_symbol("gold")

    asyncio.run(run())


def test_live_place_is_blocked_by_default() -> None:
    async def run() -> None:
        caller = FakeCaller(demo=False)
        broker = PrimeXBTBroker(caller)
        preview = await broker.preview_order(
            symbol="XAU/USD",
            side="BUY",
            qty=0.01,
            stop_loss=4000,
            take_profit=4100,
            client_order_id="test",
        )
        with pytest.raises(OrderError):
            await broker.place_previewed_order(preview)
        assert not any(name.endswith("place_order") for name, _ in caller.calls)

    asyncio.run(run())


def test_demo_place_uses_preview_ticket_only() -> None:
    async def run() -> None:
        caller = FakeCaller(demo=True)
        broker = PrimeXBTBroker(caller)
        preview = await broker.preview_order(
            symbol="XAU/USD",
            side="BUY",
            qty=0.01,
            stop_loss=4000,
            take_profit=4100,
            client_order_id="test",
        )
        await broker.place_previewed_order(preview)
        assert caller.calls[-1] == (PrimeXBTBroker.PLACE_ORDER, {"ticket": "ticket-1"})

    asyncio.run(run())
