# PrimeXBT MCP Integration

## Boundary

`PrimeXBTBroker` depends on a small `ToolCaller` protocol:

```python
class ToolCaller(Protocol):
    async def call(self, name: str, args: Mapping[str, Any]) -> Mapping[str, Any]: ...
```

The agent/runtime supplies the transport. This keeps the strategy independent from ChatGPT, a particular MCP SDK, or a future broker.

## Read flow

1. `list_accounts()` is always the source of the account ID.
2. `find_symbol(query)` resolves user text.
3. The adapter requires an exact symbol match (for example `XAU/USD`).
4. `get_symbol(accountId, symbol)` supplies min/max quantity, quantity step and tick size.
5. 1H/15M/5M bars, quote and account snapshot are fetched concurrently.
6. 1M bars are fetched only after a valid 5M BOS, reducing MCP calls and latency.

Read transport failures can be retried with short exponential backoff.

## Order flow

```text
signal
  -> exposure check
  -> preview_order(..., SL, TP, clientOrderId)
  -> validate errors == [] and ticket exists
  -> human/host approval
  -> place_order({ticket})
```

`place_order` is never retried automatically. If its result is unclear, reconcile using `list_order_history(clientOrderId=...)` rather than submitting another order.

## Protection flow

Moving SL/TP uses the broker's declarative position-protection API:

```text
preview_position_protection(positionId, takeProfit, stopLoss)
  -> ticket
  -> set_position_protection(ticket)
```

Do not cancel a protective order just to move a stop; that can leave the position unprotected.

## Close flow

```text
preview_close_position(positionId)
  -> ticket
  -> close_position(ticket)
```

Again, no retry is performed on the write.

## Live safety

`allow_live_execution=False` by default. A live account may be used for read-only analysis and previews, but `place_order`, protection writes, and closing writes are blocked until the host explicitly enables live execution.

No credentials, account IDs or tickets are stored in the repository.
