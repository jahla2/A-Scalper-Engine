from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .indicators import atr, ema, session_vwap
from .models import (
    Bar,
    Direction,
    ExecutionSignal,
    MarketBias,
    Regime,
    Setup,
    StructureSignal,
)
from .strategy import execution, market_bias, regime, setup
from .strategy_catalog import get_strategy
from .structure import classify_structure, find_swings, recent_bos


@dataclass(frozen=True, slots=True)
class StrategySnapshot:
    bias: MarketBias
    regime: Regime
    setup: Setup
    structure: StructureSignal
    execution: ExecutionSignal
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IchimokuSnapshot:
    tenkan: float
    kijun: float
    span_a: float
    span_b: float

    @property
    def cloud_top(self) -> float:
        return max(self.span_a, self.span_b)

    @property
    def cloud_bottom(self) -> float:
        return min(self.span_a, self.span_b)


def evaluate_strategy(
    strategy_id: str,
    bars_1h: list[Bar],
    bars_15m: list[Bar],
    bars_5m: list[Bar],
    bars_1m: list[Bar],
    min_tick: float,
    settings: Settings,
) -> StrategySnapshot:
    get_strategy(strategy_id)
    if strategy_id == "a_plus_structure":
        return _a_plus(bars_1h, bars_15m, bars_5m, bars_1m, min_tick, settings)
    if strategy_id == "ema_20_50_pullback":
        return _ema_pullback(bars_1h, bars_15m, bars_5m, bars_1m, min_tick, settings)
    if strategy_id == "vwap_momentum":
        return _vwap_momentum(bars_1h, bars_15m, bars_5m, bars_1m, min_tick, settings)
    if strategy_id == "ichimoku_mtf":
        return _ichimoku_mtf(bars_1h, bars_15m, bars_5m, bars_1m, min_tick, settings)
    raise AssertionError("strategy catalog and evaluator are out of sync")


def _analysis_direction(reg: Regime, bias: MarketBias) -> Direction:
    return reg.direction if reg.direction != Direction.NEUTRAL else bias.direction


def _a_plus(
    bars_1h: list[Bar],
    bars_15m: list[Bar],
    bars_5m: list[Bar],
    bars_1m: list[Bar],
    min_tick: float,
    settings: Settings,
) -> StrategySnapshot:
    reg = regime(bars_1h, settings)
    bias = market_bias(bars_1h, settings)
    direction = _analysis_direction(reg, bias)
    stp = setup(bars_15m, direction, settings)
    structure = recent_bos(bars_5m, direction, min_tick, settings.structure)
    exe = execution(bars_1m, direction, min_tick, settings)
    return StrategySnapshot(
        bias,
        reg,
        stp,
        structure,
        exe,
        (
            "All 1H/15M/5M/1M diagnostics were evaluated before the final decision.",
            "Strict trade direction still requires full 1H regime alignment.",
        ),
    )


def _ema_pullback(
    bars_1h: list[Bar],
    bars_15m: list[Bar],
    bars_5m: list[Bar],
    bars_1m: list[Bar],
    min_tick: float,
    settings: Settings,
) -> StrategySnapshot:
    bias, reg = _ema_regime(bars_1h, settings)
    direction = _analysis_direction(reg, bias)
    stp = _ema_setup(bars_15m, direction, settings)
    structure = recent_bos(bars_5m, direction, min_tick, settings.structure)
    exe = _ema_execution(bars_1m, direction, min_tick, settings)
    return StrategySnapshot(
        bias,
        reg,
        stp,
        structure,
        exe,
        (
            "1H EMA20/50 trend, 15M pullback, 5M structure and 1M execution were evaluated.",
        ),
    )


def _vwap_momentum(
    bars_1h: list[Bar],
    bars_15m: list[Bar],
    bars_5m: list[Bar],
    bars_1m: list[Bar],
    min_tick: float,
    settings: Settings,
) -> StrategySnapshot:
    bias, reg = _vwap_regime(bars_1h, settings)
    direction = _analysis_direction(reg, bias)
    stp = _vwap_setup(bars_15m, direction, settings)
    structure = recent_bos(bars_5m, direction, min_tick, settings.structure)
    exe = _vwap_execution(bars_1m, direction, min_tick, settings)
    return StrategySnapshot(
        bias,
        reg,
        stp,
        structure,
        exe,
        (
            "1H trend context, 15M VWAP location, 5M structure and "
            "1M VWAP execution were evaluated.",
        ),
    )


def _ichimoku_mtf(
    bars_1h: list[Bar],
    bars_15m: list[Bar],
    bars_5m: list[Bar],
    bars_1m: list[Bar],
    min_tick: float,
    settings: Settings,
) -> StrategySnapshot:
    bias, reg = _ichimoku_regime(bars_1h, settings)
    direction = _analysis_direction(reg, bias)
    stp = _ichimoku_setup(bars_15m, direction, settings)
    structure = recent_bos(bars_5m, direction, min_tick, settings.structure)
    exe = _ichimoku_execution(bars_1m, direction, min_tick, settings)
    return StrategySnapshot(
        bias,
        reg,
        stp,
        structure,
        exe,
        (
            "1H Ichimoku cloud, 15M Kijun/cloud location, 5M structure and "
            "1M Tenkan/Kijun execution were evaluated.",
        ),
    )


def _ema_regime(bars: list[Bar], settings: Settings) -> tuple[MarketBias, Regime]:
    closes = [bar.close for bar in bars]
    if len(closes) < 55:
        return _empty_bias("Not enough 1H bars for EMA20/50."), _empty_regime(closes)

    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    close = closes[-1]
    swings = find_swings(bars, settings.structure.swing_left, settings.structure.swing_right)
    structure = classify_structure(swings)
    long_score = 0
    short_score = 0
    components: dict[str, str] = {}
    reasons: list[str] = []

    long_score, short_score = _score_relation(
        close, ema50[-1], "price_vs_ema50", components, reasons, long_score, short_score
    )
    long_score, short_score = _score_relation(
        ema20[-1], ema50[-1], "ema20_vs_ema50", components, reasons, long_score, short_score
    )
    previous = ema20[-4]
    long_score, short_score = _score_relation(
        ema20[-1], previous, "ema20_slope", components, reasons, long_score, short_score
    )
    long_score, short_score = _score_structure(
        structure, components, reasons, long_score, short_score
    )
    bias = _build_bias(long_score, short_score, components, reasons)

    long_regime = close > ema50[-1] and ema20[-1] > ema50[-1] and ema20[-1] > previous
    short_regime = close < ema50[-1] and ema20[-1] < ema50[-1] and ema20[-1] < previous
    if long_regime and structure == "HH_HL":
        direction = Direction.LONG
    elif short_regime and structure == "LH_LL":
        direction = Direction.SHORT
    else:
        direction = Direction.NEUTRAL
    return bias, Regime(
        direction,
        close,
        ema20[-1],
        ema50[-1],
        structure,
        long_regime or short_regime,
    )


def _ema_setup(bars: list[Bar], direction: Direction, settings: Settings) -> Setup:
    if len(bars) < 50 or direction == Direction.NEUTRAL:
        return Setup(False, False, False, 0.0, 0.0, None, "no directional EMA setup")
    closes = [bar.close for bar in bars]
    ema20 = ema(closes, 20)[-1]
    ema50 = ema(closes, 50)[-1]
    current_atr = atr(bars, settings.indicators.atr_period)[-1]
    close = closes[-1]
    threshold = current_atr * settings.setup.location_atr_distance
    nearest = ema20 if abs(close - ema20) <= abs(close - ema50) else ema50
    location = min(abs(close - ema20), abs(close - ema50)) <= threshold
    side_ok = (direction == Direction.LONG and close >= ema50) or (
        direction == Direction.SHORT and close <= ema50
    )
    valid = location and side_ok
    return Setup(
        valid,
        location,
        abs(close - ema20) <= threshold,
        session_vwap(bars, settings.timezone),
        current_atr,
        nearest,
        "valid EMA20/50 pullback" if valid else "15M EMA pullback/side filter failed",
    )


def _ema_execution(
    bars: list[Bar], direction: Direction, min_tick: float, settings: Settings
) -> ExecutionSignal:
    if len(bars) < 50 or direction == Direction.NEUTRAL:
        return ExecutionSignal(False, False, "UNKNOWN")
    closes = [bar.close for bar in bars]
    ema20 = ema(closes, 20)[-1]
    ema50 = ema(closes, 50)[-1]
    micro = recent_bos(bars, direction, min_tick, settings.structure)
    aligned = (direction == Direction.LONG and closes[-1] > ema20 > ema50) or (
        direction == Direction.SHORT and closes[-1] < ema20 < ema50
    )
    structure = classify_structure(
        find_swings(bars, settings.structure.swing_left, settings.structure.swing_right)
    )
    return ExecutionSignal(aligned and micro.bos, micro.bos, structure)


def _vwap_regime(bars: list[Bar], settings: Settings) -> tuple[MarketBias, Regime]:
    closes = [bar.close for bar in bars]
    if len(closes) < 205:
        return _empty_bias("Not enough 1H bars for VWAP trend context."), _empty_regime(closes)
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200)
    close = closes[-1]
    vwap = session_vwap(bars, settings.timezone)
    structure = classify_structure(
        find_swings(bars, settings.structure.swing_left, settings.structure.swing_right)
    )
    components: dict[str, str] = {}
    reasons: list[str] = []
    long_score = short_score = 0
    long_score, short_score = _score_relation(
        close, ema200[-1], "price_vs_ema200", components, reasons, long_score, short_score
    )
    long_score, short_score = _score_relation(
        close, vwap, "price_vs_vwap", components, reasons, long_score, short_score
    )
    long_score, short_score = _score_relation(
        ema50[-1], ema50[-4], "ema50_slope", components, reasons, long_score, short_score
    )
    long_score, short_score = _score_structure(
        structure, components, reasons, long_score, short_score
    )
    bias = _build_bias(long_score, short_score, components, reasons)
    long_regime = close > ema200[-1] and close > vwap and ema50[-1] > ema50[-4]
    short_regime = close < ema200[-1] and close < vwap and ema50[-1] < ema50[-4]
    if long_regime and structure != "LH_LL":
        direction = Direction.LONG
    elif short_regime and structure != "HH_HL":
        direction = Direction.SHORT
    else:
        direction = Direction.NEUTRAL
    return bias, Regime(
        direction,
        close,
        ema50[-1],
        ema200[-1],
        structure,
        long_regime or short_regime,
    )


def _vwap_setup(bars: list[Bar], direction: Direction, settings: Settings) -> Setup:
    if not bars or direction == Direction.NEUTRAL:
        return Setup(False, False, False, 0.0, 0.0, None, "no directional VWAP setup")
    current_vwap = session_vwap(bars, settings.timezone)
    current_atr = atr(bars, settings.indicators.atr_period)[-1]
    close = bars[-1].close
    threshold = current_atr * settings.setup.location_atr_distance
    location = abs(close - current_vwap) <= threshold
    side_ok = (direction == Direction.LONG and close >= current_vwap) or (
        direction == Direction.SHORT and close <= current_vwap
    )
    valid = location and side_ok
    return Setup(
        valid,
        location,
        location,
        current_vwap,
        current_atr,
        current_vwap,
        "valid VWAP momentum location" if valid else "15M VWAP location/side filter failed",
    )


def _vwap_execution(
    bars: list[Bar], direction: Direction, min_tick: float, settings: Settings
) -> ExecutionSignal:
    if not bars or direction == Direction.NEUTRAL:
        return ExecutionSignal(False, False, "UNKNOWN")
    current_vwap = session_vwap(bars, settings.timezone)
    close = bars[-1].close
    micro = recent_bos(bars, direction, min_tick, settings.structure)
    side_ok = (direction == Direction.LONG and close > current_vwap) or (
        direction == Direction.SHORT and close < current_vwap
    )
    structure = classify_structure(
        find_swings(bars, settings.structure.swing_left, settings.structure.swing_right)
    )
    return ExecutionSignal(side_ok and micro.bos, micro.bos, structure)


def _ichimoku_regime(bars: list[Bar], settings: Settings) -> tuple[MarketBias, Regime]:
    snapshot = _ichimoku_snapshot(bars)
    closes = [bar.close for bar in bars]
    if snapshot is None:
        return _empty_bias("Not enough 1H bars for Ichimoku cloud."), _empty_regime(closes)
    close = closes[-1]
    structure = classify_structure(
        find_swings(bars, settings.structure.swing_left, settings.structure.swing_right)
    )
    components: dict[str, str] = {}
    reasons: list[str] = []
    long_score = short_score = 0

    if close > snapshot.cloud_top:
        components["price_vs_cloud"] = "LONG"
        long_score += 25
        reasons.append("Price is above the Ichimoku cloud.")
    elif close < snapshot.cloud_bottom:
        components["price_vs_cloud"] = "SHORT"
        short_score += 25
        reasons.append("Price is below the Ichimoku cloud.")
    else:
        components["price_vs_cloud"] = "NEUTRAL"
        reasons.append("Price is inside the Ichimoku cloud.")

    long_score, short_score = _score_relation(
        snapshot.tenkan,
        snapshot.kijun,
        "tenkan_vs_kijun",
        components,
        reasons,
        long_score,
        short_score,
    )
    long_score, short_score = _score_relation(
        snapshot.span_a,
        snapshot.span_b,
        "cloud_orientation",
        components,
        reasons,
        long_score,
        short_score,
    )
    long_score, short_score = _score_structure(
        structure, components, reasons, long_score, short_score
    )
    bias = _build_bias(long_score, short_score, components, reasons)

    long_regime = (
        close > snapshot.cloud_top
        and snapshot.tenkan > snapshot.kijun
        and snapshot.span_a > snapshot.span_b
    )
    short_regime = (
        close < snapshot.cloud_bottom
        and snapshot.tenkan < snapshot.kijun
        and snapshot.span_a < snapshot.span_b
    )
    if long_regime and structure != "LH_LL":
        direction = Direction.LONG
    elif short_regime and structure != "HH_HL":
        direction = Direction.SHORT
    else:
        direction = Direction.NEUTRAL
    return bias, Regime(
        direction,
        close,
        snapshot.tenkan,
        snapshot.kijun,
        structure,
        long_regime or short_regime,
    )


def _ichimoku_setup(bars: list[Bar], direction: Direction, settings: Settings) -> Setup:
    snapshot = _ichimoku_snapshot(bars)
    if snapshot is None or direction == Direction.NEUTRAL:
        return Setup(False, False, False, 0.0, 0.0, None, "no directional Ichimoku setup")
    current_atr = atr(bars, settings.indicators.atr_period)[-1]
    close = bars[-1].close
    threshold = current_atr * settings.setup.location_atr_distance
    levels = (snapshot.kijun, snapshot.cloud_top, snapshot.cloud_bottom)
    nearest = min(levels, key=lambda level: abs(close - level))
    location = abs(close - nearest) <= threshold
    side_ok = (direction == Direction.LONG and close >= snapshot.cloud_top) or (
        direction == Direction.SHORT and close <= snapshot.cloud_bottom
    )
    valid = location and side_ok
    return Setup(
        valid,
        location,
        abs(close - snapshot.kijun) <= threshold,
        session_vwap(bars, settings.timezone),
        current_atr,
        nearest,
        "valid Kijun/cloud pullback" if valid else "15M Kijun/cloud location filter failed",
    )


def _ichimoku_execution(
    bars: list[Bar], direction: Direction, min_tick: float, settings: Settings
) -> ExecutionSignal:
    snapshot = _ichimoku_snapshot(bars)
    if snapshot is None or direction == Direction.NEUTRAL:
        return ExecutionSignal(False, False, "UNKNOWN")
    close = bars[-1].close
    micro = recent_bos(bars, direction, min_tick, settings.structure)
    aligned = (
        direction == Direction.LONG
        and close > snapshot.cloud_top
        and snapshot.tenkan > snapshot.kijun
    ) or (
        direction == Direction.SHORT
        and close < snapshot.cloud_bottom
        and snapshot.tenkan < snapshot.kijun
    )
    structure = classify_structure(
        find_swings(bars, settings.structure.swing_left, settings.structure.swing_right)
    )
    return ExecutionSignal(aligned and micro.bos, micro.bos, structure)


def _ichimoku_snapshot(bars: list[Bar]) -> IchimokuSnapshot | None:
    shift = 26
    if len(bars) < 78:
        return None
    tenkan = _midpoint(bars, 9)
    kijun = _midpoint(bars, 26)
    origin = bars[:-shift]
    origin_tenkan = _midpoint(origin, 9)
    origin_kijun = _midpoint(origin, 26)
    span_b = _midpoint(origin, 52)
    if None in (tenkan, kijun, origin_tenkan, origin_kijun, span_b):
        return None
    span_a = (float(origin_tenkan) + float(origin_kijun)) / 2.0
    return IchimokuSnapshot(float(tenkan), float(kijun), span_a, float(span_b))


def _midpoint(bars: list[Bar], period: int) -> float | None:
    if len(bars) < period:
        return None
    window = bars[-period:]
    return (max(bar.high for bar in window) + min(bar.low for bar in window)) / 2.0


def _empty_bias(reason: str) -> MarketBias:
    return MarketBias(Direction.NEUTRAL, 0, 0, 0, {}, (reason,))


def _empty_regime(closes: list[float]) -> Regime:
    return Regime(
        Direction.NEUTRAL,
        closes[-1] if closes else 0.0,
        0.0,
        0.0,
        "UNKNOWN",
        False,
    )


def _score_relation(
    left: float,
    right: float,
    key: str,
    components: dict[str, str],
    reasons: list[str],
    long_score: int,
    short_score: int,
) -> tuple[int, int]:
    if left > right:
        components[key] = "LONG"
        reasons.append(f"{key.replace('_', ' ')} favors LONG.")
        return long_score + 25, short_score
    if left < right:
        components[key] = "SHORT"
        reasons.append(f"{key.replace('_', ' ')} favors SHORT.")
        return long_score, short_score + 25
    components[key] = "NEUTRAL"
    return long_score, short_score


def _score_structure(
    structure: str,
    components: dict[str, str],
    reasons: list[str],
    long_score: int,
    short_score: int,
) -> tuple[int, int]:
    if structure == "HH_HL":
        components["structure"] = "LONG"
        reasons.append("Swing structure is HH/HL.")
        return long_score + 25, short_score
    if structure == "LH_LL":
        components["structure"] = "SHORT"
        reasons.append("Swing structure is LH/LL.")
        return long_score, short_score + 25
    components["structure"] = "NEUTRAL"
    reasons.append("Swing structure is mixed/ranging.")
    return long_score, short_score


def _build_bias(
    long_score: int,
    short_score: int,
    components: dict[str, str],
    reasons: list[str],
) -> MarketBias:
    if long_score > short_score:
        direction = Direction.LONG
    elif short_score > long_score:
        direction = Direction.SHORT
    else:
        direction = Direction.NEUTRAL
    return MarketBias(
        direction,
        long_score,
        short_score,
        max(long_score, short_score),
        components,
        tuple(reasons),
    )
