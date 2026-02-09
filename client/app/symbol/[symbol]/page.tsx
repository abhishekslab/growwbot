"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import QuoteHeader from "@/components/QuoteHeader";
import CandlestickChart from "@/components/CandlestickChart";
import OrderPanel from "@/components/OrderPanel";
import OrderConfirmDialog from "@/components/OrderConfirmDialog";
import { Candle, Quote, OrderPayload, OrderResult } from "@/types/symbol";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = API_URL.replace(/^http/, "ws");

export default function SymbolPage() {
  const params = useParams();
  const symbol = typeof params.symbol === "string" ? params.symbol : "";

  const [candles, setCandles] = useState<Candle[]>([]);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [liveLtp, setLiveLtp] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Order flow state
  const [pendingOrder, setPendingOrder] = useState<OrderPayload | null>(null);
  const [orderLoading, setOrderLoading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const candleRefreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const quotePollTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch candles
  const fetchCandles = useCallback(() => {
    if (!symbol) return;
    fetch(`${API_URL}/api/candles/${encodeURIComponent(symbol)}?interval=5minute&days=5`)
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
        if (data.ltp) setLiveLtp(data.ltp);
      } catch {}
    };

    ws.onclose = () => {
      // Fall back to polling, try reconnect after 10s
      if (!quotePollTimer.current) {
        quotePollTimer.current = setInterval(fetchQuote, 5000);
      }
      reconnectTimer.current = setTimeout(connectWs, 10000);
    };

    ws.onopen = () => {
      // Stop polling fallback when WS connects
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

    // Refresh candles every 5 minutes
    candleRefreshTimer.current = setInterval(fetchCandles, 5 * 60 * 1000);

    return () => {
      wsRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (candleRefreshTimer.current) clearInterval(candleRefreshTimer.current);
      if (quotePollTimer.current) clearInterval(quotePollTimer.current);
    };
  }, [fetchCandles, fetchQuote, connectWs]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  // Order submission
  const handleOrderSubmit = (order: OrderPayload) => setPendingOrder(order);

  const handleOrderConfirm = async () => {
    if (!pendingOrder) return;
    setOrderLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(pendingOrder),
      });
      const data: OrderResult = await res.json();
      if (!res.ok) throw new Error((data as Record<string, string>).detail || "Order failed");
      setToast({ message: `Order placed! ID: ${data.order_id || "—"}`, type: "success" });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Order failed";
      setToast({ message, type: "error" });
    } finally {
      setOrderLoading(false);
      setPendingOrder(null);
    }
  };

  const currentLtp = liveLtp ?? quote?.ltp ?? 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Breadcrumb */}
      <nav className="mb-4 text-sm text-gray-500 dark:text-gray-400">
        <Link href="/" className="hover:text-gray-900 dark:hover:text-gray-200">
          Daily Picks
        </Link>
        <span className="mx-2">/</span>
        <Link href="/portfolio" className="hover:text-gray-900 dark:hover:text-gray-200">
          Portfolio
        </Link>
        <span className="mx-2">/</span>
        <span className="text-gray-900 dark:text-gray-100">{symbol}</span>
      </nav>

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
        <div className="space-y-6">
          <QuoteHeader quote={quote} liveLtp={liveLtp} />

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <CandlestickChart candles={candles} liveLtp={liveLtp} />
            </div>
            <div>
              <OrderPanel
                symbol={symbol}
                ltp={currentLtp}
                onSubmit={handleOrderSubmit}
              />
            </div>
          </div>
        </div>
      )}

      {/* Order confirm dialog */}
      {pendingOrder && (
        <OrderConfirmDialog
          order={pendingOrder}
          loading={orderLoading}
          onConfirm={handleOrderConfirm}
          onCancel={() => setPendingOrder(null)}
        />
      )}

      {/* Toast notification */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 rounded-lg px-4 py-3 text-sm font-medium text-white shadow-lg ${
            toast.type === "success" ? "bg-green-600" : "bg-red-600"
          }`}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}
