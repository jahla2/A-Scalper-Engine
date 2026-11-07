from __future__ import annotations

import asyncio
from time import time

from .broker import PrimeXBTBroker
from .config import Settings
from .models import (
    Decision,
    Direction,
    ExecutionSignal,
    Setup,
    Signal,
    StructureSignal,
)
from .risk import make_trade_plan, opposing_level, structural_stop
from .strategy import execution, market_bias, regime, score_setup, setup
from .structure import recent_bos
from .timeframes import closed_bars


class ScalperEngine:
    def __init__(self, broker: PrimeXBTBroker, settings: Settings | None = None) -> None:
        self.broker = broker
        self.settings = settings or Settings()

    async def scan(self, requested_symbol: str, now: int | None = None) -> Signal:
        now = int(time()) if now is None else now
        symbol = await self.broker.resolve_symbol(requested_symbol)
        info = await self.broker.symbol_info(symbol)
        bars_1h_raw, bars_15m_raw, bars_5m_raw, quote, snapshot = await asyncio.gather(
            self.broker.bars(symbol, "1H", self.settings.bars_1h),
            self.broker.bars(symbol, "15M", self.settings.bars_15m),
            self.broker.bars(symbol, "5M", self.settings.bars_5m),
            self.broker.quote(symbol),
            self.broker.snapshot(),
        )
        bars_1h = closed_bars(bars_1h_raw, "1H", now)
        bars_15m = closed_bars(bars_15m_raw, "15M", now)
        bars_5m = closed_bars(bars_5m_raw, "5M", now)

        empty_setup = Setup(False, False, False, 0.0, 0.0, None, "not evaluated")
        empty_structure = StructureSignal(
            Direction.NEUTRAL, False, None, None, None, False, False, 0.0, "not evaluated"
        )
        empty_execution = ExecutionSignal(False, False, "UNKNOWN")
        reg = regime(bars_1h, self.settings)
        bias = market_bias(bars_1h, self.settings)
        if reg.direction == Direction.NEUTRAL:
            return Signal(
                "A_PLUS_SCALPER_V1", symbol, now, Decision.NO_TRADE, reg.direction,
                bias,
                score_setup(
                    reg,
                    empty_setup,
                    empty_structure,
                    empty_execution,
                    False,
                    now,
                    self.settings,
                ),
                reg, empty_setup, empty_structure, empty_execution, None,
                (
                    "Strict 1H regime is neutral; trend and swing structure are not fully aligned.",
                    f"Directional alignment currently leans {bias.direction.value} "
                    f"({bias.strength}/100 rule alignment).",
                ),
            )

        stp = setup(bars_15m, reg.direction, self.settings)
        if not stp.valid:
            return Signal(
                "A_PLUS_SCALPER_V1", symbol, now, Decision.NO_TRADE, reg.direction,
                bias,
                score_setup(
                    reg,
                    stp,
                    empty_structure,
                    empty_execution,
                    False,
                    now,
                    self.settings,
                ),
                reg, stp, empty_structure, empty_execution, None,
                (stp.reason,),
            )

        structure = recent_bos(bars_5m, reg.direction, info.min_price_step, self.settings.structure)
        if not structure.bos:
            return Signal(
                "A_PLUS_SCALPER_V1", symbol, now, Decision.WATCH, reg.direction,
                bias,
                score_setup(
                    reg,
                    stp,
                    structure,
                    empty_execution,
                    False,
                    now,
                    self.settings,
                ),
                reg, stp, structure, empty_execution, None,
                ("setup valid; waiting for confirmed 5M BOS",),
            )

        bars_1m_raw = await self.broker.bars(symbol, "1M", self.settings.bars_1m)
        bars_1m = closed_bars(bars_1m_raw, "1M", now)
        exe = execution(bars_1m, reg.direction, info.min_price_step, self.settings)

        entry = quote.ask if reg.direction == Direction.LONG else quote.bid
        stop = structural_stop(
            bars_5m, reg.direction, structure.atr, self.settings.risk, self.settings.structure
        )
        obstacle = opposing_level(bars_15m, reg.direction, entry, self.settings.structure)
        equity = float(snapshot.get("equity", 0.0))
        entry_reason = (
            "Current ask after confirmed 5M BOS; 1M execution is confirmed."
            if reg.direction == Direction.LONG and exe.confirmed
            else "Current bid after confirmed 5M BOS; 1M execution is confirmed."
            if reg.direction == Direction.SHORT and exe.confirmed
            else "Current executable quote after 5M BOS; waiting for 1M execution confirmation."
        )
        plan = None if stop is None else make_trade_plan(
            reg.direction,
            entry,
            stop,
            equity,
            self.settings.risk,
            obstacle,
            status="READY" if exe.confirmed else "PROVISIONAL",
            entry_reason=entry_reason,
        )
        rr_ok = plan is not None
        score = score_setup(reg, stp, structure, exe, rr_ok, now, self.settings)

        spread_ok = structure.atr > 0 and (
            quote.spread / structure.atr <= self.settings.risk.max_spread_atr_ratio
        )
        reasons: list[str] = []
        if not quote.market_open:
            reasons.append("market is closed")
        if not spread_ok:
            reasons.append("spread is too large relative to 5M ATR")
        if plan is None:
            reasons.append("minimum reward-to-risk is not available")
        if not structure.displacement:
            reasons.append("BOS lacks displacement")
        if not structure.retest:
            reasons.append("BOS retest not confirmed")
        if not exe.confirmed:
            reasons.append("1M execution confirmation is not ready")

        candidate = (
            quote.market_open
            and spread_ok
            and plan is not None
            and structure.displacement
            and structure.retest
            and exe.confirmed
            and score.total >= score.threshold
        )
        decision = Decision.TRADE_CANDIDATE if candidate else Decision.WATCH
        if candidate:
            reasons.append(
                "A+ threshold reached with displacement, retest, and 1M execution confirmation"
            )
        elif not reasons:
            reasons.append("score below A+ threshold")

        return Signal(
            "A_PLUS_SCALPER_V1",
            symbol,
            now,
            decision,
            reg.direction,
            bias,
            score,
            reg,
            stp,
            structure,
            exe,
            plan,
            tuple(reasons),
        )

    async def preview(self, signal: Signal, qty: float) -> dict:
        if signal.decision != Decision.TRADE_CANDIDATE or signal.trade is None:
            raise ValueError("only TRADE_CANDIDATE signals can be previewed")
        info = await self.broker.symbol_info(signal.symbol)
        rounded = round(qty / info.qty_step) * info.qty_step
        if abs(rounded - qty) > 1e-9 or qty < info.min_qty or qty > info.max_qty:
            raise ValueError("quantity violates PrimeXBT min/max/step rules")
        if await self.broker.has_symbol_exposure(signal.symbol):
            raise ValueError("symbol already has an open position or working entry order")
        side = "BUY" if signal.direction == Direction.LONG else "SELL"
        client_id = f"aplus-{signal.symbol.replace('/', '')}-{signal.structure.bos_time}"
        preview = await self.broker.preview_order(
            symbol=signal.symbol,
            side=side,
            qty=qty,
            stop_loss=signal.trade.stop_loss,
            take_profit=signal.trade.take_profit,
            client_order_id=client_id,
        )
        return dict(preview)

    async def execute_preview(self, preview: dict) -> dict:
        return dict(await self.broker.place_previewed_order(preview))
