from __future__ import annotations

from .config import Settings
from .indicators import atr, ema, session_vwap
from .models import (
    Bar,
    Direction,
    ExecutionSignal,
    Regime,
    Score,
    Setup,
    StructureSignal,
)
from .session import preferred_scalping_window
from .structure import classify_structure, find_swings, recent_bos


def regime(bars: list[Bar], settings: Settings) -> Regime:
    cfg = settings.indicators
    closes = [b.close for b in bars]
    if len(closes) < cfg.ema_slow + cfg.ema_slope_bars + 1:
        close = closes[-1] if closes else 0.0
        return Regime(Direction.NEUTRAL, close, 0.0, 0.0, "UNKNOWN", False)
    fast = ema(closes, cfg.ema_fast)
    slow = ema(closes, cfg.ema_slow)
    swings = find_swings(bars, settings.structure.swing_left, settings.structure.swing_right)
    market_structure = classify_structure(swings)
    slope_up = fast[-1] > fast[-1 - cfg.ema_slope_bars]
    slope_down = fast[-1] < fast[-1 - cfg.ema_slope_bars]
    close = closes[-1]

    if close > slow[-1] and fast[-1] > slow[-1] and slope_up and market_structure == "HH_HL":
        direction = Direction.LONG
        slope_ok = True
    elif close < slow[-1] and fast[-1] < slow[-1] and slope_down and market_structure == "LH_LL":
        direction = Direction.SHORT
        slope_ok = True
    else:
        direction = Direction.NEUTRAL
        slope_ok = slope_up or slope_down
    return Regime(direction, close, fast[-1], slow[-1], market_structure, slope_ok)


def setup(bars: list[Bar], direction: Direction, settings: Settings) -> Setup:
    if not bars or direction == Direction.NEUTRAL:
        return Setup(False, False, False, 0.0, 0.0, None, "neutral regime")
    closes = [b.close for b in bars]
    fast = ema(closes, settings.indicators.ema_fast)[-1]
    current_atr = atr(bars, settings.indicators.atr_period)[-1]
    vwap = session_vwap(bars, settings.timezone)
    close = closes[-1]
    swings = find_swings(bars, settings.structure.swing_left, settings.structure.swing_right)

    if direction == Direction.LONG:
        support = [s.price for s in swings if s.kind == "LOW" and s.price <= close]
        nearest = max(support) if support else None
        vwap_side = close >= vwap
    else:
        resistance = [s.price for s in swings if s.kind == "HIGH" and s.price >= close]
        nearest = min(resistance) if resistance else None
        vwap_side = close <= vwap

    threshold = current_atr * settings.setup.location_atr_distance
    distances = [abs(close - fast), abs(close - vwap)]
    if nearest is not None:
        distances.append(abs(close - nearest))
    location_valid = min(distances) <= threshold if threshold > 0 else False
    level_aligned = nearest is not None and abs(close - nearest) <= threshold
    valid = location_valid and (vwap_side or not settings.setup.require_vwap_side)
    reason = "valid pullback/location" if valid else "location or VWAP filter failed"
    return Setup(valid, location_valid, level_aligned, vwap, current_atr, nearest, reason)


def execution(
    bars: list[Bar], direction: Direction, min_tick: float, settings: Settings
) -> ExecutionSignal:
    swings = find_swings(bars, settings.structure.swing_left, settings.structure.swing_right)
    structure = classify_structure(swings)
    micro = recent_bos(bars, direction, min_tick, settings.structure)
    aligned = (direction == Direction.LONG and structure == "HH_HL") or (
        direction == Direction.SHORT and structure == "LH_LL"
    )
    return ExecutionSignal(confirmed=aligned or micro.bos, micro_bos=micro.bos, structure=structure)


def score_setup(
    reg: Regime,
    stp: Setup,
    structure: StructureSignal,
    exe: ExecutionSignal,
    rr_ok: bool,
    timestamp: int,
    settings: Settings,
) -> Score:
    cfg = settings.score
    parts = {
        "regime": cfg.regime if reg.direction != Direction.NEUTRAL else 0,
        "location": cfg.location if stp.location_valid else 0,
        "level": cfg.level if stp.level_aligned else 0,
        "bos": cfg.bos if structure.bos else 0,
        "displacement": cfg.displacement if structure.displacement else 0,
        "retest": cfg.retest if structure.retest else 0,
        "session": cfg.session if preferred_scalping_window(timestamp, settings.timezone) else 0,
        "micro": cfg.micro if exe.confirmed else 0,
        "rr": cfg.rr if rr_ok else 0,
    }
    return Score(sum(parts.values()), cfg.threshold, parts)
