from __future__ import annotations

from .models import Bar

SECONDS = {
    "1M": 60,
    "5M": 300,
    "15M": 900,
    "30M": 1800,
    "1H": 3600,
    "4H": 14400,
    "1D": 86400,
}


def closed_bars(bars: list[Bar], bar_size: str, now: int) -> list[Bar]:
    seconds = SECONDS[bar_size]
    return [bar for bar in bars if bar.t + seconds <= now]
