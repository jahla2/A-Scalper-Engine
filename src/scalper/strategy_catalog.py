from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    strategy_id: str
    code: str
    name: str
    origin: str
    style: str
    description: str
    timeframes: tuple[str, ...]
    evidence_note: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["timeframes"] = list(self.timeframes)
        return data


DEFAULT_STRATEGY = "a_plus_structure"

STRATEGIES: dict[str, StrategyDefinition] = {
    "a_plus_structure": StrategyDefinition(
        strategy_id="a_plus_structure",
        code="A_PLUS_SCALPER_V1",
        name="A+ Structure MTF",
        origin="Systematic multi-timeframe",
        style="Structure / trend-following scalper",
        description=(
            "EMA regime, 15M location, 5M body-close BOS/displacement/retest, "
            "then 1M execution refinement."
        ),
        timeframes=("1H", "15M", "5M", "1M"),
        evidence_note=(
            "Combines established technical-analysis concepts; strategy thresholds are "
            "project rules that still require backtesting."
        ),
    ),
    "ichimoku_mtf": StrategyDefinition(
        strategy_id="ichimoku_mtf",
        code="ICHIMOKU_MTF_V1",
        name="Ichimoku MTF",
        origin="Japanese-origin: Goichi Hosoda",
        style="Trend / momentum / support-resistance",
        description=(
            "Uses Ichimoku cloud direction on 1H, Kijun/cloud location on 15M, "
            "5M structure confirmation and 1M Tenkan/Kijun execution."
        ),
        timeframes=("1H", "15M", "5M", "1M"),
        evidence_note=(
            "Ichimoku is a Japanese trend-following system; this multi-timeframe entry "
            "implementation is our deterministic adaptation."
        ),
    ),
    "ema_20_50_pullback": StrategyDefinition(
        strategy_id="ema_20_50_pullback",
        code="EMA_20_50_PULLBACK_V1",
        name="EMA 20/50 Pullback",
        origin="Common trend-following technique",
        style="Fast pullback scalper",
        description=(
            "Uses 20/50 EMA trend alignment, a 15M pullback location, 5M structure "
            "confirmation and 1M EMA/micro-structure trigger."
        ),
        timeframes=("1H", "15M", "5M", "1M"),
        evidence_note=(
            "Moving averages are widely used trend tools; the 20/50 periods and exact "
            "entry gates are implementation choices to validate in backtests."
        ),
    ),
    "vwap_momentum": StrategyDefinition(
        strategy_id="vwap_momentum",
        code="VWAP_MOMENTUM_V1",
        name="VWAP Momentum",
        origin="Volume-weighted execution / intraday analysis",
        style="Intraday momentum scalper",
        description=(
            "Uses 1H trend context, 15M VWAP location, 5M structure/momentum and "
            "1M VWAP-side execution confirmation."
        ),
        timeframes=("1H", "15M", "5M", "1M"),
        evidence_note=(
            "VWAP is a standard volume-weighted benchmark/tool; this is an intraday "
            "signal adaptation, not an institutional execution algorithm."
        ),
    ),
}


def get_strategy(strategy_id: str) -> StrategyDefinition:
    try:
        return STRATEGIES[strategy_id]
    except KeyError as exc:
        choices = ", ".join(sorted(STRATEGIES))
        raise ValueError(f"unknown strategy {strategy_id!r}; choices={choices}") from exc


def list_strategies() -> list[dict[str, object]]:
    return [item.to_dict() for item in STRATEGIES.values()]
