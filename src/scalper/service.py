from __future__ import annotations

from .engine import ScalperEngine
from .journal import JsonlJournal


class ScalperService:
    def __init__(self, engine: ScalperEngine, journal: JsonlJournal | None = None) -> None:
        self.engine = engine
        self.journal = journal

    async def scan(self, symbol: str) -> dict:
        signal = await self.engine.scan(symbol)
        payload = signal.to_dict()
        if self.journal is not None:
            await self.journal.append({"type": "signal", "data": payload})
        return payload
