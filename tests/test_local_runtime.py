import pytest

from scalper.broker import Account
from scalper.local_config import LocalConfig, env_bool
from scalper.mcp_client import parse_authorization_result, raw_tool_name
from scalper.runner import require_demo_account
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
        "PRIMEXBT_MCP_URL",
        "SCALPER_SYMBOL",
        "PRIMEXBT_ACCOUNT_ID",
        "SCALPER_REQUIRE_DEMO",
        "SCALPER_POLL_SECONDS",
        "SCALPER_MAX_DAILY_DRAWDOWN_PCT",
        "SCALPER_OAUTH_FILE",
        "SCALPER_JOURNAL_FILE",
    ):
        monkeypatch.delenv(key, raising=False)
    config = LocalConfig.from_env()
    assert config.mcp_url == "https://api.primexbt.com/v2/mcp"
    assert config.symbol == "XAU/USD"
    assert config.require_demo is True
    assert config.poll_seconds == 2.0


def test_poll_interval_cannot_be_too_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scalper.local_config.load_env_file", lambda path=".env": None)
    monkeypatch.setenv("SCALPER_POLL_SECONDS", "0.1")
    with pytest.raises(ValueError):
        LocalConfig.from_env()


def test_env_bool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_BOOL", "yes")
    assert env_bool("TEST_BOOL", False) is True
    monkeypatch.setenv("TEST_BOOL", "off")
    assert env_bool("TEST_BOOL", True) is False


def test_demo_gate_blocks_live_account() -> None:
    live = Account("L1", False, "USD", 100.0, 90.0, "HEDGE")
    with pytest.raises(RuntimeError, match="Demo account required"):
        require_demo_account(live, True)


def test_demo_gate_allows_demo_account() -> None:
    demo = Account("D1", True, "USD", 10000.0, 10000.0, "HEDGE")
    require_demo_account(demo, True)


def test_oauth_redirect_parser() -> None:
    result = parse_authorization_result(
        "http://localhost:3030/callback?code=abc123&state=state456"
    )
    assert result.code == "abc123"
    assert result.state == "state456"


def test_oauth_redirect_parser_requires_code_and_state() -> None:
    with pytest.raises(RuntimeError, match="missing code/state"):
        parse_authorization_result("http://localhost:3030/callback")
