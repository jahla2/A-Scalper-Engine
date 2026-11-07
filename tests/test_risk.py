import pytest

from scalper.config import RiskConfig
from scalper.models import Direction
from scalper.risk import make_trade_plan, quantity_from_contract_value


def test_trade_plan_rejects_obstacle_below_min_rr() -> None:
    cfg = RiskConfig(min_rr=1.5, target_rr=2.0)
    assert make_trade_plan(Direction.LONG, 100, 98, 1000, cfg, obstacle=102) is None


def test_trade_plan_builds_three_targets_without_obstacle() -> None:
    cfg = RiskConfig(risk_pct=0.5, min_rr=1.5, target_rr=2.0)
    plan = make_trade_plan(Direction.LONG, 100, 98, 1000, cfg)
    assert plan is not None
    assert plan.tp1 == 102
    assert plan.tp2 == 103
    assert plan.tp3 == 104
    assert plan.take_profit == plan.tp3
    assert plan.rr1 == 1
    assert plan.rr2 == 1.5
    assert plan.rr3 == 2
    assert plan.rr == 2
    assert plan.risk_budget == 5


def test_trade_plan_scales_targets_when_structure_caps_final_rr() -> None:
    cfg = RiskConfig(min_rr=1.5, target_rr=2.0)
    plan = make_trade_plan(Direction.LONG, 100, 98, 1000, cfg, obstacle=103)
    assert plan is not None
    assert plan.rr3 == pytest.approx(1.5)
    assert plan.rr1 == pytest.approx(0.75)
    assert plan.rr2 == pytest.approx(1.125)
    assert plan.tp3 == pytest.approx(103)
    assert plan.obstacle == 103


def test_short_trade_plan_orders_targets_below_entry() -> None:
    cfg = RiskConfig(min_rr=1.5, target_rr=2.0)
    plan = make_trade_plan(Direction.SHORT, 100, 102, 1000, cfg)
    assert plan is not None
    assert plan.tp1 == 98
    assert plan.tp2 == 97
    assert plan.tp3 == 96
    assert plan.stop_loss == 102


def test_quantity_requires_verified_contract_value() -> None:
    with pytest.raises(ValueError):
        quantity_from_contract_value(5, 100, 99, 0, 0.01, 10, 0.01)


def test_quantity_rounds_down_to_step() -> None:
    qty = quantity_from_contract_value(10, 100, 98, 10, 0.01, 10, 0.01)
    assert qty == 0.5
