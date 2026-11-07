from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from time import time
from zoneinfo import ZoneInfo

from .broker import PrimeXBTBroker
from .engine import ScalperEngine
from .journal import JsonlJournal
from .models import Decision, Signal
from .timeframes import closed_bars


@dataclass(slots=True)
class DailyLossGuard:
    max_drawdown_pct: float
    timezone: str = "Asia/Manila"
    day: date | None = None
    baseline_equity: float | None = None

    def update(self, equity: float, timestamp: int) -> tuple[bool, float]:
        current_day = datetime.fromtimestamp(timestamp, ZoneInfo(self.timezone)).date()
        if self.day != current_day or self.baseline_equity is None:
            self.day = current_day
            self.baseline_equity = equity
            return True, 0.0
        if self.baseline_equity <= 0:
            return False, 100.0
        drawdown = max(0.0, (self.baseline_equity - equity) / self.baseline_equity * 100.0)
        return drawdown < self.max_drawdown_pct, drawdown


class RealtimeRunner:
    """Candle-driven watcher. Full strategy scans happen only after a new closed 1M bar."""

    def __init__(
        self,
        broker: PrimeXBTBroker,
        engine: ScalperEngine,
        symbol: str,
        *,
        poll_seconds: float = 2.0,
        max_daily_drawdown_pct: float = 2.0,
        journal: JsonlJournal | None = None,
    ) -> None:
        self.broker = broker
        self.engine = engine
        self.symbol = symbol
        self.poll_seconds = poll_seconds
        self.guard = DailyLossGuard(max_daily_drawdown_pct)
        self.journal = journal
        self._last_closed_1m: int | None = None
        self._last_candidate_key: tuple[str, int | None] | None = None

    async def _new_closed_minute(self, now: int) -> bool:
        bars = await self.broker.bars(self.symbol, "1M", 3)
        closed = closed_bars(bars, "1M", now)
        if not closed:
            return False
        latest = closed[-1].t
        if self._last_closed_1m is None or latest > self._last_closed_1m:
            self._last_closed_1m = latest
            return True
        return False

    async def scan_once(self) -> Signal:
        now = int(time())
        signal = await self.engine.scan(self.symbol, now)
        snapshot = await self.broker.snapshot()
        equity = float(snapshot.get("equity", 0.0))
        allowed, drawdown = self.guard.update(equity, now)
        payload = signal.to_dict()
        payload["runtime"] = {
            "equity": equity,
            "daily_drawdown_pct": drawdown,
            "risk_guard_allowed": allowed,
        }
        if self.journal is not None:
            await self.journal.append({"type": "signal", "data": payload})
        print(
            f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] "
            f"{signal.symbol} {signal.decision.value} {signal.direction.value} "
            f"score={signal.score.total}/{signal.score.threshold} dailyDD={drawdown:.2f}%"
        )
        if signal.reasons:
            print("  " + " | ".join(signal.reasons))
        if signal.decision == Decision.TRADE_CANDIDATE:
            key = (signal.direction.value, signal.structure.bos_time)
            if key != self._last_candidate_key:
                self._last_candidate_key = key
                message = "NEW A+ TRADE CANDIDATE" if allowed else "CANDIDATE BLOCKED BY LOSS GUARD"
                print(f"  >>> {message} (analysis only; no MCP auto execution)")
        return signal

    async def run(self) -> None:
        await self.broker.resolve_symbol(self.symbol)
        print(
            f"Watching {self.symbol}. Full scans happen on newly closed 1M candles. "
            "Press Ctrl+C to stop."
        )
        while True:
            now = int(time())
            try:
                if await self._new_closed_minute(now):
                    await self.scan_once()
            except Exception as exc:
                print(f"runtime read/scan error: {exc}")
            await asyncio.sleep(self.poll_seconds)
