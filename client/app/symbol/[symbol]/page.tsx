"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import CandlestickChart from "@/components/CandlestickChart";
import TradePanel from "@/components/TradePanel";
import { Candle, Quote } from "@/types/symbol";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = API_URL.replace(/^http/, "ws");

export default function SymbolPage() {
  const params = useParams();
  const symbol = typeof params.symbol === "string" ? params.symbol : "";

  const [candles, setCandles] = useState<Candle[]>([]);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [liveLtp, setLiveLtp] = useState<number | null>(null);
  const [prevLtp, setPrevLtp] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const candleRefreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const quotePollTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch candles (2 days for zoomed-in view)
  const fetchCandles = useCallback(() => {
    if (!symbol) return;
    fetch(`${API_URL}/api/candles/${encodeURIComponent(symbol)}?interval=5minute&days=2`)
      .then((r) => (r.ok ? r.json() : r.json().then((e) => Promise.reject(e))))
      .then((data) => {
        setCandles(data.candles || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err?.detail || err?.message || "Failed to load candles");
        setLoading(false);
      });
  }, [symbol]);

  // Fetch quote
  const fetchQuote = useCallback(() => {
    if (!symbol) return;
    fetch(`${API_URL}/api/quote/${encodeURIComponent(symbol)}`)
      .then((r) => (r.ok ? r.json() : r.json().then((e) => Promise.reject(e))))
      .then((data) => setQuote(data))
      .catch(() => {});
  }, [symbol]);

  // WebSocket for live LTP
  const connectWs = useCallback(() => {
    if (!symbol) return;
    const ws = new WebSocket(`${WS_URL}/ws/ltp/${encodeURIComponent(symbol)}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.ltp) {
          setPrevLtp((prev) => prev ?? data.ltp);
          setLiveLtp((prev) => {
            setPrevLtp(prev);
            return data.ltp;
          });
        }
      } catch {}
    };

    ws.onclose = () => {
      if (!quotePollTimer.current) {
        quotePollTimer.current = setInterval(fetchQuote, 5000);
      }
      reconnectTimer.current = setTimeout(connectWs, 10000);
    };

    ws.onopen = () => {
      if (quotePollTimer.current) {
        clearInterval(quotePollTimer.current);
        quotePollTimer.current = null;
      }
    };

    ws.onerror = () => ws.close();
  }, [symbol, fetchQuote]);

  // Initial load
  useEffect(() => {
    fetchCandles();
    fetchQuote();
    connectWs();

    candleRefreshTimer.current = setInterval(fetchCandles, 5 * 60 * 1000);

    return () => {
      wsRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (candleRefreshTimer.current) clearInterval(candleRefreshTimer.current);
      if (quotePollTimer.current) clearInterval(quotePollTimer.current);
    };
  }, [fetchCandles, fetchQuote, connectWs]);

  const currentLtp = liveLtp ?? quote?.ltp ?? 0;
  const change = quote
    ? currentLtp - (quote.prev_close || quote.close || 0)
    : 0;
  const changePct = quote?.prev_close
    ? (change / quote.prev_close) * 100
    : 0;
  const isPositive = change >= 0;
  const ltpChanged = prevLtp !== null && liveLtp !== null && prevLtp !== liveLtp;

  return (
    <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600" />
          <span className="ml-3 text-gray-500">Loading chart data...</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-800 dark:bg-red-950">
          <h2 className="text-lg font-semibold text-red-800 dark:text-red-200">Error</h2>
          <p className="mt-2 text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <>
          {/* Compact header */}
          <div className="mb-3 flex items-baseline gap-4">
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
              {symbol}
            </h1>
            <span
              className={`text-2xl font-semibold ${
                ltpChanged ? "animate-pulse" : ""
              } ${
                isPositive
                  ? "text-green-600 dark:text-green-400"
                  : "text-red-600 dark:text-red-400"
              }`}
            >
              {"\u20B9"}
              {currentLtp.toLocaleString("en-IN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
            <span
              className={`text-sm font-medium ${
                isPositive
                  ? "text-green-600 dark:text-green-400"
                  : "text-red-600 dark:text-red-400"
              }`}
            >
              {isPositive ? "+" : ""}
              {change.toFixed(2)} ({isPositive ? "+" : ""}
              {changePct.toFixed(2)}%)
            </span>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <CandlestickChart candles={candles} liveLtp={liveLtp} />
            </div>
            <div>
              <TradePanel symbol={symbol} ltp={currentLtp} candles={candles} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
