from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True, slots=True)
class LocalConfig:
    mcp_url: str
    symbol: str
    account_id: str | None
    poll_seconds: float
    max_daily_drawdown_pct: float
    oauth_file: Path
    journal_file: Path

    @classmethod
    def from_env(cls) -> "LocalConfig":
        load_env_file()
        poll = float(os.getenv("SCALPER_POLL_SECONDS", "2.0"))
        drawdown = float(os.getenv("SCALPER_MAX_DAILY_DRAWDOWN_PCT", "2.0"))
        if poll < 0.5:
            raise ValueError("SCALPER_POLL_SECONDS must be >= 0.5")
        if not 0 < drawdown <= 100:
            raise ValueError("SCALPER_MAX_DAILY_DRAWDOWN_PCT must be in (0, 100]")
        return cls(
            mcp_url=os.getenv("PRIMEXBT_MCP_URL", "https://api.primexbt.com/v2/mcp"),
            symbol=os.getenv("SCALPER_SYMBOL", "XAU/USD"),
            account_id=os.getenv("PRIMEXBT_ACCOUNT_ID") or None,
            poll_seconds=poll,
            max_daily_drawdown_pct=drawdown,
            oauth_file=Path(os.getenv("SCALPER_OAUTH_FILE", ".scalper/primexbt_oauth.json")),
            journal_file=Path(os.getenv("SCALPER_JOURNAL_FILE", "logs/signals.jsonl")),
        )
