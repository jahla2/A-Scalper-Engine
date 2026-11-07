from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any


class AnalysisStore:
    """Small local SQLite store for analysis history and UI filtering."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    async def append(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            await asyncio.to_thread(self._append_sync, payload)

    async def latest(self, symbol: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._latest_sync, symbol)

    async def history(
        self,
        *,
        symbol: str | None = None,
        decision: str | None = None,
        direction: str | None = None,
        min_score: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        return await asyncio.to_thread(
            self._history_sync,
            symbol,
            decision,
            direction,
            min_score,
            safe_limit,
        )

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analysis_symbol_time
                ON analysis_events(symbol, timestamp DESC)
                """
            )

    def _append_sync(self, payload: dict[str, Any]) -> None:
        score = payload.get("score", {})
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_events(
                    timestamp, symbol, decision, direction, score, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(payload["timestamp"]),
                    str(payload["symbol"]),
                    str(payload["decision"]),
                    str(payload["direction"]),
                    int(score.get("total", 0)),
                    json.dumps(payload, separators=(",", ":"), sort_keys=True),
                ),
            )

    def _latest_sync(self, symbol: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM analysis_events
                WHERE symbol = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def _history_sync(
        self,
        symbol: str | None,
        decision: str | None,
        direction: str | None,
        min_score: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if symbol:
            clauses.append("symbol = ?")
            values.append(symbol)
        if decision:
            clauses.append("decision = ?")
            values.append(decision)
        if direction:
            clauses.append("direction = ?")
            values.append(direction)
        if min_score is not None:
            clauses.append("score >= ?")
            values.append(min_score)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(limit)
        query = (
            "SELECT payload_json FROM analysis_events "
            f"{where} ORDER BY timestamp DESC, id DESC LIMIT ?"
        )
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]
