from __future__ import annotations

from .config import StructureConfig
from .indicators import atr, body_ratio
from .models import Bar, Direction, StructureSignal, Swing


def find_swings(bars: list[Bar], left: int = 2, right: int = 2) -> list[Swing]:
    if left < 1 or right < 1:
        raise ValueError("left and right must be positive")
    swings: list[Swing] = []
    for i in range(left, len(bars) - right):
        high = bars[i].h
        low = bars[i].l
        if all(high > bars[j].h for j in range(i - left, i)) and all(
            high > bars[j].h for j in range(i + 1, i + right + 1)
        ):
            swings.append(Swing(i, high, "HIGH"))
        if all(low < bars[j].l for j in range(i - left, i)) and all(
            low < bars[j].l for j in range(i + 1, i + right + 1)
        ):
            swings.append(Swing(i, low, "LOW"))
    return swings


def classify_structure(swings: list[Swing]) -> str:
    highs = [s for s in swings if s.kind == "HIGH"]
    lows = [s for s in swings if s.kind == "LOW"]
    if len(highs) < 2 or len(lows) < 2:
        return "UNKNOWN"
    hh = highs[-1].price > highs[-2].price
    hl = lows[-1].price > lows[-2].price
    lh = highs[-1].price < highs[-2].price
    ll = lows[-1].price < lows[-2].price
    if hh and hl:
        return "HH_HL"
    if lh and ll:
        return "LH_LL"
    return "RANGE"


def latest_swing(swings: list[Swing], kind: str, before_index: int | None = None) -> Swing | None:
    candidates = [s for s in swings if s.kind == kind]
    if before_index is not None:
        candidates = [s for s in candidates if s.index < before_index]
    return candidates[-1] if candidates else None


def _confirmed_level(
    swings: list[Swing], kind: str, before_index: int, right: int
) -> Swing | None:
    candidates = [
        s
        for s in swings
        if s.kind == kind and s.index + right < before_index
    ]
    return candidates[-1] if candidates else None


def recent_bos(
    bars: list[Bar],
    direction: Direction,
    min_tick: float,
    config: StructureConfig,
) -> StructureSignal:
    if len(bars) < max(10, config.swing_left + config.swing_right + 5):
        return StructureSignal(
            direction, False, None, None, None, False, False, 0.0, "insufficient bars"
        )
    atrs = atr(bars, 14)
    current_atr = atrs[-1]
    swings = find_swings(bars, config.swing_left, config.swing_right)
    if direction == Direction.NEUTRAL:
        return StructureSignal(
            direction, False, None, None, None, False, False, current_atr, "neutral direction"
        )

    kind = "HIGH" if direction == Direction.LONG else "LOW"
    start = max(1, len(bars) - config.bos_lookback)
    found: tuple[int, float, bool] | None = None

    for i in range(start, len(bars)):
        swing = _confirmed_level(swings, kind, i, config.swing_right)
        if swing is None:
            continue
        buffer = max(min_tick * config.bos_min_ticks, atrs[i] * config.bos_atr_buffer)
        level = swing.price
        if direction == Direction.LONG:
            crossed = bars[i].c > level + buffer and bars[i - 1].c <= level + buffer
        else:
            crossed = bars[i].c < level - buffer and bars[i - 1].c >= level - buffer
        if not crossed:
            continue
        displacement = (
            body_ratio(bars[i]) >= config.displacement_body_ratio
            and bars[i].body >= atrs[i] * config.displacement_atr_ratio
        )
        found = (i, level, displacement)

    if found is None:
        return StructureSignal(
            direction, False, None, None, None, False, False, current_atr, "no confirmed BOS"
        )

    bos_index, level, displacement = found
    zone = atrs[bos_index] * config.retest_atr_zone
    retest = False
    for bar in bars[bos_index + 1 : bos_index + 1 + config.retest_lookback]:
        if direction == Direction.LONG:
            if bar.l <= level + zone and bar.c >= level:
                retest = True
                break
        elif bar.h >= level - zone and bar.c <= level:
            retest = True
            break

    return StructureSignal(
        direction=direction,
        bos=True,
        bos_level=level,
        bos_index=bos_index,
        bos_time=bars[bos_index].t,
        displacement=displacement,
        retest=retest,
        atr=current_atr,
        reason="confirmed body-close BOS",
    )
