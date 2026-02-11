"use client";

import { useRef, useEffect } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  HistogramData,
  Time,
} from "lightweight-charts";
import { Candle } from "@/types/symbol";

interface Props {
  candles: Candle[];
  liveLtp: number | null;
}

export default function CandlestickChart({ candles, liveLtp }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  // Create chart on mount
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#9ca3af",
      },
      grid: {
        vertLines: { color: "rgba(156, 163, 175, 0.1)" },
        horzLines: { color: "rgba(156, 163, 175, 0.1)" },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: "rgba(156, 163, 175, 0.2)",
      },
      timeScale: {
        borderColor: "rgba(156, 163, 175, 0.2)",
        timeVisible: true,
        secondsVisible: false,
      },
      width: containerRef.current.clientWidth,
      height: 550,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      borderUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      wickUpColor: "#22c55e",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, []);

  // Update data when candles change
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || candles.length === 0) return;

    const validCandles = candles.filter(
      (c) => c.open > 0 && c.high > 0 && c.low > 0 && c.close > 0
    );

    const candleData: CandlestickData<Time>[] = validCandles.map((c) => ({
      time: c.time as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    const volumeData: HistogramData<Time>[] = validCandles.map((c) => ({
      time: c.time as Time,
      value: c.volume,
      color: c.close >= c.open ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)",
    }));

    candleSeriesRef.current.setData(candleData);
    volumeSeriesRef.current.setData(volumeData);
    chartRef.current?.timeScale().fitContent();
    if (candleData.length > 50) {
      chartRef.current?.timeScale().setVisibleLogicalRange({
        from: candleData.length - 50,
        to: candleData.length - 1,
      });
    }
  }, [candles]);

  // Live LTP: update the last candle
  useEffect(() => {
    if (!candleSeriesRef.current || !liveLtp || candles.length === 0) return;

    const last = candles[candles.length - 1];
    candleSeriesRef.current.update({
      time: last.time as Time,
      open: last.open,
      high: Math.max(last.high, liveLtp),
      low: Math.min(last.low, liveLtp),
      close: liveLtp,
    });
  }, [liveLtp, candles]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-xl border border-gray-200 bg-white p-2 shadow-sm dark:border-gray-800 dark:bg-gray-900"
    />
  );
}
