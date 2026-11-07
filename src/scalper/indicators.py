from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .models import Bar


def ema(values: list[float], period: int) -> list[float]:
    if period <= 0:
        raise ValueError("period must be positive")
    if not values:
        return []
    result: list[float] = []
    running = 0.0
    seed_count = min(period, len(values))
    for i in range(seed_count):
        running += values[i]
        result.append(running / (i + 1))
    if len(values) <= period:
        return result
    alpha = 2.0 / (period + 1.0)
    current = result[-1]
    for value in values[period:]:
        current = alpha * value + (1.0 - alpha) * current
        result.append(current)
    return result


def true_ranges(bars: list[Bar]) -> list[float]:
    if not bars:
        return []
    result = [bars[0].high - bars[0].low]
    previous_close = bars[0].close
    for bar in bars[1:]:
        result.append(
            max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        )
        previous_close = bar.close
    return result


def atr(bars: list[Bar], period: int = 14) -> list[float]:
    if period <= 0:
        raise ValueError("period must be positive")
    ranges = true_ranges(bars)
    if not ranges:
        return []
    result: list[float] = []
    running = 0.0
    seed_count = min(period, len(ranges))
    for i in range(seed_count):
        running += ranges[i]
        result.append(running / (i + 1))
    if len(ranges) <= period:
        return result
    current = result[-1]
    for tr in ranges[period:]:
        current = ((period - 1) * current + tr) / period
        result.append(current)
    return result


def session_vwap(bars: list[Bar], timezone: str = "Asia/Manila") -> float:
    if not bars:
        raise ValueError("bars are required")
    zone = ZoneInfo(timezone)
    latest_day = datetime.fromtimestamp(bars[-1].t, zone).date()
    weighted = 0.0
    volume = 0.0
    fallback_sum = 0.0
    fallback_count = 0
    for bar in reversed(bars):
        if datetime.fromtimestamp(bar.t, zone).date() != latest_day:
            break
        typical = (bar.high + bar.low + bar.close) / 3.0
        fallback_sum += typical
        fallback_count += 1
        if bar.volume > 0:
            weighted += typical * bar.volume
            volume += bar.volume
    if volume > 0:
        return weighted / volume
    return fallback_sum / max(1, fallback_count)


def body_ratio(bar: Bar) -> float:
    if bar.range <= 0:
        return 0.0
    return bar.body / bar.range
