# A+ Scalper Engine — Demo-First Local Setup

This is the start-to-finish setup for running the A+ Structure-Filtered Scalper locally against a **PrimeXBT PXTrader 2.0 Demo account** through PrimeXBT MCP.

> Safety default: the local runner requires a demo account. If OAuth returns an account beginning with `L`, the app stops before scanning. Demo accounts returned by PrimeXBT begin with `D`.

## 1. What this local version does

```text
PrimeXBT Demo account
        |
        | OAuth + MCP
        v
A+ Scalper local process
        |
        +--> 1H regime
        +--> 15M location
        +--> 5M BOS / displacement / retest
        +--> 1M refinement
        |
        v
NO_TRADE / WATCH / TRADE_CANDIDATE
        |
        v
logs/signals.jsonl
```

This MCP runtime reads live market/account data and generates deterministic signals. It does **not** auto-place trades.

## 2. Create or select a PrimeXBT Demo account

1. Sign in to PrimeXBT.
2. Open **PXTrader 2.0**.
3. Choose **Demo Account**, not Real Account.
4. Confirm that you are inside the demo trading interface before connecting the local client.

PrimeXBT describes the Demo account as a practice environment with virtual funds and real-market-like conditions.

Official references:

- https://primexbt.help/en/articles/10660544-how-to-start-trading-on-pxtrader-2-0
- https://primexbt.help/en/articles/17695344-primexbt-mcp-what-it-is-and-how-to-connect

The MCP tool available to this project can list existing accounts but cannot create a new PrimeXBT trading account for you. Demo creation/selection must therefore be done in the PrimeXBT UI.

## 3. Clone the project

Windows PowerShell:

```powershell
cd F:\
git clone https://github.com/jahla2/A-Scalper-Engine.git
cd A-Scalper-Engine
```

If you already cloned it:

```powershell
cd F:\A-Scalper-Engine
git checkout main
git pull origin main
```

## 4. Install Python 3.12 environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

Expected:

```text
Python 3.12.x
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Validate the project:

```powershell
pytest
ruff check src tests
```

Both commands should pass before connecting PrimeXBT.

## 5. Create local configuration

```powershell
Copy-Item .env.example .env
```

Default:

```env
PRIMEXBT_MCP_URL=https://api.primexbt.com/v2/mcp
SCALPER_SYMBOL=XAU/USD
SCALPER_REQUIRE_DEMO=true
SCALPER_POLL_SECONDS=2.0
SCALPER_MAX_DAILY_DRAWDOWN_PCT=2.0
SCALPER_OAUTH_FILE=.scalper/primexbt_oauth.json
SCALPER_JOURNAL_FILE=logs/signals.jsonl
```

Do not put passwords in `.env`. PrimeXBT authorization is OAuth-based.

## 6. Connect the local client to the Demo account

Make sure your virtual environment is active, then run:

```powershell
aplus connect
```

The browser opens PrimeXBT authorization.

During authorization:

1. Sign in to PrimeXBT.
2. Select/authorize the **PXTrader 2.0 Demo account**.
3. Complete the consent screen.
4. When your browser is redirected, copy the **entire redirected URL** from the address bar.
5. Paste that full URL into the PowerShell prompt.

OAuth state is stored locally at:

```text
.scalper/primexbt_oauth.json
```

That path is gitignored.

## 7. Verify that the account is really Demo

A successful connection should print JSON similar to:

```json
{
  "account": {
    "id": "D123456",
    "demo": true,
    "currency": "USD",
    "position_mode": "HEDGE"
  },
  "symbol": "XAU/USD",
  "market_open": true,
  "bid": 0,
  "ask": 0,
  "available_tools": 0
}
```

The actual prices and tool count will differ.

The two important checks are:

```text
account.id starts with D
account.demo = true
```

After you know the demo account ID, you may pin it in `.env`:

```env
PRIMEXBT_ACCOUNT_ID=D123456
```

Use your actual returned ID.

## 8. If you accidentally connected the Live account

The runner intentionally stops if it sees an `L...` account while:

```env
SCALPER_REQUIRE_DEMO=true
```

Reset OAuth:

```powershell
Remove-Item .scalper\primexbt_oauth.json
```

Then return to PrimeXBT, select the Demo account, and run:

```powershell
aplus connect
```

again.

Do not set `SCALPER_REQUIRE_DEMO=false` during development just to bypass this guard.

## 9. Run one live Demo scan

```powershell
aplus scan
```

The engine reads:

```text
1H  -> regime / EMA50 / EMA200 / HH-HL or LH-LL
15M -> location / EMA50 / VWAP / structure
5M  -> confirmed body-close BOS / displacement / retest
1M  -> optional execution refinement
```

Output will be one of:

```text
NO_TRADE
WATCH
TRADE_CANDIDATE
```

A score of 85+ is an A+ setup-quality threshold, not a promised win probability.

## 10. Start realtime monitoring

```powershell
aplus watch
```

Runtime behavior:

```text
every ~2 seconds
      |
      v
fetch only last 3 x 1M bars
      |
new closed 1M candle?
   |          |
   no         yes
   |          |
 sleep        v
        full A+ scan
       1H/15M/5M
            |
       1M if needed
            |
   signal + journal
```

This avoids repeatedly downloading the full multi-timeframe history every two seconds.

Stop with:

```text
Ctrl + C
```

## 11. Signal journal

Signals are written to:

```text
logs/signals.jsonl
```

Use this later for backtesting/forward-testing analysis such as:

- number of A+ candidates
- long vs short performance
- session performance
- score threshold performance
- effect of 1M confirmation
- maximum drawdown
- expectancy and profit factor

## 12. Daily loss guard

Default:

```env
SCALPER_MAX_DAILY_DRAWDOWN_PCT=2.0
```

The runner records the starting equity for the local trading day and blocks a candidate when drawdown reaches the configured limit.

This currently blocks the runtime candidate state; MCP auto-execution remains disabled regardless.

## 13. Normal daily startup

After initial setup, your normal startup is:

```powershell
cd F:\A-Scalper-Engine
.\.venv\Scripts\Activate.ps1
git pull origin main
pip install -e ".[dev]"
aplus watch
```

You do not need to recreate the virtual environment every day.

## 14. Troubleshooting

### `Demo account required, but PrimeXBT OAuth is connected to L...`

You authorized a Live account.

```powershell
Remove-Item .scalper\primexbt_oauth.json
aplus connect
```

Select Demo during PrimeXBT authorization.

### OAuth redirect error

Copy the entire browser URL, including `code=` and `state=`, and paste it into PowerShell.

### `configured PrimeXBT account was not returned by list_accounts`

Your `PRIMEXBT_ACCOUNT_ID` does not belong to the account authorized by the current OAuth token.

Remove or correct it, or reset OAuth.

### Wrong XAU instrument

Keep:

```env
SCALPER_SYMBOL=XAU/USD
```

The broker requires an exact match and will not silently change it to `XAU/USD.24`.

### Tests fail after pulling

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
ruff check src tests
```

## 15. Important execution limitation

PrimeXBT documents MCP as an AI-assistant/human-confirmed trading interface. The local MCP runner therefore does not attempt unattended order placement.

For future autonomous/demo execution, keep the A+ strategy engine and add a separate PXTrader 2.0 Trade API broker adapter after validating PrimeXBT's current published authentication and endpoint specification.

Do not bypass MCP confirmation mechanics to imitate a low-latency trading API.


## 16. Windows timezone dependency

If Windows shows `ZoneInfoNotFoundError` or `No module named 'tzdata'`, update to the latest project version and reinstall dependencies:

```powershell
git pull origin main
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Version 0.2.1+ includes `tzdata` as a required dependency, so `ZoneInfo("UTC")` and `ZoneInfo("Asia/Manila")` work on Windows without a separate manual setup.

For an older checkout, the immediate workaround is:

```powershell
pip install tzdata
pytest
```
