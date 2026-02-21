"use client";

import { useCallback, useEffect, useState } from "react";
import SymbolSearch from "./SymbolSearch";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const CANDLE_INTERVALS = [
  "1minute",
  "2minute",
  "3minute",
  "5minute",
  "10minute",
  "15minute",
  "30minute",
  "1hour",
  "4hours",
  "1day",
  "1week",
  "1month",
];

interface AlgoInfo {
  algo_id: string;
  name: string;
  description?: string;
}

export interface BacktestRunRequest {
  algo_id: string;
  groww_symbol: string;
  exchange: string;
  segment: string;
  start_date: string;
  end_date: string;
  candle_interval: string;
  initial_capital: number;
  risk_percent: number;
  max_positions: number;
  config_overrides?: Record<string, unknown>;
}

export default function BacktestConfigPanel({
  onRun,
  running,
  progressPercent,
  progressLabel,
}: {
  onRun: (body: BacktestRunRequest) => void;
  running: boolean;
  progressPercent: number | null;
  progressLabel: string | null;
}) {
  const [algos, setAlgos] = useState<AlgoInfo[]>([]);
  const [algoId, setAlgoId] = useState("");
  const [growwSymbol, setGrowwSymbol] = useState("");
  const [segment, setSegment] = useState<"CASH" | "FNO">("CASH");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [candleInterval, setCandleInterval] = useState("5minute");
  const [initialCapital, setInitialCapital] = useState(100000);
  const [riskPercent, setRiskPercent] = useState(1);
  const [exchange] = useState("NSE");

  useEffect(() => {
    fetch(`${API}/api/algos`)
      .then((r) => r.json())
      .then((data) => {
        if (!data?.algos?.length) return;
        const list = data.algos.map((a: { id: string; name?: string }) => ({
          algo_id: a.id,
          name: a.name || a.id,
        }));
        setAlgos(list);
        setAlgoId(list[0].algo_id);
      })
      .catch(() => {});
  }, []);

  // Pre-warm instrument cache for faster symbol search
  useEffect(() => {
    fetch(`${API}/api/cache/warmup`, { method: "POST" }).catch(() => {});
  }, []);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (!algoId || !growwSymbol.trim() || !startDate || !endDate) return;
      onRun({
        algo_id: algoId,
        groww_symbol: growwSymbol.trim(),
        exchange,
        segment,
        start_date: startDate,
        end_date: endDate,
        candle_interval: candleInterval,
        initial_capital: initialCapital,
        risk_percent: riskPercent,
        max_positions: 1,
      });
    },
    [
      algoId,
      growwSymbol,
      exchange,
      segment,
      startDate,
      endDate,
      candleInterval,
      initialCapital,
      riskPercent,
      onRun,
    ],
  );

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-gray-100">
        Backtest Config
      </h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">
            Algorithm
          </label>
          <select
            value={algoId}
            onChange={(e) => setAlgoId(e.target.value)}
            className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
          >
            {algos.map((a) => (
              <option key={a.algo_id} value={a.algo_id}>
                {a.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">
            Segment
          </label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="segment"
                checked={segment === "CASH"}
                onChange={() => setSegment("CASH")}
                className="rounded"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">CASH</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="segment"
                checked={segment === "FNO"}
                onChange={() => setSegment("FNO")}
                className="rounded"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">FNO</span>
            </label>
          </div>
        </div>
        <SymbolSearch
          value={growwSymbol}
          onChange={setGrowwSymbol}
          segment={segment}
          disabled={running}
        />
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">
              Start Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">
              End Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
            />
          </div>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">
            Candle Interval
          </label>
          <select
            value={candleInterval}
            onChange={(e) => setCandleInterval(e.target.value)}
            className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
          >
            {CANDLE_INTERVALS.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">
              Initial Capital (₹)
            </label>
            <input
              type="number"
              min={1000}
              step={1000}
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">
              Risk %
            </label>
            <input
              type="number"
              min={0.1}
              max={100}
              step={0.1}
              value={riskPercent}
              onChange={(e) => setRiskPercent(Number(e.target.value))}
              className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
            />
          </div>
        </div>
        {running && (
          <div className="rounded bg-blue-50 px-3 py-2 text-sm text-blue-800 dark:bg-blue-900/30 dark:text-blue-200">
            {progressLabel ?? "Running…"}{" "}
            {progressPercent != null ? `(${progressPercent.toFixed(0)}%)` : ""}
          </div>
        )}
        <button
          type="submit"
          disabled={running || !algoId || !growwSymbol.trim() || !startDate || !endDate}
          className="w-full rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
        >
          {running ? "Running…" : "Run Backtest"}
        </button>
      </form>
    </div>
  );
}
