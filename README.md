# A+ Scalper Engine

A deterministic, multi-timeframe scalping engine designed for **XAU/USD first** and built to run behind an agent/MCP host.

The strategy is intentionally rule-based: the agent orchestrates data and broker tools, while the engine decides from explicit, testable rules. It does **not** treat an LLM opinion as a trading signal.

## Strategy flow

```text
1H regime
  -> 15M location
  -> 5M BOS + displacement + retest
  -> 1M execution refinement
  -> A+ score
  -> structural SL / RR check
  -> PrimeXBT preview
  -> explicit approval
  -> PrimeXBT ticket execution
```

### Timeframe responsibilities

| Timeframe | Responsibility |
| --- | --- |
| 1H | Trend/regime permission using EMA50, EMA200 and HH/HL or LH/LL structure |
| 15M | Pullback/location using EMA50, session VWAP and nearby structure |
| 5M | Core confirmation: body-close BOS, displacement and retest |
| 1M | Optional micro-structure confirmation; never overrides higher timeframes |

## Design goals

- Fast hot path: standard-library Python, no pandas/numpy in realtime evaluation.
- Closed-candle logic: forming bars are removed before strategy evaluation.
- Fail closed: no trade on neutral regime, invalid location, poor RR, excessive spread or closed market.
- Exact symbol resolution: `XAU/USD` cannot silently become `XAU/USD.24`.
- PrimeXBT contract safety: account discovery first, account-specific quote/specs, preview-before-write tickets.
- No write retries: unknown broker write outcomes are reconciled instead of repeated.
- Live execution disabled by default.
- No guessed position sizing: risk-based quantity requires a verified broker contract-value multiplier.

## Package layout

```text
src/scalper/
  broker.py       PrimeXBT MCP boundary and write safety
  config.py       Strategy/risk configuration
  engine.py       Async top-down orchestrator
  indicators.py   EMA, ATR, VWAP
  journal.py      Non-blocking JSONL journal
  models.py       Small immutable domain models
  risk.py         Structural stop, RR, optional verified sizing
  service.py      Thin application service
  session.py      Low-weight session context
  strategy.py     Regime/setup/scoring rules
  structure.py    Swings, HH/HL, LH/LL, BOS/retest
  timeframes.py   Closed-candle filtering
```

## Install and test

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
pytest
ruff check src tests
```

## PrimeXBT MCP integration

The Python package does not hard-code a transport. The agent host injects a `ToolCaller` that can invoke the available MCP tools. The broker adapter uses these exact PrimeXBT operations:

- `list_accounts`
- `find_symbol`
- `get_symbol`
- `get_bars`
- `get_quotes`
- `get_account_snapshot`
- `list_positions`
- `list_orders`
- `preview_order` -> `place_order(ticket)`
- `preview_position_protection` -> `set_position_protection(ticket)`
- `preview_close_position` -> `close_position(ticket)`
- `list_order_history` for reconciliation

See [`docs/MCP_INTEGRATION.md`](docs/MCP_INTEGRATION.md).

## Position sizing

The engine computes the **risk budget** and structural stop distance, but it deliberately will not infer contract value from leverage/margin. `quantity_from_contract_value()` requires a verified `contract_value_per_price_unit` before it can size automatically.

This is a safety requirement, not a missing formula: broker quantity units can differ across CFD products, and the current MCP symbol metadata exposes quantity bounds/step but not a contract multiplier.

## Current status

V1 includes the complete deterministic signal path, MCP broker adapter, preview/write safety, position-protection primitives, journaling and unit tests. The next research layer is historical/walk-forward testing and parameter calibration before enabling live execution.

Trading involves risk. Backtests and strategy scores are not guarantees of future profitability.
