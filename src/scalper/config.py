from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndicatorConfig:
    ema_fast: int = 50
    ema_slow: int = 200
    atr_period: int = 14
    ema_slope_bars: int = 3


@dataclass(frozen=True, slots=True)
class StructureConfig:
    swing_left: int = 2
    swing_right: int = 2
    bos_atr_buffer: float = 0.05
    bos_min_ticks: int = 2
    bos_lookback: int = 8
    displacement_body_ratio: float = 0.60
    displacement_atr_ratio: float = 0.80
    retest_atr_zone: float = 0.15
    retest_lookback: int = 4


@dataclass(frozen=True, slots=True)
class SetupConfig:
    location_atr_distance: float = 0.50
    level_cluster_atr: float = 0.25
    require_vwap_side: bool = True


@dataclass(frozen=True, slots=True)
class RiskConfig:
    risk_pct: float = 0.25
    max_risk_pct: float = 0.50
    min_rr: float = 1.50
    target_rr: float = 2.00
    stop_atr_buffer: float = 0.15
    max_spread_atr_ratio: float = 0.10


@dataclass(frozen=True, slots=True)
class ScoreConfig:
    threshold: int = 85
    regime: int = 20
    location: int = 15
    level: int = 10
    bos: int = 20
    displacement: int = 10
    retest: int = 10
    session: int = 5
    micro: int = 5
    rr: int = 5


@dataclass(frozen=True, slots=True)
class Settings:
    indicators: IndicatorConfig = IndicatorConfig()
    structure: StructureConfig = StructureConfig()
    setup: SetupConfig = SetupConfig()
    risk: RiskConfig = RiskConfig()
    score: ScoreConfig = ScoreConfig()
    timezone: str = "Asia/Manila"
    bars_1h: int = 300
    bars_15m: int = 300
    bars_5m: int = 300
    bars_1m: int = 150
