from __future__ import annotations

import math

from .config import RiskConfig, StructureConfig
from .models import Bar, Direction, TradePlan
from .structure import find_swings, latest_swing


def structural_stop(
    bars: list[Bar],
    direction: Direction,
    current_atr: float,
    risk: RiskConfig,
    structure: StructureConfig,
) -> float | None:
    swings = find_swings(bars, structure.swing_left, structure.swing_right)
    if direction == Direction.LONG:
        swing = latest_swing(swings, "LOW")
        return None if swing is None else swing.price - current_atr * risk.stop_atr_buffer
    if direction == Direction.SHORT:
        swing = latest_swing(swings, "HIGH")
        return None if swing is None else swing.price + current_atr * risk.stop_atr_buffer
    return None


def opposing_level(
    bars: list[Bar], direction: Direction, entry: float, structure: StructureConfig
) -> float | None:
    swings = find_swings(bars, structure.swing_left, structure.swing_right)
    if direction == Direction.LONG:
        levels = sorted({s.price for s in swings if s.kind == "HIGH" and s.price > entry})
        return levels[0] if levels else None
    if direction == Direction.SHORT:
        levels = sorted(
            {s.price for s in swings if s.kind == "LOW" and s.price < entry},
            reverse=True,
        )
        return levels[0] if levels else None
    return None


def make_trade_plan(
    direction: Direction,
    entry: float,
    stop: float,
    equity: float,
    risk: RiskConfig,
    obstacle: float | None = None,
) -> TradePlan | None:
    distance = abs(entry - stop)
    if distance <= 0:
        return None
    if direction == Direction.LONG and stop >= entry:
        return None
    if direction == Direction.SHORT and stop <= entry:
        return None

    target_distance = distance * risk.target_rr
    target = entry + target_distance if direction == Direction.LONG else entry - target_distance

    if obstacle is not None:
        if direction == Direction.LONG and obstacle > entry:
            target = min(target, obstacle)
        elif direction == Direction.SHORT and obstacle < entry:
            target = max(target, obstacle)

    rr = abs(target - entry) / distance
    if rr + 1e-9 < risk.min_rr:
        return None
    return TradePlan(
        entry=entry,
        stop_loss=stop,
        take_profit=target,
        rr=rr,
        risk_budget=equity * (risk.risk_pct / 100.0),
    )


def quantity_from_contract_value(
    risk_budget: float,
    entry: float,
    stop: float,
    contract_value_per_price_unit: float,
    min_qty: float,
    max_qty: float,
    qty_step: float,
) -> float:
    """Size only when a verified broker contract multiplier is configured.

    The PrimeXBT symbol metadata exposed by MCP does not include a contract multiplier,
    so the engine deliberately refuses to infer it from leverage or margin.
    """
    if contract_value_per_price_unit <= 0:
        raise ValueError("verified contract_value_per_price_unit is required")
    unit_risk = abs(entry - stop) * contract_value_per_price_unit
    if unit_risk <= 0:
        raise ValueError("invalid stop distance")
    raw = risk_budget / unit_risk
    steps = math.floor((raw + 1e-12) / qty_step)
    qty = steps * qty_step
    if qty < min_qty:
        raise ValueError("risk budget is too small for minimum quantity")
    return min(qty, max_qty)
