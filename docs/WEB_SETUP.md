# Web Dashboard Setup

The web dashboard keeps PrimeXBT MCP credentials and traffic inside the Python backend.
The React browser never connects to PrimeXBT directly.

## Architecture

```text
React UI :5173
    |
    | REST + WebSocket
    v
FastAPI :8000
    |
    +-- one shared PrimeXBT MCP session
    +-- cached OHLCV / quote / account reads
    +-- A+ strategy engine
    +-- SQLite analysis history
    +-- adaptive polling and backoff
```

## 1. Backend

Use the same Python environment and Demo OAuth created in SETUP.md.

```powershell
cd E:\Project\Tradde\A-Scalper-Engine
.\.venv\Scripts\Activate.ps1
git pull origin main
pip install -e ".[dev]"
```

Make sure `.env` contains your Demo account:

```env
PRIMEXBT_ACCOUNT_ID=D1334618
SCALPER_REQUIRE_DEMO=true

SCALPER_QUOTE_POLL_SECONDS=2.0
SCALPER_BAR_POLL_SECONDS=5.0
SCALPER_ACCOUNT_POLL_SECONDS=10.0

SCALPER_API_HOST=127.0.0.1
SCALPER_API_PORT=8000
SCALPER_UI_ORIGIN=http://localhost:5173
```

Start the backend:

```powershell
aplus-web
```

The API starts at:

```text
http://127.0.0.1:8000
```

Useful endpoints:

```text
GET  /api/status
GET  /api/health
GET  /api/market/bars
GET  /api/analysis/latest
GET  /api/analysis/history
POST /api/analysis/scan
POST /api/market/select
WS    /ws
```

## 2. React UI

Open a second PowerShell window:

```powershell
cd E:\Project\Tradde\A-Scalper-Engine\ui
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

Vite proxies `/api` and `/ws` to the local FastAPI backend.

## 3. Realtime request policy

The browser never polls PrimeXBT itself.

Backend defaults:

```text
quote       every 2 seconds
1M bars     every 5 seconds, only a 3-bar refresh
account     every 10 seconds
full scan   only on a newly closed 1M candle or manual Run scan
```

Higher-timeframe history is cached and invalidated only at its candle boundary.
Concurrent UI consumers share the same cache and MCP session.

If an MCP read starts failing, each supervisor loop exponentially backs off up to 60 seconds.

## 4. Dashboard functionality

- realtime bid / ask / spread and market-open state
- candlestick chart
- EMA50, EMA200 and VWAP overlays
- 1M / 5M / 15M / 1H chart switching
- A+ confluence score and threshold
- 1H / 15M / 5M / 1M engine-state cards
- manual strategy scan
- realtime WebSocket analysis updates
- SQLite analysis history
- PrimeXBT symbol search and safe symbol switching, including BTC instruments
- Demo account indicator
- MCP health and request-cache metrics through the API
- dark and light themes

## 5. Safety

The web backend refuses a Live account when `SCALPER_REQUIRE_DEMO=true`.

MCP order writes are not exposed to the React UI. The current dashboard is monitoring and
analysis only.
