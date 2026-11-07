from scalper.models import Bar
from scalper.timeframes import closed_bars


def test_closed_bars_drops_forming_candle() -> None:
    bars = [Bar(0, 1, 1, 1, 1), Bar(300, 1, 1, 1, 1)]
    assert [b.t for b in closed_bars(bars, "5M", 599)] == [0]
    assert [b.t for b in closed_bars(bars, "5M", 600)] == [0, 300]
