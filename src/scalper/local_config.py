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


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true/false")


@dataclass(frozen=True, slots=True)
class LocalConfig:
    mcp_url: str
    symbol: str
    account_id: str | None
    require_demo: bool
    poll_seconds: float
    quote_poll_seconds: float
    bar_poll_seconds: float
    account_poll_seconds: float
    max_daily_drawdown_pct: float
    oauth_file: Path
    journal_file: Path
    database_file: Path
    api_host: str
    api_port: int
    ui_origin: str
    timezone: str

    @classmethod
    def from_env(cls) -> LocalConfig:
        load_env_file()
        poll = float(os.getenv("SCALPER_POLL_SECONDS", "2.0"))
        quote_poll = float(os.getenv("SCALPER_QUOTE_POLL_SECONDS", "2.0"))
        bar_poll = float(os.getenv("SCALPER_BAR_POLL_SECONDS", "5.0"))
        account_poll = float(os.getenv("SCALPER_ACCOUNT_POLL_SECONDS", "10.0"))
        drawdown = float(os.getenv("SCALPER_MAX_DAILY_DRAWDOWN_PCT", "2.0"))
        api_port = int(os.getenv("SCALPER_API_PORT", "8000"))
        for name, value in (
            ("SCALPER_POLL_SECONDS", poll),
            ("SCALPER_QUOTE_POLL_SECONDS", quote_poll),
            ("SCALPER_BAR_POLL_SECONDS", bar_poll),
            ("SCALPER_ACCOUNT_POLL_SECONDS", account_poll),
        ):
            if value < 0.5:
                raise ValueError(f"{name} must be >= 0.5")
        if not 0 < drawdown <= 100:
            raise ValueError("SCALPER_MAX_DAILY_DRAWDOWN_PCT must be in (0, 100]")
        if not 1 <= api_port <= 65535:
            raise ValueError("SCALPER_API_PORT must be a valid TCP port")
        return cls(
            mcp_url=os.getenv("PRIMEXBT_MCP_URL", "https://api.primexbt.com/v2/mcp"),
            symbol=os.getenv("SCALPER_SYMBOL", "XAU/USD"),
            account_id=os.getenv("PRIMEXBT_ACCOUNT_ID") or None,
            require_demo=env_bool("SCALPER_REQUIRE_DEMO", True),
            poll_seconds=poll,
            quote_poll_seconds=quote_poll,
            bar_poll_seconds=bar_poll,
            account_poll_seconds=account_poll,
            max_daily_drawdown_pct=drawdown,
            oauth_file=Path(
                os.getenv("SCALPER_OAUTH_FILE", ".scalper/primexbt_oauth.json")
            ),
            journal_file=Path(
                os.getenv("SCALPER_JOURNAL_FILE", "logs/signals.jsonl")
            ),
            database_file=Path(
                os.getenv("SCALPER_DATABASE_FILE", ".scalper/analysis.db")
            ),
            api_host=os.getenv("SCALPER_API_HOST", "127.0.0.1"),
            api_port=api_port,
            ui_origin=os.getenv("SCALPER_UI_ORIGIN", "http://localhost:5173"),
            timezone=os.getenv("SCALPER_TIMEZONE", "Asia/Manila"),
        )
