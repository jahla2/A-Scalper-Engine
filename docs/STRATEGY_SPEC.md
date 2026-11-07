# A+ Structure-Filtered Scalper v1.0

## 1. Indicators

### EMA

For period `N`, seed the EMA with the simple average of the first `N` closes, then:

```text
alpha = 2 / (N + 1)
EMA[t] = alpha * close[t] + (1 - alpha) * EMA[t-1]
```

V1 uses EMA50 and EMA200.

### ATR

```text
TR[t] = max(
  high[t] - low[t],
  abs(high[t] - close[t-1]),
  abs(low[t] - close[t-1])
)
```

ATR14 uses Wilder smoothing after the initial average.

### Session VWAP

```text
typical_price = (high + low + close) / 3
VWAP = sum(typical_price * volume) / sum(volume)
```

The current local trading day in `Asia/Manila` is used as the reset boundary. If volume is unavailable/zero, the implementation falls back to the mean typical price and VWAP loses scoring significance as a volume measure.

## 2. Swings

Default pivot width is `left=2`, `right=2`.

A swing high at index `i` must be strictly higher than both preceding left bars and following right bars. Swing lows are the inverse. The right-side requirement means the swing is confirmed only after those future bars close; this avoids look-ahead use in BOS detection.

## 3. 1H regime

Long permission requires all of:

- close > EMA200
- EMA50 > EMA200
- EMA50 is rising versus 3 bars earlier
- confirmed structure = HH/HL

Short is the exact inverse. Otherwise the direction is `NEUTRAL` and no trade is permitted.

## 4. 15M setup

A valid setup requires price to be within `0.50 * ATR14` of at least one location anchor:

- EMA50
- session VWAP
- nearest aligned confirmed swing level

By default long setups must remain on/above VWAP and short setups on/below VWAP. This can be disabled in configuration for research.

## 5. 5M BOS

A wick through structure is not enough.

For long:

```text
close > confirmed_swing_high + buffer
previous_close <= confirmed_swing_high + buffer
```

For short, invert the comparisons.

```text
buffer = max(min_tick * 2, ATR14 * 0.05)
```

Only swings already confirmed before the BOS candle are eligible.

## 6. Displacement

The BOS candle is marked as displacement when both are true:

```text
body / range >= 0.60
body >= 0.80 * ATR14
```

Displacement adds score; BOS itself remains the required structural event.

## 7. Retest

After BOS, V1 looks up to four bars ahead for a revisit of the broken level within:

```text
level +/- 0.15 * ATR14
```

A bullish retest must close at/above the broken level; bearish retest closes at/below it.

## 8. 1M refinement

1M is fetched only after the 1H, 15M and 5M gates pass. It adds a small score when micro structure aligns or a micro BOS appears. It never changes the 1H direction.

## 9. Score

| Rule | Points |
| --- | ---: |
| 1H regime aligned | 20 |
| 15M location valid | 15 |
| confirmed nearby level | 10 |
| 5M BOS | 20 |
| displacement | 10 |
| retest | 10 |
| preferred active window | 5 |
| 1M confirmation | 5 |
| RR >= minimum | 5 |
| **A+ threshold** | **85 / 100** |

The score is a setup-quality score, **not a probability or win rate**.

## 10. Stop and target

Stop is structural:

- long: latest confirmed 5M swing low - `0.15 * ATR`
- short: latest confirmed 5M swing high + `0.15 * ATR`

Default target is 2R, but the nearest opposing 15M swing caps the target. If this leaves less than 1.5R, the trade is rejected.

## 11. Spread and market gates

The market must be open and:

```text
spread / 5M_ATR <= 0.10
```

This threshold is intentionally configurable and should be calibrated by instrument/session from recorded live data.

## 12. Execution states

```text
NO_TRADE -> WATCH -> TRADE_CANDIDATE -> PREVIEW -> APPROVAL -> EXECUTE
```

A candidate cannot bypass broker preview. A preview ticket is single-purpose and is the only input accepted by the subsequent PrimeXBT write.
