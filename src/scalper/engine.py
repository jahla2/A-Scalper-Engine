from __future__ import annotations

import asyncio
from time import time

from .broker import PrimeXBTBroker
from .config import Settings
from .models import Decision, Direction, Signal
from .risk import make_trade_plan, opposing_level, structural_stop
from .strategy import score_setup
from .strategy_catalog import DEFAULT_STRATEGY, get_strategy
from .strategy_modes import evaluate_strategy
from .timeframes import closed_bars


class ScalperEngine:
    def __init__(
        self,
        broker: PrimeXBTBroker,
        settings: Settings | None = None,
        *,
        strategy_id: str = DEFAULT_STRATEGY,
    ) -> None:
        self.broker = broker
        self.settings = settings or Settings()
        self.strategy_id = get_strategy(strategy_id).strategy_id

    @property
    def strategy(self):
        return get_strategy(self.strategy_id)

    def set_strategy(self, strategy_id: str) -> None:
        self.strategy_id = get_strategy(strategy_id).strategy_id

    async def scan(self, requested_symbol: str, now: int | None = None) -> Signal:
        now = int(time()) if now is None else now
        symbol = await self.broker.resolve_symbol(requested_symbol)
        info = await self.broker.symbol_info(symbol)

        (
            bars_1h_raw,
            bars_15m_raw,
            bars_5m_raw,
            bars_1m_raw,
            quote,
            account_snapshot,
        ) = await asyncio.gather(
            self.broker.bars(symbol, "1H", self.settings.bars_1h),
            self.broker.bars(symbol, "15M", self.settings.bars_15m),
            self.broker.bars(symbol, "5M", self.settings.bars_5m),
            self.broker.bars(symbol, "1M", self.settings.bars_1m),
            self.broker.quote(symbol),
            self.broker.snapshot(),
        )

        bars_1h = closed_bars(bars_1h_raw, "1H", now)
        bars_15m = closed_bars(bars_15m_raw, "15M", now)
        bars_5m = closed_bars(bars_5m_raw, "5M", now)
        bars_1m = closed_bars(bars_1m_raw, "1M", now)

        evaluated = evaluate_strategy(
            self.strategy_id,
            bars_1h,
            bars_15m,
            bars_5m,
            bars_1m,
            info.min_price_step,
            self.settings,
        )
        reg = evaluated.regime
        bias = evaluated.bias
        stp = evaluated.setup
        structure = evaluated.structure
        exe = evaluated.execution

        plan = None
        if reg.direction != Direction.NEUTRAL and structure.bos:
            entry = quote.ask if reg.direction == Direction.LONG else quote.bid
            stop = structural_stop(
                bars_5m,
                reg.direction,
                structure.atr,
                self.settings.risk,
                self.settings.structure,
            )
            obstacle = opposing_level(
                bars_15m,
                reg.direction,
                entry,
                self.settings.structure,
            )
            equity = float(account_snapshot.get("equity", 0.0))
            execution_ready = (
                stp.valid
                and structure.displacement
                and structure.retest
                and exe.confirmed
            )
            if stop is not None:
                plan = make_trade_plan(
                    reg.direction,
                    entry,
                    stop,
                    equity,
                    self.settings.risk,
                    obstacle,
                    status="READY" if execution_ready else "PROVISIONAL",
                    entry_reason=(
                        f"Current {'ask' if reg.direction == Direction.LONG else 'bid'} "
                        f"after {self.strategy.name} produced a confirmed 5M BOS; "
                        + (
                            "1M execution is confirmed."
                            if exe.confirmed
                            else "1M execution confirmation is still pending."
                        )
                    ),
                )

        rr_ok = plan is not None
        score = score_setup(
            reg,
            stp,
            structure,
            exe,
            rr_ok,
            now,
            self.settings,
        )

        spread_ok = structure.atr > 0 and (
            quote.spread / structure.atr <= self.settings.risk.max_spread_atr_ratio
        )
        reasons: list[str] = list(evaluated.notes)

        if reg.direction == Direction.NEUTRAL:
            reasons.append(
                "1H strict regime is neutral, so no trade can qualify yet; "
                "15M, 5M and 1M were still evaluated for diagnostics."
            )
        if not stp.valid:
            reasons.append(f"15M setup is not valid: {stp.reason}.")
        if not structure.bos:
            reasons.append(f"5M confirmation is not ready: {structure.reason}.")
        elif not structure.displacement:
            reasons.append("5M BOS exists but displacement is not confirmed.")
        elif not structure.retest:
            reasons.append("5M BOS exists but retest is not confirmed.")
        if not exe.confirmed:
            reasons.append(
                f"1M execution is not confirmed; current micro structure is {exe.structure}."
            )
        if not quote.market_open:
            reasons.append("Market is closed.")
        if not spread_ok:
            reasons.append("Spread is too large relative to 5M ATR.")
        if reg.direction != Direction.NEUTRAL and structure.bos and plan is None:
            reasons.append(
                "No valid structural trade plan: stop/target geometry cannot satisfy minimum RR."
            )

        candidate = (
            reg.direction != Direction.NEUTRAL
            and stp.valid
            and structure.bos
            and structure.displacement
            and structure.retest
            and exe.confirmed
            and quote.market_open
            and spread_ok
            and plan is not None
            and score.total >= score.threshold
        )

        if candidate:
            decision = Decision.TRADE_CANDIDATE
            reasons.append(
                "All selected-strategy stages and A+ safety gates are aligned."
            )
        elif reg.direction == Direction.NEUTRAL or not stp.valid:
            decision = Decision.NO_TRADE
        else:
            decision = Decision.WATCH

        if not candidate and score.total < score.threshold:
            reasons.append(
                f"Setup score is {score.total}/{score.threshold}; threshold not reached."
            )

        return Signal(
            self.strategy.code,
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
            tuple(dict.fromkeys(reasons)),
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
