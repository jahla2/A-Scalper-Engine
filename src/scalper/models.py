from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class Direction(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class Decision(StrEnum):
    NO_TRADE = "NO_TRADE"
    WATCH = "WATCH"
    TRADE_CANDIDATE = "TRADE_CANDIDATE"


@dataclass(frozen=True, slots=True)
class Bar:
    t: int
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0

    @property
    def body(self) -> float:
        return abs(self.c - self.o)

    @property
    def range(self) -> float:
        return max(0.0, self.h - self.l)


@dataclass(frozen=True, slots=True)
class Swing:
    index: int
    price: float
    kind: str


@dataclass(frozen=True, slots=True)
class Regime:
    direction: Direction
    close: float
    ema50: float
    ema200: float
    structure: str
    slope_ok: bool


@dataclass(frozen=True, slots=True)
class Setup:
    valid: bool
    location_valid: bool
    level_aligned: bool
    vwap: float
    atr: float
    nearest_level: float | None
    reason: str


@dataclass(frozen=True, slots=True)
class StructureSignal:
    direction: Direction
    bos: bool
    bos_level: float | None
    bos_index: int | None
    bos_time: int | None
    displacement: bool
    retest: bool
    atr: float
    reason: str


@dataclass(frozen=True, slots=True)
class ExecutionSignal:
    confirmed: bool
    micro_bos: bool
    structure: str


@dataclass(frozen=True, slots=True)
class TradePlan:
    entry: float
    stop_loss: float
    take_profit: float
    rr: float
    risk_budget: float


@dataclass(frozen=True, slots=True)
class Score:
    total: int
    threshold: int
    parts: dict[str, int]


@dataclass(frozen=True, slots=True)
class Signal:
    strategy: str
    symbol: str
    timestamp: int
    decision: Decision
    direction: Direction
    score: Score
    regime: Regime
    setup: Setup
    structure: StructureSignal
    execution: ExecutionSignal
    trade: TradePlan | None
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["decision"] = self.decision.value
        data["direction"] = self.direction.value
        data["regime"]["direction"] = self.regime.direction.value
        data["structure"]["direction"] = self.structure.direction.value
        return data


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    symbol: str
    min_qty: float
    max_qty: float
    qty_step: float
    min_price_step: float
    price_scale: int


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    ask: float
    bid: float
    price: float
    market_open: bool

    @property
    def spread(self) -> float:
        return max(0.0, self.ask - self.bid)
