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
    *,
    status: str = "PROVISIONAL",
    entry_reason: str = "Current executable quote after structure confirmation.",
) -> TradePlan | None:
    """Build a deterministic three-target plan from structural risk.

    TP3 is the final target. It starts at target_rr and is capped by the nearest
    opposing 15M swing. TP1/TP2 are deterministic milestones toward the reachable
    final target. If the final target cannot satisfy min_rr, no plan is returned.
    """
    distance = abs(entry - stop)
    if distance <= 0:
        return None
    if direction == Direction.LONG and stop >= entry:
        return None
    if direction == Direction.SHORT and stop <= entry:
        return None

    obstacle_rr: float | None = None
    valid_obstacle = False
    if obstacle is not None:
        valid_obstacle = (
            direction == Direction.LONG and obstacle > entry
        ) or (
            direction == Direction.SHORT and obstacle < entry
        )
        if valid_obstacle:
            obstacle_rr = abs(obstacle - entry) / distance

    final_rr = risk.target_rr
    if obstacle_rr is not None:
        final_rr = min(final_rr, obstacle_rr)

    if final_rr + 1e-9 < risk.min_rr:
        return None

    rr1 = min(1.0, final_rr * 0.50)
    rr2 = min(1.5, final_rr * 0.75)
    rr3 = final_rr

    def price_at(rr_value: float) -> float:
        delta = distance * rr_value
        return entry + delta if direction == Direction.LONG else entry - delta

    tp1 = price_at(rr1)
    tp2 = price_at(rr2)
    tp3 = price_at(rr3)

    if obstacle_rr is not None and obstacle_rr <= risk.target_rr + 1e-9:
        tp3_reason = (
            f"Final target capped by nearest opposing 15M swing at {obstacle:.6f}; "
            f"reachable RR is {rr3:.2f}R."
        )
    else:
        tp3_reason = f"Final target uses configured {risk.target_rr:.2f}R objective."

    side = "below" if direction == Direction.LONG else "above"
    swing_kind = "5M swing low" if direction == Direction.LONG else "5M swing high"

    return TradePlan(
        status=status,
        entry=entry,
        stop_loss=stop,
        take_profit=tp3,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        rr=rr3,
        rr1=rr1,
        rr2=rr2,
        rr3=rr3,
        risk_budget=equity * (risk.risk_pct / 100.0),
        obstacle=obstacle if valid_obstacle else None,
        entry_reason=entry_reason,
        stop_reason=(
            f"Invalidation sits {side} the latest confirmed {swing_kind} "
            f"with a {risk.stop_atr_buffer:.2f} ATR buffer."
        ),
        tp1_reason=f"First partial milestone at {rr1:.2f}R.",
        tp2_reason=f"Second partial milestone at {rr2:.2f}R.",
        tp3_reason=tp3_reason,
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
