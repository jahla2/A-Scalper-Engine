from __future__ import annotations

from dataclasses import dataclass

from ..engine import ScalperEngine
from ..mcp_client import PrimeXbtMcpToolCaller
from ..realtime.cache import CachedBroker
from ..realtime.events import EventBus
from ..realtime.storage import AnalysisStore
from ..realtime.supervisor import MarketSupervisor


@dataclass(slots=True)
class AppContext:
    caller: PrimeXbtMcpToolCaller
    broker: CachedBroker
    engine: ScalperEngine
    store: AnalysisStore
    events: EventBus
    supervisor: MarketSupervisor
