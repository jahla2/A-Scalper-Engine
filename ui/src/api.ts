import type {
  Analysis,
  AppStatus,
  ChartPayload,
  SettingsPayload,
  SymbolSearchResult,
  Timeframe
} from "./types";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || "Request failed: " + response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  status: () => request<AppStatus>("/api/status"),
  settings: () => request<SettingsPayload>("/api/settings"),
  updateRuntime: (runtime: SettingsPayload["runtime"]) =>
    request<{ runtime: SettingsPayload["runtime"] }>("/api/settings/runtime", {
      method: "PATCH",
      body: JSON.stringify(runtime)
    }),
  bars: (symbol: string, timeframe: Timeframe, limit = 300) =>
    request<ChartPayload>(
      "/api/market/bars?symbol=" + encodeURIComponent(symbol) +
      "&timeframe=" + timeframe + "&limit=" + limit
    ),
  scan: (symbol: string) =>
    request<Analysis>("/api/analysis/scan", {
      method: "POST",
      body: JSON.stringify({ symbol })
    }),
  history: (symbol: string, limit = 100) =>
    request<{ items: Analysis[] }>(
      "/api/analysis/history?symbol=" + encodeURIComponent(symbol) + "&limit=" + limit
    ),
  searchSymbols: (query: string) =>
    request<{ items: SymbolSearchResult[] }>(
      "/api/symbols/search?q=" + encodeURIComponent(query)
    ),
  selectSymbol: (symbol: string) =>
    request<{ symbol: string }>("/api/market/select", {
      method: "POST",
      body: JSON.stringify({ symbol })
    })
};
