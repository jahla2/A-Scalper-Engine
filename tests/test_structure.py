from scalper.config import StructureConfig
from scalper.models import Bar, Direction, Swing
from scalper.structure import classify_structure, find_swings, recent_bos


def make_bar(i: int, open_: float, high: float, low: float, close: float) -> Bar:
    return Bar(i * 300, open_, high, low, close, 100)


def test_classify_hh_hl() -> None:
    swings = [
        Swing(1, 10, "LOW"),
        Swing(2, 15, "HIGH"),
        Swing(3, 12, "LOW"),
        Swing(4, 18, "HIGH"),
    ]
    assert classify_structure(swings) == "HH_HL"


def test_find_swings_requires_confirmation_on_both_sides() -> None:
    bars = [
        make_bar(0, 10, 11, 9, 10),
        make_bar(1, 10, 12, 9.5, 11),
        make_bar(2, 11, 15, 10, 13),
        make_bar(3, 13, 12, 9, 10),
        make_bar(4, 10, 11, 8, 9),
        make_bar(5, 9, 12, 9, 11),
    ]
    swings = find_swings(bars, 2, 2)
    assert any(s.kind == "HIGH" and s.index == 2 for s in swings)


def test_recent_bos_requires_body_close_not_wick_only() -> None:
    cfg = StructureConfig(
        swing_left=2,
        swing_right=2,
        bos_atr_buffer=0.0,
        bos_min_ticks=0,
        bos_lookback=8,
        displacement_body_ratio=0.4,
        displacement_atr_ratio=0.2,
        retest_atr_zone=0.2,
        retest_lookback=3,
    )
    bars = [
        make_bar(0, 10, 11, 9, 10),
        make_bar(1, 10, 12, 9.5, 11),
        make_bar(2, 11, 15, 10.5, 14),
        make_bar(3, 14, 13, 10, 11),
        make_bar(4, 11, 12, 8, 9),
        make_bar(5, 9, 11.5, 9, 10.5),
        make_bar(6, 10.5, 12.5, 10, 12),
        make_bar(7, 12, 15.5, 11.8, 14.8),  # wick over 15, close below: no BOS
        make_bar(8, 14.8, 16.5, 14.7, 16.2),  # body close over swing high
        make_bar(9, 16.2, 16.4, 14.9, 15.4),  # retest of broken level
        make_bar(10, 15.4, 16.8, 15.2, 16.5),
        make_bar(11, 16.5, 17.0, 16.0, 16.8),
    ]
    signal = recent_bos(bars, Direction.LONG, 0.01, cfg)
    assert signal.bos is True
    assert signal.bos_index == 8
    assert signal.bos_level == 15
    assert signal.bos_time == 8 * 300
    assert signal.retest is True
