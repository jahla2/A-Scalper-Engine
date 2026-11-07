# Analysis Model

## Decision engine

A+ Scalper v1 uses a deterministic rule engine. It does not require an LLM to decide whether
the market is LONG, SHORT, WATCH, NO_TRADE, or a TRADE_CANDIDATE.

The current decision pipeline is:

```text
PrimeXBT OHLCV / quote
        |
        v
1H directional alignment + strict regime
        |
        v
15M location / VWAP / key level
        |
        v
5M BOS / displacement / retest
        |
        v
1M execution refinement
        |
        v
A+ setup score + RR + spread + market-open safety
```

## Directional alignment versus A+ setup score

These are deliberately separate.

### Directional alignment

The UI shows LONG and SHORT rule alignment from four equal 1H checks:

- price versus EMA200: 25 points
- EMA50 versus EMA200: 25 points
- EMA50 slope: 25 points
- confirmed swing structure: 25 points

Example:

```text
LONG alignment  75
SHORT alignment 25
Bias             LONG
```

This means three of the four directional rule groups favor LONG. It is **not** a 75% win
probability.

### Strict 1H regime

A tradable LONG regime still requires all long-side filters to align, including HH/HL swing
structure. SHORT requires the inverse. If the EMA filters are bullish but structure is bearish,
the strict regime remains NEUTRAL even when the directional alignment leans LONG.

### A+ setup score

The A+ score measures trade qualification:

```text
1H regime       20
15M location    15
Key level       10
5M BOS          20
Displacement    10
Retest          10
Session          5
1M execution     5
Reward / risk    5
------------------
Maximum        100
Threshold       85
```

Early pipeline stages now return the score components that have actually been validated instead
of an empty score object.

## Why Run Scan can return the same answer

A manual scan reads the newest cached/PrimeXBT state and applies the same deterministic rules.
If no relevant candle or structure changed, the correct result can be identical.

Manual scans have a 3-second server-side cooldown. Repeated clicks inside that window return the
latest analysis without starting another strategy scan.

The UI shows the scan source:

- startup
- symbol change
- candle close
- manual
- manual cached

## LLM / agent role

An LLM is optional and should stay outside the trading decision hot path.

Useful future LLM roles:

- explain a deterministic result in natural language
- summarize analysis history
- research news/context
- generate post-trade journal observations
- propose hypotheses for backtesting

The LLM should not override the deterministic safety gates, risk rules, or broker execution
controls.
