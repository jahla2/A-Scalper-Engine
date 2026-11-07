# Strategy Catalog and Full-Scan Pipeline

## Why the scanner evaluates every timeframe

The scanner now fetches the latest **closed** candles for all four analysis timeframes on every
strategy scan:

```text
1H  context / regime
15M setup / location
5M  confirmation / structure
1M  execution timing
```

The final decision is made **after** all four diagnostics are calculated.

A higher-timeframe gate can still block a trade. For example, a strict 1H regime may be neutral
while 15M/5M/1M show partial bullish alignment. In that case the correct decision can remain
`NO_TRADE`, but those lower-timeframe cards must show their real evaluated state instead of
`SKIPPED`.

This is deliberately different from the original early-exit implementation.

## Included strategies

### A+ Structure MTF

Project baseline:

- 1H: EMA50/EMA200 trend + slope + swing structure.
- 15M: pullback/location around EMA50, session VWAP or nearby swing level.
- 5M: close-based BOS, displacement and retest.
- 1M: micro structure / BOS execution confirmation.

### Ichimoku MTF

Japanese-origin trend framework based on Ichimoku Kinko Hyo.

Our adaptation:

- 1H: price versus cloud, Tenkan/Kijun, cloud orientation and swing structure.
- 15M: Kijun/cloud pullback location.
- 5M: structural BOS/displacement/retest confirmation.
- 1M: Tenkan/Kijun + cloud-side + micro BOS execution.

Ichimoku itself is established; this exact multi-timeframe rule combination is an implementation
choice that must be backtested.

### EMA 20/50 Pullback

Fast trend-pullback profile:

- 1H: price / EMA20 / EMA50 alignment and swing context.
- 15M: pullback near EMA20/EMA50.
- 5M: BOS/displacement/retest.
- 1M: EMA20/50 alignment plus micro BOS.

The exact 20/50 periods are a strategy parameter, not a guaranteed professional standard.

### VWAP Momentum

Intraday profile:

- 1H: broader trend context using EMA200, EMA50 slope and session VWAP.
- 15M: location around session VWAP.
- 5M: structure/momentum confirmation.
- 1M: VWAP-side + micro BOS execution.

PrimeXBT volume may represent platform/tick volume rather than centralized market volume, so VWAP
is treated as a secondary intraday tool rather than absolute market truth.

## Research basis

The catalog is based on established technical-analysis concepts rather than claims that any one
strategy is universally used or profitable.

References reviewed during implementation:

- CMT Association, Ichimoku overview:
  https://cmtassociation.org/technically_speaking/technically-speaking-may-2022/
- Fidelity, Ichimoku Cloud guide:
  https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/ichimoku-cloud
- Fidelity, technical-analysis overview:
  https://www.fidelity.com/learning-center/trading-investing/technical-analysis/what-is-technical-analysis
- CME Group, trend and continuation patterns:
  https://www.cmegroup.com/education/courses/technical-analysis/trend-and-continuation-patterns
- Fidelity, chart indicators including VWAP / Heikin Ashi:
  https://www.fidelity.com/learning-center/trading-investing/technical-analysis/new-charts-replay

## Safety

Strategy selection changes the analysis rules, not broker execution permissions.

All current web strategies remain:

```text
analysis only
demo required by default
no browser-direct PrimeXBT access
no LLM required for BUY/SELL decisions
```

Every strategy must be backtested and forward-tested independently. A strategy name or historical
lineage is not evidence of profitability.
