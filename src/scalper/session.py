from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def preferred_scalping_window(timestamp: int, timezone: str = "Asia/Manila") -> bool:
    """Project-guide windows, used only as a small score modifier.

    These are not treated as official exchange session opens because DST can shift
    London/New York relative to Philippine time.
    """
    local = datetime.fromtimestamp(timestamp, ZoneInfo(timezone))
    minute = local.hour * 60 + local.minute
    london_source_window = 15 * 60 <= minute <= 18 * 60
    new_york_source_window = 20 * 60 + 30 <= minute <= 23 * 60 + 30
    return london_source_window or new_york_source_window
