from __future__ import annotations

from typing import Any

from ..indicators import atr, ema, session_vwap_series
from ..models import Bar


def chart_payload(bars: list[Bar], timezone: str) -> dict[str, Any]:
    closes = [bar.close for bar in bars]
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200)
    vwap = session_vwap_series(bars, timezone)
    atr14 = atr(bars, 14)
    return {
        "bars": [
            {
                "time": bar.t,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ],
        "indicators": {
            "ema50": _line_series(bars, ema50),
            "ema200": _line_series(bars, ema200),
            "vwap": _line_series(bars, vwap),
            "atr14": atr14[-1] if atr14 else None,
        },
    }


def _line_series(bars: list[Bar], values: list[float]) -> list[dict[str, float | int]]:
    offset = max(0, len(bars) - len(values))
    selected = bars[offset:]
    return [
        {"time": bar.t, "value": value}
        for bar, value in zip(selected, values, strict=False)
    ]
