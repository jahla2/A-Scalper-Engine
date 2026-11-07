from scalper.indicators import atr, ema, session_vwap
from scalper.models import Bar


def test_ema_keeps_length_and_tracks_series() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    result = ema(values, 3)
    assert result == [1.0, 1.5, 2.0, 3.0]


def test_atr_uses_true_range() -> None:
    bars = [
        Bar(0, 10, 12, 9, 11, 1),
        Bar(60, 11, 13, 10, 12, 1),
        Bar(120, 15, 16, 14, 15, 1),
    ]
    result = atr(bars, 2)
    assert result[0] == 3
    assert result[1] == 3
    assert result[2] == 3.5


def test_vwap_uses_volume_weighting() -> None:
    day = 1_767_225_600
    bars = [
        Bar(day, 10, 12, 8, 10, 1),
        Bar(day + 60, 20, 22, 18, 20, 3),
    ]
    assert session_vwap(bars, "UTC") == 17.5
