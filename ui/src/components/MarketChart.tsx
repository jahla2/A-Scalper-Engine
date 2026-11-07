import { useEffect, useRef } from "react";
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type UTCTimestamp
} from "lightweight-charts";
import type { Analysis, ChartPayload } from "../types";

export function MarketChart(props: {
  data: ChartPayload | null;
  analysis: Analysis | null;
  dark: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const candles = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ema50 = useRef<ISeriesApi<"Line"> | null>(null);
  const ema200 = useRef<ISeriesApi<"Line"> | null>(null);
  const vwap = useRef<ISeriesApi<"Line"> | null>(null);
  const tradeLines = useRef<IPriceLine[]>([]);

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
      tradeLines.current = [];
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

  useEffect(() => {
    const series = candles.current;
    if (!series) return;

    for (const line of tradeLines.current) {
      series.removePriceLine(line);
    }
    tradeLines.current = [];

    const plan = props.analysis?.trade;
    if (!plan) return;

    const specs = [
      { price: plan.entry, title: "ENTRY", color: "#6172f3", width: 2 as const },
      { price: plan.stop_loss, title: "SL", color: "#f04438", width: 2 as const },
      { price: plan.tp1, title: "TP1", color: "#47cd89", width: 1 as const },
      { price: plan.tp2, title: "TP2", color: "#17b26a", width: 1 as const },
      { price: plan.tp3, title: "TP3", color: "#079455", width: 2 as const }
    ];

    tradeLines.current = specs.map((spec) =>
      series.createPriceLine({
        price: spec.price,
        color: spec.color,
        lineWidth: spec.width,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: spec.title
      })
    );
  }, [props.analysis?.trade]);

  return <div className="chart-host" ref={host} />;
}
