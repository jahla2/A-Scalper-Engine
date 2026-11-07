from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..broker import PrimeXBTBroker
from ..config import Settings
from ..engine import ScalperEngine
from ..local_config import LocalConfig
from ..mcp_client import PrimeXbtMcpToolCaller
from ..realtime.cache import CachedBroker
from ..realtime.events import EventBus
from ..realtime.storage import AnalysisStore
from ..realtime.supervisor import MarketSupervisor
from .context import AppContext
from .serializers import chart_payload


class SymbolRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=80)


class RuntimeSettingsRequest(BaseModel):
    quote_poll_seconds: float | None = Field(default=None, ge=0.5, le=60)
    bar_poll_seconds: float | None = Field(default=None, ge=0.5, le=60)
    account_poll_seconds: float | None = Field(default=None, ge=0.5, le=60)
    max_daily_drawdown_pct: float | None = Field(default=None, ge=0.1, le=20)


def _context(request: Request) -> AppContext:
    return request.app.state.context


def _websocket_context(websocket: WebSocket) -> AppContext:
    return websocket.scope["app"].state.context


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = LocalConfig.from_env()
    caller = PrimeXbtMcpToolCaller(config.mcp_url, config.oauth_file)
    await caller.__aenter__()
    try:
        raw_broker = PrimeXBTBroker(
            caller,
            account_id=config.account_id,
            allow_live_execution=False,
        )
        account = await raw_broker.account()
        if config.require_demo and not account.demo:
            raise RuntimeError(
                f"Web dashboard requires a Demo account; connected to {account.account_id}"
            )
        broker = CachedBroker(raw_broker)
        engine = ScalperEngine(broker, Settings(timezone=config.timezone))
        store = AnalysisStore(config.database_file)
        await store.initialize()
        events = EventBus()
        supervisor = MarketSupervisor(
            broker,
            engine,
            store,
            events,
            symbol=config.symbol,
            quote_poll_seconds=config.quote_poll_seconds,
            bar_poll_seconds=config.bar_poll_seconds,
            account_poll_seconds=config.account_poll_seconds,
            max_daily_drawdown_pct=config.max_daily_drawdown_pct,
        )
        context = AppContext(caller, broker, engine, store, events, supervisor)
        app.state.context = context
        app.state.config = config
        await supervisor.start()
        yield
    finally:
        context = getattr(app.state, "context", None)
        if context is not None:
            await context.supervisor.stop()
        await caller.__aexit__(None, None, None)


app = FastAPI(
    title="A+ Scalper Engine API",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[LocalConfig.from_env().ui_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health(request: Request) -> dict[str, Any]:
    return _context(request).supervisor.health()


@app.get("/api/status")
async def status(request: Request) -> dict[str, Any]:
    context = _context(request)
    account = await context.broker.account()
    return {
        "account": {
            "id": account.account_id,
            "demo": account.demo,
            "currency": account.currency,
            "position_mode": account.position_mode,
        },
        **context.supervisor.snapshot(),
    }


@app.get("/api/account")
async def account(request: Request) -> dict[str, Any]:
    context = _context(request)
    value = await context.broker.account()
    snapshot = dict(await context.broker.snapshot())
    return {
        "id": value.account_id,
        "demo": value.demo,
        "currency": value.currency,
        "position_mode": value.position_mode,
        "snapshot": snapshot,
    }


@app.get("/api/symbols/search")
async def search_symbols(
    request: Request,
    q: Annotated[str, Query(min_length=1, max_length=80)],
) -> dict[str, Any]:
    items = await _context(request).broker.search_symbols(q)
    return {"items": items}


@app.post("/api/market/select")
async def select_market(request: Request, body: SymbolRequest) -> dict[str, Any]:
    try:
        symbol = await _context(request).supervisor.select_symbol(body.symbol)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"symbol": symbol}


@app.get("/api/market/quote")
async def quote(request: Request, symbol: str | None = None) -> dict[str, Any]:
    context = _context(request)
    selected = symbol or context.supervisor.selected_symbol
    value = await context.broker.quote(selected)
    return {
        "symbol": value.symbol,
        "bid": value.bid,
        "ask": value.ask,
        "price": value.price,
        "spread": value.spread,
        "market_open": value.market_open,
    }


@app.get("/api/market/bars")
async def bars(
    request: Request,
    timeframe: Annotated[
        str,
        Query(pattern="^(1M|5M|15M|30M|1H|4H|1D)$"),
    ] = "5M",
    limit: Annotated[int, Query(ge=20, le=1000)] = 300,
    symbol: str | None = None,
) -> dict[str, Any]:
    context = _context(request)
    selected = symbol or context.supervisor.selected_symbol
    values = await context.broker.bars(selected, timeframe, limit)
    payload = chart_payload(values, request.app.state.config.timezone)
    return {"symbol": selected, "timeframe": timeframe, **payload}


@app.get("/api/analysis/latest")
async def latest_analysis(
    request: Request,
    symbol: str | None = None,
) -> dict[str, Any] | None:
    context = _context(request)
    selected = symbol or context.supervisor.selected_symbol
    cached = context.supervisor.latest_analysis.get(selected)
    return cached or await context.store.latest(selected)


@app.post("/api/analysis/scan")
async def scan(request: Request, body: SymbolRequest | None = None) -> dict[str, Any]:
    context = _context(request)
    symbol = body.symbol if body else context.supervisor.selected_symbol
    try:
        resolved = await context.broker.resolve_symbol(symbol)
        return await context.supervisor.manual_scan(resolved)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analysis/history")
async def history(
    request: Request,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    symbol: str | None = None,
    decision: str | None = None,
    direction: str | None = None,
) -> dict[str, Any]:
    items = await _context(request).store.history(
        symbol=symbol,
        decision=decision,
        direction=direction,
        min_score=min_score,
        limit=limit,
    )
    return {"items": items}


@app.get("/api/settings")
async def settings(request: Request) -> dict[str, Any]:
    config = request.app.state.config
    context = _context(request)
    return {
        "runtime": context.supervisor.runtime_settings(),
        "strategy": {
            "name": "A_PLUS_SCALPER_V1",
            "engine": "deterministic_rules",
            "llm_required": False,
            "score_threshold": 85,
            "timeframes": ["1M", "5M", "15M", "1H"],
        },
        "safety": {
            "require_demo": config.require_demo,
            "live_execution": False,
        },
    }


@app.patch("/api/settings/runtime")
async def update_runtime_settings(
    request: Request,
    body: RuntimeSettingsRequest,
) -> dict[str, Any]:
    values = body.model_dump(exclude_none=True)
    try:
        runtime = _context(request).supervisor.update_runtime(**values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"runtime": runtime}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    context = _websocket_context(websocket)
    queue = context.events.subscribe()
    try:
        await websocket.send_json(
            {"type": "system.snapshot", "data": context.supervisor.snapshot()}
        )
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        context.events.unsubscribe(queue)


def run() -> None:
    config = LocalConfig.from_env()
    uvicorn.run(
        "scalper.api.app:app",
        host=config.api_host,
        port=config.api_port,
        reload=False,
    )
