import { useCallback, useEffect, useMemo, useState } from "react";
import { Moon, RefreshCw, Search, Sun, Wifi, WifiOff } from "lucide-react";
import { api } from "./api";
import { AnalysisLog } from "./components/AnalysisLog";
import { MarketChart } from "./components/MarketChart";
import { ScorePanel } from "./components/ScorePanel";
import { TimeframeGrid } from "./components/TimeframeGrid";
import { TradePlanCard } from "./components/TradePlanCard";
import { useRealtime } from "./hooks/useRealtime";
import type {
  Analysis,
  AppStatus,
  ChartPayload,
  Quote,
  SettingsPayload,
  SocketEvent,
  StrategyDefinition,
  SymbolSearchResult,
  Timeframe
} from "./types";

type Page = "dashboard" | "markets" | "strategies" | "analysis" | "settings";

const timeframes: Timeframe[] = ["1M", "5M", "15M", "1H"];

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [dark, setDark] = useState(() => localStorage.getItem("theme") !== "light");
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [symbol, setSymbol] = useState("XAU/USD");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [history, setHistory] = useState<Analysis[]>([]);
  const [chart, setChart] = useState<ChartPayload | null>(null);
  const [timeframe, setTimeframe] = useState<Timeframe>("5M");
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [strategies, setStrategies] = useState<StrategyDefinition[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyDefinition | null>(null);
  const [strategyBusy, setStrategyBusy] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<SymbolSearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanBusy, setScanBusy] = useState(false);
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadChart = useCallback(async (selected: string, tf: Timeframe) => {
    try {
      setChart(await api.bars(selected, tf));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  const loadHistory = useCallback(async (selected: string) => {
    try {
      const response = await api.history(selected, 100);
      setHistory(response.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    Promise.all([api.status(), api.settings(), api.strategies()])
      .then(([nextStatus, nextSettings, strategyCatalog]) => {
        const selected = nextStatus.health.selected_symbol;
        setStatus(nextStatus);
        setSettings(nextSettings);
        setStrategies(strategyCatalog.items);
        setSelectedStrategy(strategyCatalog.selected);
        setSymbol(selected);
        setQuote(nextStatus.quote);
        setAnalysis(nextStatus.analysis);
        return Promise.all([loadChart(selected, timeframe), loadHistory(selected)]);
      })
      .catch((reason) => {
        setError(reason instanceof Error ? reason.message : String(reason));
      })
      .finally(() => setLoading(false));
  }, []);

  const onSocketEvent = useCallback((event: SocketEvent) => {
    if (event.type === "quote.updated") {
      const next = event.data as Quote;
      if (next.symbol === symbol) setQuote(next);
    }
    if (event.type === "bar.updated") {
      const payload = event.data as {
        symbol: string;
        timeframe: string;
        bar: ChartPayload["bars"][number];
      };
      if (payload.symbol === symbol) {
        setChart((current) => updateChartBar(current, payload.bar, timeframe));
      }
    }
    if (event.type === "analysis.updated") {
      const next = event.data as Analysis;
      if (next.symbol === symbol) {
        setAnalysis(next);
        setHistory((items) => prependAnalysis(items, next));
        if (next.runtime?.scan_source === "candle_close") {
          void loadChart(symbol, timeframe);
        }
      }
    }
    if (event.type === "strategy.changed") {
      const payload = event.data as { strategy: StrategyDefinition };
      setSelectedStrategy(payload.strategy);
    }
    if (event.type === "settings.updated") {
      const runtime = event.data as SettingsPayload["runtime"];
      setSettings((current) => current ? { ...current, runtime } : current);
    }
    if (event.type === "system.error") {
      const payload = event.data as { message?: string };
      if (payload.message) setError(payload.message);
    }
  }, [loadChart, symbol, timeframe]);

  const socketConnected = useRealtime(onSocketEvent);

  useEffect(() => {
    if (!loading) void loadChart(symbol, timeframe);
  }, [symbol, timeframe, loading, loadChart]);

  const runScan = async () => {
    setScanBusy(true);
    setError(null);
    try {
      const next = await api.scan(symbol);
      setAnalysis(next);
      if (!next.runtime?.scan_cached) {
        setHistory((items) => prependAnalysis(items, next));
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setScanBusy(false);
    }
  };

  const searchMarkets = async () => {
    if (!search.trim()) return;
    try {
      const response = await api.searchSymbols(search.trim());
      setResults(response.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  const saveRuntimeSettings = async () => {
    if (!settings) return;
    setSettingsBusy(true);
    setError(null);
    try {
      const response = await api.updateRuntime(settings.runtime);
      setSettings({ ...settings, runtime: response.runtime });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSettingsBusy(false);
    }
  };

  const selectStrategyMode = async (strategyId: string) => {
    setStrategyBusy(strategyId);
    setError(null);
    try {
      const response = await api.selectStrategy(strategyId);
      setSelectedStrategy(response.selected);
      setAnalysis(response.analysis);
      setHistory((items) => prependAnalysis(items, response.analysis));
      const nextSettings = await api.settings();
      setSettings(nextSettings);
      setPage("dashboard");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setStrategyBusy(null);
    }
  };

  const selectMarket = async (nextSymbol: string) => {
    try {
      const response = await api.selectSymbol(nextSymbol);
      setSymbol(response.symbol);
      setResults([]);
      setSearch("");
      await Promise.all([
        loadChart(response.symbol, timeframe),
        loadHistory(response.symbol)
      ]);
      setPage("dashboard");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  const marketState = useMemo(() => {
    if (!quote) return "Waiting";
    return quote.market_open ? "Market open" : "Market closed";
  }, [quote]);

  if (loading) {
    return <div className="boot">Starting A+ Scalper dashboard...</div>;
  }

  return (
    <div className="shell">
      <header className="topbar">
        <button className="brand" onClick={() => setPage("dashboard")}>
          <span className="brand-mark">A+</span>
          <span><strong>Scalper</strong><small>Deterministic engine</small></span>
        </button>

        <nav>
          {(["dashboard", "markets", "strategies", "analysis", "settings"] as Page[]).map((item) => (
            <button
              className={page === item ? "active" : ""}
              key={item}
              onClick={() => setPage(item)}
            >
              {item}
            </button>
          ))}
        </nav>

        <div className="top-actions">
          <span className={"connection " + (socketConnected ? "online" : "offline")}>
            {socketConnected ? <Wifi size={15} /> : <WifiOff size={15} />}
            {socketConnected ? "Connected" : "Reconnecting"}
          </span>
          <span className="demo-badge">
            {(status?.account.demo ? "DEMO" : "LIVE") + " · " + (status?.account.id ?? "—")}
          </span>
          <button className="icon-button" onClick={() => setDark((value) => !value)}>
            {dark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </header>

      <main>
        {error && (
          <div className="error-banner">
            <span>{error}</span>
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        {page === "dashboard" && (
          <>
            <section className="market-header">
              <div>
                <p className="eyebrow">Active market</p>
                <div className="symbol-title">
                  <h1>{symbol}</h1>
                  <span className={quote?.market_open ? "market-open" : "market-closed"}>
                    {marketState}
                  </span>
                </div>
                <div className="active-strategy-line">
                  <span>Strategy</span>
                  <button onClick={() => setPage("strategies")}>
                    {selectedStrategy?.name ?? analysis?.strategy ?? "A+ Structure MTF"}
                  </button>
                  <small>Full scan: 1H · 15M · 5M · 1M</small>
                </div>
              </div>
              <div className="market-numbers">
                <Metric label="Price" value={quote?.price} />
                <Metric label="Bid" value={quote?.bid} />
                <Metric label="Ask" value={quote?.ask} />
                <Metric label="Spread" value={quote?.spread} />
                <div className="scan-control">
                  <button className="primary-button" disabled={scanBusy} onClick={runScan}>
                    <RefreshCw size={16} className={scanBusy ? "spin" : ""} />
                    {scanBusy ? "Scanning" : "Run scan"}
                  </button>
                  <small>{scanStatus(analysis)}</small>
                </div>
              </div>
            </section>

            <div className="dashboard-grid">
              <section className="panel chart-panel">
                <div className="panel-heading chart-heading">
                  <div><p className="eyebrow">Market structure</p><h2>Realtime chart</h2></div>
                  <div className="timeframe-tabs">
                    {timeframes.map((item) => (
                      <button
                        className={timeframe === item ? "active" : ""}
                        key={item}
                        onClick={() => setTimeframe(item)}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                </div>
                <MarketChart data={chart} analysis={analysis} dark={dark} />
                <div className="chart-legend">
                  <span><i className="ema50" />EMA50</span>
                  <span><i className="ema200" />EMA200</span>
                  <span><i className="vwap" />VWAP</span>
                  <span>ATR14 {chart?.indicators.atr14?.toFixed(2) ?? "—"}</span>
                </div>
              </section>
              <ScorePanel analysis={analysis} />
            </div>

            <TimeframeGrid analysis={analysis} />
            <TradePlanCard analysis={analysis} />

            <div className="lower-grid">
              <AnalysisLog items={history} />
              <section className="panel explanation-panel">
                <div className="panel-heading">
                  <div><p className="eyebrow">Decision</p><h2>Why the engine decided this</h2></div>
                </div>
                <div className="reason-list">
                  {(analysis?.reasons ?? ["Waiting for the first analysis."]).map((reason) => (
                    <div key={reason}>{reason}</div>
                  ))}
                </div>
                <dl className="detail-list">
                  <Detail name="Strategy" value={analysis?.strategy ?? "A_PLUS_SCALPER_V1"} />
                  <Detail
                    name="Directional bias"
                    value={analysis?.bias ? analysis.bias.direction + " · " + analysis.bias.strength + "/100" : "—"}
                  />
                  <Detail
                    name="Long / Short alignment"
                    value={analysis?.bias ? analysis.bias.long_alignment + " / " + analysis.bias.short_alignment : "—"}
                  />
                  <Detail name="1H structure" value={analysis?.regime.structure ?? "—"} />
                  <Detail name="5M BOS" value={analysis?.structure.bos ? "Confirmed" : "No"} />
                  <Detail
                    name="Displacement"
                    value={analysis?.structure.displacement ? "Confirmed" : "No"}
                  />
                  <Detail name="Retest" value={analysis?.structure.retest ? "Confirmed" : "No"} />
                  <Detail
                    name="Risk guard"
                    value={analysis?.runtime?.risk_guard_allowed === false ? "Blocked" : "Ready"}
                  />
                </dl>
              </section>
            </div>
          </>
        )}

        {page === "strategies" && (
          <section className="page-section">
            <PageHeading
              eyebrow="Deterministic strategy catalog"
              title="Strategies"
              copy="Choose one analysis model before Run Scan. Every model evaluates 1H, 15M, 5M and 1M before the final decision."
            />

            <div className="strategy-research-note">
              <strong>Research note</strong>
              <span>
                These are rule-based technical-analysis frameworks, not guaranteed profitable systems.
                Each strategy needs its own backtest and demo forward-test.
              </span>
            </div>

            <div className="strategy-card-grid">
              {strategies.map((strategy) => {
                const active = selectedStrategy?.strategy_id === strategy.strategy_id;
                const busy = strategyBusy === strategy.strategy_id;
                return (
                  <article className={"panel strategy-card " + (active ? "strategy-card-active" : "")}
                    key={strategy.strategy_id}>
                    <div className="strategy-card-header">
                      <div>
                        <p className="eyebrow">{strategy.style}</p>
                        <h2>{strategy.name}</h2>
                      </div>
                      <span className={active ? "strategy-active-badge" : "strategy-origin-badge"}>
                        {active ? "ACTIVE" : strategy.origin}
                      </span>
                    </div>
                    <p className="strategy-description">{strategy.description}</p>
                    <div className="strategy-flow">
                      {strategy.timeframes.map((tf, index) => (
                        <span key={tf}>
                          <b>{tf}</b>
                          {index < strategy.timeframes.length - 1 && <i>→</i>}
                        </span>
                      ))}
                    </div>
                    <div className="strategy-evidence">
                      <strong>Basis</strong>
                      <span>{strategy.evidence_note}</span>
                    </div>
                    <button
                      className={active ? "secondary-button strategy-select" : "primary-button strategy-select"}
                      disabled={active || strategyBusy !== null}
                      onClick={() => void selectStrategyMode(strategy.strategy_id)}
                    >
                      {active ? "Selected" : busy ? "Switching" : "Use strategy"}
                    </button>
                  </article>
                );
              })}
            </div>
          </section>
        )}

        {page === "markets" && (
          <section className="page-section">
            <PageHeading
              eyebrow="Instrument discovery"
              title="Markets"
              copy="Search PrimeXBT symbols and switch the monitored instrument safely."
            />
            <section className="panel">
              <div className="search-row">
                <Search size={18} />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  onKeyDown={(event) => event.key === "Enter" && void searchMarkets()}
                  placeholder="Search gold, BTC, ETH..."
                />
                <button className="primary-button" onClick={searchMarkets}>Search</button>
              </div>
              <div className="market-results">
                {results.map((item) => {
                  const resultSymbol = String(item.symbol ?? "");
                  return (
                    <button
                      className="market-result"
                      key={resultSymbol}
                      onClick={() => resultSymbol && void selectMarket(resultSymbol)}
                    >
                      <strong>{resultSymbol || "Unknown"}</strong>
                      <span>{String(item.description ?? item.category ?? "")}</span>
                    </button>
                  );
                })}
                {results.length === 0 && <div className="empty">Search for a PrimeXBT instrument.</div>}
              </div>
            </section>
          </section>
        )}

        {page === "analysis" && (
          <section className="page-section">
            <div className="page-heading">
              <div>
                <p className="eyebrow">Stored locally in SQLite</p>
                <h1>Analysis history</h1>
                <p>Review every engine decision for the currently selected symbol.</p>
              </div>
              <button className="secondary-button" onClick={() => void loadHistory(symbol)}>
                <RefreshCw size={16} />Refresh
              </button>
            </div>
            <section className="panel table-panel">
              <table>
                <thead>
                  <tr>
                    <th>Time</th><th>Symbol</th><th>Bias</th><th>Strict direction</th>
                    <th>Decision</th><th>Score</th><th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((item, index) => (
                    <tr key={item.timestamp + "-" + index}>
                      <td>{new Date(item.timestamp * 1000).toLocaleString()}</td>
                      <td>{item.symbol}</td>
                      <td>
                        <span className={"direction direction-" + (item.bias?.direction ?? "NEUTRAL")}>
                          {item.bias?.direction ?? "LEGACY"} {item.bias?.strength ?? "—"}
                        </span>
                      </td>
                      <td>{item.direction}</td>
                      <td>{item.decision.replaceAll("_", " ")}</td>
                      <td>{item.score.total}</td>
                      <td>{item.reasons?.[0] ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </section>
        )}

        {page === "settings" && (
          <section className="page-section">
            <PageHeading
              eyebrow="Safe runtime configuration"
              title="Settings"
              copy="Backend cadence and trading safeguards currently active."
            />
            <div className="settings-grid">
              <section className="panel settings-card">
                <div className="settings-title-row">
                  <h2>Runtime</h2>
                  <span>Session settings</span>
                </div>
                <div className="settings-form">
                  <RuntimeField
                    label="Quote polling"
                    value={settings?.runtime.quote_poll_seconds ?? 2}
                    suffix="seconds"
                    onChange={(value) => setSettings((current) => current ? {
                      ...current,
                      runtime: { ...current.runtime, quote_poll_seconds: value }
                    } : current)}
                  />
                  <RuntimeField
                    label="1M candle polling"
                    value={settings?.runtime.bar_poll_seconds ?? 5}
                    suffix="seconds"
                    onChange={(value) => setSettings((current) => current ? {
                      ...current,
                      runtime: { ...current.runtime, bar_poll_seconds: value }
                    } : current)}
                  />
                  <RuntimeField
                    label="Account polling"
                    value={settings?.runtime.account_poll_seconds ?? 10}
                    suffix="seconds"
                    onChange={(value) => setSettings((current) => current ? {
                      ...current,
                      runtime: { ...current.runtime, account_poll_seconds: value }
                    } : current)}
                  />
                  <RuntimeField
                    label="Daily drawdown guard"
                    value={settings?.runtime.max_daily_drawdown_pct ?? 2}
                    suffix="%"
                    onChange={(value) => setSettings((current) => current ? {
                      ...current,
                      runtime: { ...current.runtime, max_daily_drawdown_pct: value }
                    } : current)}
                  />
                  <button
                    className="primary-button settings-save"
                    disabled={settingsBusy}
                    onClick={saveRuntimeSettings}
                  >
                    {settingsBusy ? "Saving" : "Apply runtime settings"}
                  </button>
                </div>
              </section>
              <SettingsCard title="Strategy">
                <Detail name="Model" value={settings?.strategy.name ?? "A+ Structure MTF"} />
                <Detail name="Strategy ID" value={settings?.strategy.strategy_id ?? "a_plus_structure"} />
                <Detail name="Origin" value={settings?.strategy.origin ?? "Systematic multi-timeframe"} />
                <Detail name="Engine" value={settings?.strategy.engine ?? "Deterministic rules"} />
                <Detail name="LLM required" value={settings?.strategy.llm_required ? "Yes" : "No"} />
                <Detail name="A+ threshold" value={String(settings?.strategy.score_threshold ?? 85)} />
                <Detail name="Timeframes" value={settings?.strategy.timeframes.join(" · ") ?? "—"} />
                <Detail name="Execution" value="Analysis only" />
              </SettingsCard>
              <SettingsCard title="Safety">
                <Detail name="Demo required" value={settings?.safety.require_demo ? "Yes" : "No"} />
                <Detail name="Live execution" value="Disabled" />
                <Detail name="Browser MCP access" value="Never" />
              </SettingsCard>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

function Metric(props: { label: string; value?: number }) {
  return (
    <div><small>{props.label}</small><strong>{props.value?.toFixed(2) ?? "—"}</strong></div>
  );
}

function Detail(props: { name: string; value: string }) {
  return <div><dt>{props.name}</dt><dd>{props.value}</dd></div>;
}

function PageHeading(props: { eyebrow: string; title: string; copy: string }) {
  return (
    <div className="page-heading">
      <div><p className="eyebrow">{props.eyebrow}</p><h1>{props.title}</h1><p>{props.copy}</p></div>
    </div>
  );
}

function SettingsCard(props: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel settings-card">
      <h2>{props.title}</h2>
      <dl className="detail-list">{props.children}</dl>
    </section>
  );
}

function RuntimeField(props: {
  label: string;
  value: number;
  suffix: string;
  onChange: (value: number) => void;
}) {
  return (
    <label className="runtime-field">
      <span>{props.label}</span>
      <div>
        <input
          type="number"
          min="0.5"
          step="0.5"
          value={props.value}
          onChange={(event) => props.onChange(Number(event.target.value))}
        />
        <small>{props.suffix}</small>
      </div>
    </label>
  );
}

function updateChartBar(
  current: ChartPayload | null,
  incoming: ChartPayload["bars"][number],
  timeframe: Timeframe
): ChartPayload | null {
  if (!current) return current;
  const seconds: Record<Timeframe, number> = {
    "1M": 60,
    "5M": 300,
    "15M": 900,
    "30M": 1800,
    "1H": 3600,
    "4H": 14400,
    "1D": 86400
  };
  const interval = seconds[timeframe];
  const bucket = Math.floor(incoming.time / interval) * interval;
  const bars = [...current.bars];
  const last = bars[bars.length - 1];

  if (!last || bucket > last.time) {
    bars.push({ ...incoming, time: bucket });
  } else if (bucket === last.time) {
    bars[bars.length - 1] = timeframe === "1M"
      ? incoming
      : {
          ...last,
          high: Math.max(last.high, incoming.high),
          low: Math.min(last.low, incoming.low),
          close: incoming.close
        };
  }
  return { ...current, bars };
}


function scanStatus(analysis: Analysis | null) {
  if (!analysis) return "No scan yet";
  const time = new Date(analysis.timestamp * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
  if (analysis.runtime?.scan_cached) {
    const remaining = analysis.runtime.scan_cooldown_remaining ?? 0;
    return "Cached result · retry in " + remaining.toFixed(1) + "s";
  }
  const source = (analysis.runtime?.scan_source ?? "scan").replaceAll("_", " ");
  return "Last " + source + " · " + time;
}


function prependAnalysis(items: Analysis[], next: Analysis) {
  const duplicate = items.some(
    (item) => item.symbol === next.symbol && item.timestamp === next.timestamp
  );
  if (duplicate) return items;
  return [next, ...items].slice(0, 100);
}
