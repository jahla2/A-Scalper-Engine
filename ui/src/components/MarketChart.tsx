import { useEffect, useRef } from "react";
import {
  ColorType,
  CrosshairMode,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp
} from "lightweight-charts";
import type { ChartPayload } from "../types";

export function MarketChart(props: { data: ChartPayload | null; dark: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const candles = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ema50 = useRef<ISeriesApi<"Line"> | null>(null);
  const ema200 = useRef<ISeriesApi<"Line"> | null>(null);
  const vwap = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    if (!host.current) return;
    const value = createChart(host.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: props.dark ? "#98a2b3" : "#667085"
      },
      grid: {
        vertLines: { color: props.dark ? "#1d2634" : "#edf0f4" },
        horzLines: { color: props.dark ? "#1d2634" : "#edf0f4" }
      },
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: { timeVisible: true, secondsVisible: false }
    });
    chart.current = value;
    candles.current = value.addCandlestickSeries({
      upColor: "#12b76a",
      downColor: "#f04438",
      borderVisible: false,
      wickUpColor: "#12b76a",
      wickDownColor: "#f04438"
    });
    ema50.current = value.addLineSeries({
      color: "#6172f3",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false
    });
    ema200.current = value.addLineSeries({
      color: "#f79009",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false
    });
    vwap.current = value.addLineSeries({
      color: "#9e77ed",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false
    });
    return () => {
      value.remove();
      chart.current = null;
    };
  }, [props.dark]);

  useEffect(() => {
    if (!props.data || !candles.current) return;
    candles.current.setData(
      props.data.bars.map((bar) => ({
        time: bar.time as UTCTimestamp,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close
      }))
    );
    ema50.current?.setData(
      props.data.indicators.ema50.map((point) => ({
        time: point.time as UTCTimestamp,
        value: point.value
      }))
    );
    ema200.current?.setData(
      props.data.indicators.ema200.map((point) => ({
        time: point.time as UTCTimestamp,
        value: point.value
      }))
    );
    vwap.current?.setData(
      props.data.indicators.vwap.map((point) => ({
        time: point.time as UTCTimestamp,
        value: point.value
      }))
    );
    chart.current?.timeScale().fitContent();
  }, [props.data]);

  return <div className="chart-host" ref={host} />;
}
