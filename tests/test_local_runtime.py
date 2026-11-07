import pytest

from scalper.local_config import LocalConfig
from scalper.mcp_client import raw_tool_name
from scalper.runtime import DailyLossGuard


def test_raw_mcp_tool_name_is_normalized() -> None:
    assert raw_tool_name("mcp__PrimeXBT__get_bars") == "get_bars"
    assert raw_tool_name("get_bars") == "get_bars"


def test_daily_loss_guard_resets_and_blocks() -> None:
    guard = DailyLossGuard(max_drawdown_pct=2.0, timezone="UTC")
    ok, dd = guard.update(100.0, 1_767_225_600)
    assert ok is True and dd == 0
    ok, dd = guard.update(97.9, 1_767_225_700)
    assert ok is False
    assert dd == pytest.approx(2.1)


def test_local_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scalper.local_config.load_env_file", lambda path=".env": None)
    for key in (
        "PRIMEXBT_MCP_URL", "SCALPER_SYMBOL", "PRIMEXBT_ACCOUNT_ID",
        "SCALPER_POLL_SECONDS", "SCALPER_MAX_DAILY_DRAWDOWN_PCT",
        "SCALPER_OAUTH_FILE", "SCALPER_JOURNAL_FILE",
    ):
        monkeypatch.delenv(key, raising=False)
    config = LocalConfig.from_env()
    assert config.mcp_url == "https://api.primexbt.com/v2/mcp"
    assert config.symbol == "XAU/USD"
    assert config.poll_seconds == 2.0


def test_poll_interval_cannot_be_too_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scalper.local_config.load_env_file", lambda path=".env": None)
    monkeypatch.setenv("SCALPER_POLL_SECONDS", "0.1")
    with pytest.raises(ValueError):
        LocalConfig.from_env()
