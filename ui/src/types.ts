export type Decision = "NO_TRADE" | "WATCH" | "TRADE_CANDIDATE";
export type Direction = "LONG" | "SHORT" | "NEUTRAL";
export type Timeframe = "1M" | "5M" | "15M" | "30M" | "1H" | "4H" | "1D";

export interface Quote {
  symbol: string;
  bid: number;
  ask: number;
  price: number;
  spread: number;
  market_open: boolean;
  updated_at?: string;
}

export interface MarketBias {
  direction: Direction;
  long_alignment: number;
  short_alignment: number;
  strength: number;
  components: Record<string, string>;
  reasons: string[];
}

export interface Analysis {
  strategy: string;
  symbol: string;
  timestamp: number;
  decision: Decision;
  direction: Direction;
  bias?: MarketBias;
  score: { total: number; threshold: number; parts: Record<string, number> };
  regime: {
    direction: Direction;
    close: number;
    ema50: number;
    ema200: number;
    structure: string;
    slope_ok: boolean;
  };
  setup: {
    valid: boolean;
    location_valid: boolean;
    level_aligned: boolean;
    vwap: number;
    atr: number;
    nearest_level: number | null;
    reason: string;
  };
  structure: {
    direction: Direction;
    bos: boolean;
    bos_level: number | null;
    bos_time: number | null;
    displacement: boolean;
    retest: boolean;
    atr: number;
    reason: string;
  };
  execution: { confirmed: boolean; micro_bos: boolean; structure: string };
  trade: {
    entry: number;
    stop_loss: number;
    take_profit: number;
    rr: number;
    risk_budget: number;
  } | null;
  reasons: string[];
  runtime?: {
    equity: number;
    daily_drawdown_pct: number;
    risk_guard_allowed: boolean;
    scan_source?: string;
    scan_cached?: boolean;
    scan_cooldown_remaining?: number;
  };
}

export interface ChartPayload {
  symbol: string;
  timeframe: Timeframe;
  bars: Array<{
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
  indicators: {
    ema50: Array<{ time: number; value: number }>;
    ema200: Array<{ time: number; value: number }>;
    vwap: Array<{ time: number; value: number }>;
    atr14: number | null;
  };
}

export interface AppStatus {
  account: { id: string; demo: boolean; currency: string; position_mode: string };
  health: {
    status: string;
    selected_symbol: string;
    last_scan_at: number | null;
    last_scan_source?: string | null;
    last_error: string | null;
    websocket_clients: number;
    mcp_requests: Record<string, number>;
  };
  quote: Quote | null;
  analysis: Analysis | null;
}

export interface SettingsPayload {
  runtime: {
    quote_poll_seconds: number;
    bar_poll_seconds: number;
    account_poll_seconds: number;
    max_daily_drawdown_pct: number;
  };
  strategy: {
    name: string;
    engine: string;
    llm_required: boolean;
    score_threshold: number;
    timeframes: string[];
  };
  safety: { require_demo: boolean; live_execution: boolean };
}

export interface SymbolSearchResult {
  symbol?: string;
  description?: string;
  category?: string;
  [key: string]: unknown;
}

export interface SocketEvent {
  type: string;
  data: unknown;
}
