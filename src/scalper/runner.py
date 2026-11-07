from __future__ import annotations

import argparse
import asyncio
import json

from .broker import PrimeXBTBroker
from .engine import ScalperEngine
from .journal import JsonlJournal
from .local_config import LocalConfig
from .mcp_client import PrimeXbtMcpToolCaller
from .runtime import RealtimeRunner


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aplus", description="A+ Scalper local PrimeXBT MCP scanner")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("connect", help="OAuth-connect and verify PrimeXBT account/tools")
    sub.add_parser("scan", help="Run one live multi-timeframe strategy scan")
    sub.add_parser("watch", help="Watch newly closed 1M candles continuously")
    return parser


async def _run(command: str) -> None:
    cfg = LocalConfig.from_env()
    async with PrimeXbtMcpToolCaller(cfg.mcp_url, cfg.oauth_file) as caller:
        broker = PrimeXBTBroker(caller, account_id=cfg.account_id, allow_live_execution=False)
        if command == "connect":
            account = await broker.account()
            symbol = await broker.resolve_symbol(cfg.symbol)
            info = await broker.symbol_info(symbol)
            quote = await broker.quote(symbol)
            print(json.dumps({
                "account": {
                    "id": account.account_id,
                    "demo": account.demo,
                    "currency": account.currency,
                    "position_mode": account.position_mode,
                },
                "symbol": info.symbol,
                "market_open": quote.market_open,
                "bid": quote.bid,
                "ask": quote.ask,
                "available_tools": len(caller.tool_names),
            }, indent=2))
            return
        engine = ScalperEngine(broker)
        if command == "scan":
            signal = await engine.scan(cfg.symbol)
            print(json.dumps(signal.to_dict(), indent=2))
            return
        runner = RealtimeRunner(
            broker,
            engine,
            cfg.symbol,
            poll_seconds=cfg.poll_seconds,
            max_daily_drawdown_pct=cfg.max_daily_drawdown_pct,
            journal=JsonlJournal(cfg.journal_file),
        )
        await runner.run()


def cli() -> None:
    args = _parser().parse_args()
    try:
        asyncio.run(_run(args.command))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    cli()
