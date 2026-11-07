# Structured Trade Plan

A+ Scalper only creates price targets after the strategy has a confirmed 5M BOS and can derive
a structural stop. It does not invent Entry/SL/TP levels when the setup has not reached that stage.

## Entry

The entry reference is the current executable PrimeXBT quote:

- LONG uses the current ask.
- SHORT uses the current bid.

Before the 1M execution rule confirms, the plan is marked `PROVISIONAL`.
After 1M confirmation, it becomes `READY` if the remaining A+ safety gates also pass.

## Stop loss

The stop is structure-based:

- LONG: below the latest confirmed 5M swing low.
- SHORT: above the latest confirmed 5M swing high.

An ATR buffer is added using `stop_atr_buffer` (default 0.15 ATR).

## Targets

The final target starts from the configured `target_rr` (default 2.0R). The nearest opposing
15M swing acts as a structural cap. If that cap leaves less than `min_rr` (default 1.5R), no
trade plan is produced.

The three targets are deterministic milestones toward the reachable final target:

- TP1 = 50% of the reachable final-R objective, capped at 1.0R.
- TP2 = 75% of the reachable final-R objective, capped at 1.5R.
- TP3 = full reachable final target.

With an uncapped 2R objective:

```text
Entry  = 100
SL     = 98
Risk   = 2

TP1    = 102   = 1.0R
TP2    = 103   = 1.5R
TP3    = 104   = 2.0R
```

If a 15M opposing swing caps the move at 1.5R, the milestones scale to 0.75R / 1.125R / 1.5R.

## Candidate gate

A plan can exist while still being provisional. `TRADE_CANDIDATE` additionally requires:

- market open
- spread acceptable relative to 5M ATR
- valid trade plan
- 5M displacement confirmed
- 5M retest confirmed
- 1M execution confirmation
- A+ score >= threshold

This keeps the plan explanatory without turning every directional bias into an entry signal.
