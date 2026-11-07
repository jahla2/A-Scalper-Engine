from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class JsonlJournal:
    """Non-blocking append-only journal for signals and broker events."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()

    async def append(self, event: dict[str, Any]) -> None:
        line = json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n"
        async with self._lock:
            await asyncio.to_thread(self._append_sync, line)

    def _append_sync(self, line: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
