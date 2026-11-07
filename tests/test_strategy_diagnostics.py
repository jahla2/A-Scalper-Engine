from scalper.config import Settings
from scalper.models import Bar, Direction
from scalper.strategy import market_bias


def test_market_bias_reports_long_alignment_without_claiming_trade_signal() -> None:
    bars = [
        Bar(
            t=1_700_000_000 + i * 3600,
            open=100 + i,
            high=102 + i,
            low=99 + i,
            close=101 + i,
            volume=100,
        )
        for i in range(220)
    ]
    bias = market_bias(bars, Settings(timezone="UTC"))
    assert bias.direction == Direction.LONG
    assert bias.long_alignment == 75
    assert bias.short_alignment == 0
    assert bias.strength == 75
    assert bias.components["price_vs_ema200"] == "LONG"
    assert bias.components["ema_alignment"] == "LONG"
    assert bias.components["ema_slope"] == "LONG"
    assert bias.components["structure"] == "NEUTRAL"
