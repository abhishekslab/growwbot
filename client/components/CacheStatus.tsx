"use client";

import { useEffect, useState, useCallback } from "react";

interface CacheState {
  instruments_cached: boolean;
  ohlc_batches: number;
  historical_symbols: number;
  news_entries: number;
  warming: boolean;
  last_warmup: string | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CacheStatus() {
  const [status, setStatus] = useState<CacheState | null>(null);

  const fetchStatus = useCallback(() => {
    fetch(`${API_URL}/api/cache/status`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setStatus(data);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10_000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleWarmup = () => {
    fetch(`${API_URL}/api/cache/warmup`, { method: "POST" })
      .then(() => {
        // Poll more frequently while warming
        setTimeout(fetchStatus, 2000);
      })
      .catch(() => {});
  };

  if (!status) return null;

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border border-gray-200 bg-gray-50 px-4 py-2 text-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-center gap-1.5">
        <span
          className={`inline-block h-2 w-2 rounded-full ${
            status.instruments_cached ? "bg-green-500" : "bg-gray-400"
          }`}
        />
        <span className="text-gray-600 dark:text-gray-300">Instruments</span>
      </div>

      <span className="text-gray-500 dark:text-gray-400">OHLC: {status.ohlc_batches}</span>
      <span className="text-gray-500 dark:text-gray-400">
        Historical: {status.historical_symbols}
      </span>
      <span className="text-gray-500 dark:text-gray-400">News: {status.news_entries}</span>

      {status.last_warmup && (
        <span className="text-gray-400 dark:text-gray-500">
          Last warmup: {formatTime(status.last_warmup)}
        </span>
      )}

      <button
        onClick={handleWarmup}
        disabled={status.warming}
        className="ml-auto rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {status.warming ? "Warming..." : "Warmup Cache"}
      </button>
    </div>
  );
}
