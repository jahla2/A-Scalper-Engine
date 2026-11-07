# Local PrimeXBT MCP Setup

This mode is for live market reading, deterministic strategy scanning and manual/human-confirmed workflows. PrimeXBT states that MCP is not intended for unattended 24/7 scalping; its PXTrader 2.0 Trade API is the intended backend for a future autonomous execution service.

## Windows install

```powershell
git clone https://github.com/jahla2/A-Scalper-Engine.git
cd A-Scalper-Engine
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
ruff check src tests
Copy-Item .env.example .env
```

## First connection

```powershell
aplus connect
```

The client opens PrimeXBT OAuth in your browser. Sign in, select the PXTrader 2.0 account, and grant the permission appropriate for testing. After authorization, copy the full redirected URL from the browser address bar and paste it into the terminal. OAuth state is stored under `.scalper/`, which is gitignored.

## One live scan

```powershell
aplus scan
```

The engine reads closed 1H, 15M and 5M candles concurrently. It only requests the 1M refinement when the higher-timeframe gates and 5M BOS require it.

## Realtime watcher

```powershell
aplus watch
```

The watcher performs a lightweight three-bar 1M poll every two seconds by default. A full multi-timeframe strategy scan happens only after a newly closed 1M candle is detected.

```text
2s lightweight 1M poll
        |
new closed 1M candle?
   no -> sleep
   yes
        |
        v
1H + 15M + 5M A+ scan
        |
1M refinement only if needed
        |
NO_TRADE / WATCH / TRADE_CANDIDATE
        |
logs/signals.jsonl
```

The MCP local runner never auto-executes a trade. It is intentionally analysis-only because PrimeXBT documents MCP as an AI-assistant/human-confirmed interface rather than an unattended scalping API.

## Account selection

If the OAuth connection exposes more than one account, set the exact account returned by `aplus connect`:

```env
PRIMEXBT_ACCOUNT_ID=D123456
```

Prefer a demo account during development.

## Reset OAuth

```powershell
Remove-Item .scalper\primexbt_oauth.json
aplus connect
```

## Future autonomous backend

The strategy engine is broker-transport independent. A future `PrimeXbtTradeApiBroker` can implement the same methods using the PXTrader 2.0 Trade API without changing EMA/VWAP/ATR/BOS/scoring code. We should implement that only against PrimeXBT's published technical endpoint/auth specification, not guessed URLs or signing rules.
