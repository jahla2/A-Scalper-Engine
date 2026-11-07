from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .models import Bar, Quote, SymbolInfo


class ToolCaller(Protocol):
    async def call(self, name: str, args: Mapping[str, Any]) -> Mapping[str, Any]: ...


class BrokerError(RuntimeError):
    pass


class SymbolError(BrokerError):
    pass


class OrderError(BrokerError):
    pass


class FunctionToolCaller:
    """Small adapter for agent hosts that expose one async tool-call function."""

    def __init__(self, fn: Callable[[str, Mapping[str, Any]], Awaitable[Mapping[str, Any]]]):
        self._fn = fn

    async def call(self, name: str, args: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._fn(name, args)


@dataclass(frozen=True, slots=True)
class Account:
    account_id: str
    demo: bool
    currency: str
    equity: float
    available_margin: float
    position_mode: str


class PrimeXBTBroker:
    LIST_ACCOUNTS = "mcp__PrimeXBT__list_accounts"
    FIND_SYMBOL = "mcp__PrimeXBT__find_symbol"
    GET_SYMBOL = "mcp__PrimeXBT__get_symbol"
    GET_BARS = "mcp__PrimeXBT__get_bars"
    GET_QUOTES = "mcp__PrimeXBT__get_quotes"
    GET_SNAPSHOT = "mcp__PrimeXBT__get_account_snapshot"
    GET_ORDERS = "mcp__PrimeXBT__list_orders"
    GET_POSITIONS = "mcp__PrimeXBT__list_positions"
    ORDER_HISTORY = "mcp__PrimeXBT__list_order_history"
    PREVIEW_ORDER = "mcp__PrimeXBT__preview_order"
    PLACE_ORDER = "mcp__PrimeXBT__place_order"
    PREVIEW_PROTECTION = "mcp__PrimeXBT__preview_position_protection"
    SET_PROTECTION = "mcp__PrimeXBT__set_position_protection"
    PREVIEW_CLOSE = "mcp__PrimeXBT__preview_close_position"
    CLOSE_POSITION = "mcp__PrimeXBT__close_position"

    def __init__(
        self,
        caller: ToolCaller,
        account_id: str | None = None,
        *,
        allow_live_execution: bool = False,
        read_retries: int = 2,
    ) -> None:
        self._caller = caller
        self._account_id = account_id
        self._allow_live_execution = allow_live_execution
        self._read_retries = max(0, read_retries)
        self._account: Account | None = None

    @staticmethod
    def _payload(result: Mapping[str, Any]) -> Mapping[str, Any]:
        value: Any = result
        if "result" in value and isinstance(value["result"], Mapping):
            value = value["result"]
        if "structuredContent" in value and isinstance(value["structuredContent"], Mapping):
            value = value["structuredContent"]
        return value

    async def _read(self, name: str, args: Mapping[str, Any]) -> Mapping[str, Any]:
        error: Exception | None = None
        for attempt in range(self._read_retries + 1):
            try:
                return await self._caller.call(name, args)
            except Exception as exc:  # transport failures only; writes are never retried
                error = exc
                if attempt < self._read_retries:
                    await asyncio.sleep(0.05 * (2**attempt))
        raise BrokerError(f"read tool {name} failed") from error

    async def account(self) -> Account:
        if self._account is not None:
            return self._account
        payload = self._payload(await self._read(self.LIST_ACCOUNTS, {}))
        accounts = payload.get("accounts", [])
        if not accounts:
            raise BrokerError("PrimeXBT returned no accessible trading accounts")
        selected = None
        if self._account_id:
            selected = next((a for a in accounts if a.get("accountId") == self._account_id), None)
            if selected is None:
                raise BrokerError("configured PrimeXBT account was not returned by list_accounts")
        else:
            selected = next((a for a in accounts if a.get("demo") is True), accounts[0])
        self._account = Account(
            account_id=str(selected["accountId"]),
            demo=bool(selected.get("demo", False)),
            currency=str(selected.get("currency", "USD")),
            equity=float(selected.get("equity", selected.get("balance", 0.0))),
            available_margin=float(selected.get("availableMargin", 0.0)),
            position_mode=str(selected.get("positionMode", "UNKNOWN")),
        )
        return self._account

    async def resolve_symbol(self, query: str) -> str:
        payload = self._payload(await self._read(self.FIND_SYMBOL, {"query": query}))
        symbols = payload.get("symbols", [])
        exact = [str(item.get("symbol")) for item in symbols if item.get("symbol") == query]
        if len(exact) == 1:
            return exact[0]
        if not exact:
            choices = [str(item.get("symbol")) for item in symbols]
            raise SymbolError(f"no exact symbol match for {query!r}; candidates={choices}")
        raise SymbolError(f"ambiguous exact symbol match for {query!r}")

    async def symbol_info(self, symbol: str) -> SymbolInfo:
        account = await self.account()
        payload = self._payload(
            await self._read(self.GET_SYMBOL, {"accountId": account.account_id, "symbol": symbol})
        )
        return SymbolInfo(
            symbol=str(payload["symbol"]),
            min_qty=float(payload["minQty"]),
            max_qty=float(payload["maxQty"]),
            qty_step=float(payload["qtyStep"]),
            min_price_step=float(payload["minPriceStep"]),
            price_scale=int(payload["priceScale"]),
        )

    async def bars(self, symbol: str, bar_size: str, limit: int) -> list[Bar]:
        payload = self._payload(
            await self._read(self.GET_BARS, {"symbol": symbol, "barSize": bar_size, "limit": limit})
        )
        rows = payload.get("bars", [])
        bars = [
            Bar(
                t=int(row["t"]),
                o=float(row["o"]),
                h=float(row["h"]),
                l=float(row["l"]),
                c=float(row["c"]),
                v=float(row.get("v", 0.0)),
            )
            for row in rows
        ]
        bars.sort(key=lambda bar: bar.t)
        return bars

    async def quote(self, symbol: str) -> Quote:
        account = await self.account()
        payload = self._payload(
            await self._read(self.GET_QUOTES, {"accountId": account.account_id, "symbols": symbol})
        )
        quotes = payload.get("quotes", [])
        match = next((q for q in quotes if q.get("symbol") == symbol), None)
        if match is None:
            raise BrokerError(f"quote not returned for {symbol}")
        return Quote(
            symbol=symbol,
            ask=float(match["ask"]),
            bid=float(match["bid"]),
            price=float(match.get("price", (float(match["ask"]) + float(match["bid"])) / 2)),
            market_open=bool(match.get("marketOpen", True)),
        )

    async def snapshot(self) -> Mapping[str, Any]:
        account = await self.account()
        return self._payload(
            await self._read(self.GET_SNAPSHOT, {"accountId": account.account_id})
        )

    async def has_symbol_exposure(self, symbol: str) -> bool:
        account = await self.account()
        positions_raw, orders_raw = await asyncio.gather(
            self._read(self.GET_POSITIONS, {"accountId": account.account_id}),
            self._read(self.GET_ORDERS, {"accountId": account.account_id}),
        )
        positions = self._payload(positions_raw).get("positions", [])
        orders = self._payload(orders_raw).get("orders", [])
        open_position = any(p.get("symbol") == symbol for p in positions)
        # list_orders returns currently working orders, so any non-protective
        # order for the symbol is treated as existing entry exposure.
        open_entry = any(
            o.get("symbol") == symbol and not o.get("protective", False) for o in orders
        )
        return open_position or open_entry

    async def preview_order(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        stop_loss: float,
        take_profit: float,
        client_order_id: str,
    ) -> Mapping[str, Any]:
        account = await self.account()
        result = await self._caller.call(
            self.PREVIEW_ORDER,
            {
                "accountId": account.account_id,
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                "qty": qty,
                "takeProfit": take_profit,
                "stopLoss": stop_loss,
                "clientOrderId": client_order_id,
            },
        )
        payload = self._payload(result)
        errors = payload.get("errors", [])
        if errors:
            raise OrderError(f"PrimeXBT preview rejected order: {errors}")
        if not payload.get("ticket"):
            raise OrderError("PrimeXBT preview returned no execution ticket")
        return payload

    async def place_previewed_order(self, preview: Mapping[str, Any]) -> Mapping[str, Any]:
        account = await self.account()
        if not account.demo and not self._allow_live_execution:
            raise OrderError(
                "live execution is disabled; preview is allowed but place_order is blocked"
            )
        ticket = preview.get("ticket")
        if not ticket:
            raise OrderError("cannot place an order without the exact preview ticket")
        # Deliberately no retry: an unknown write outcome may already have created an order.
        return await self._caller.call(self.PLACE_ORDER, {"ticket": str(ticket)})

    async def preview_protection(
        self, *, position_id: int, take_profit: float, stop_loss: float
    ) -> Mapping[str, Any]:
        account = await self.account()
        result = await self._caller.call(
            self.PREVIEW_PROTECTION,
            {
                "accountId": account.account_id,
                "positionId": position_id,
                "takeProfit": take_profit,
                "stopLoss": stop_loss,
            },
        )
        payload = self._payload(result)
        if not payload.get("ticket"):
            raise OrderError("PrimeXBT protection preview returned no ticket")
        return payload

    async def apply_previewed_protection(
        self, preview: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        account = await self.account()
        if not account.demo and not self._allow_live_execution:
            raise OrderError("live execution is disabled; protection write is blocked")
        ticket = preview.get("ticket")
        if not ticket:
            raise OrderError("cannot change protection without the exact preview ticket")
        return await self._caller.call(self.SET_PROTECTION, {"ticket": str(ticket)})

    async def preview_close(self, position_id: int) -> Mapping[str, Any]:
        account = await self.account()
        result = await self._caller.call(
            self.PREVIEW_CLOSE,
            {"accountId": account.account_id, "positionId": position_id},
        )
        payload = self._payload(result)
        if not payload.get("ticket"):
            raise OrderError("PrimeXBT close preview returned no ticket")
        return payload

    async def close_previewed_position(
        self, preview: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        account = await self.account()
        if not account.demo and not self._allow_live_execution:
            raise OrderError("live execution is disabled; close_position is blocked")
        ticket = preview.get("ticket")
        if not ticket:
            raise OrderError("cannot close a position without the exact preview ticket")
        return await self._caller.call(self.CLOSE_POSITION, {"ticket": str(ticket)})

    async def order_history(self, symbol: str, client_order_id: str) -> Mapping[str, Any]:
        account = await self.account()
        return self._payload(
            await self._read(
                self.ORDER_HISTORY,
                {
                    "accountId": account.account_id,
                    "symbol": symbol,
                    "limit": 50,
                    "clientOrderId": client_order_id,
                },
            )
        )
