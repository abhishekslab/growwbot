"use client";

import { useState } from "react";
import type { DailyPicksBacktestRequest } from "./page";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Props {
  onRun: (body: DailyPicksBacktestRequest) => void;
  running: boolean;
}

const INTERVALS = [
  { value: "1minute", label: "1 Minute" },
  { value: "5minute", label: "5 Minutes" },
];

export default function DailyPicksBacktestConfig({ onRun, running }: Props) {
  const [algoId, setAlgoId] = useState("momentum_scalp");
  const [startDate, setStartDate] = useState("2025-02-10");
  const [endDate, setEndDate] = useState("2025-02-14");
  const [interval, setInterval] = useState("5minute");
  const [initialCapital, setInitialCapital] = useState(100000);
  const [maxPositions, setMaxPositions] = useState(3);
  const [riskPercent, setRiskPercent] = useState(1);
  const [maxDuration, setMaxDuration] = useState(15);
  const [useCached, setUseCached] = useState(true);
  const [clearingCache, setClearingCache] = useState(false);
  const [cacheMessage, setCacheMessage] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRun({
      algo_id: algoId,
      start_date: startDate,
      end_date: endDate,
      candle_interval: interval,
      initial_capital: initialCapital,
      max_positions_per_day: maxPositions,
      risk_percent: riskPercent,
      max_trade_duration_minutes: maxDuration,
      use_cached_snapshots: useCached,
    });
  };

  const handleClearCache = async () => {
    setClearingCache(true);
    setCacheMessage(null);
    try {
      const response = await fetch(`${API}/api/backtest/cache-daily-picks`, {
        method: "DELETE",
      });
      const data = await response.json();
      setCacheMessage(`Cache cleared: ${data.deleted_snapshots || 0} snapshots removed`);
    } catch (error) {
      setCacheMessage("Failed to clear cache");
    } finally {
      setClearingCache(false);
      setTimeout(() => setCacheMessage(null), 3000);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800"
    >
      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Algorithm
            </label>
            <select
              value={algoId}
              onChange={(e) => setAlgoId(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              disabled={running}
            >
              <option value="momentum_scalp">Momentum Scalping</option>
              <option value="mean_reversion">Mean Reversion</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                Start Date
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                disabled={running}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                End Date
              </label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                disabled={running}
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Candle Interval
            </label>
            <select
              value={interval}
              onChange={(e) => setInterval(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              disabled={running}
            >
              {INTERVALS.map((i) => (
                <option key={i.value} value={i.value}>
                  {i.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Initial Capital (₹)
            </label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              min={10000}
              step={10000}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              disabled={running}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Max Positions Per Day
            </label>
            <input
              type="number"
              value={maxPositions}
              onChange={(e) => setMaxPositions(Number(e.target.value))}
              min={1}
              max={10}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              disabled={running}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                Risk %
              </label>
              <input
                type="number"
                value={riskPercent}
                onChange={(e) => setRiskPercent(Number(e.target.value))}
                min={0.1}
                max={10}
                step={0.1}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                disabled={running}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                Max Duration (min)
              </label>
              <input
                type="number"
                value={maxDuration}
                onChange={(e) => setMaxDuration(Number(e.target.value))}
                min={5}
                max={60}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                disabled={running}
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="useCached"
              checked={useCached}
              onChange={(e) => setUseCached(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              disabled={running}
            />
            <label htmlFor="useCached" className="text-sm text-gray-700 dark:text-gray-300">
              Use cached daily picks (faster)
            </label>
          </div>
        </div>
      </div>

      <div className="mt-6 flex gap-3">
        <button
          type="submit"
          disabled={running}
          className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
        >
          {running ? "Running Backtest..." : "Run Daily Picks Backtest"}
        </button>
        <button
          type="button"
          onClick={handleClearCache}
          disabled={clearingCache || running}
          className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
        >
          {clearingCache ? "Clearing..." : "Clear Cache"}
        </button>
      </div>

      {cacheMessage && (
        <div className="mt-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700 dark:border-green-800 dark:bg-green-900/20 dark:text-green-400">
          {cacheMessage}
        </div>
      )}

      <div className="mt-4 text-xs text-gray-500 dark:text-gray-400">
        <p>
          This will backtest the complete pipeline: daily picks selection → intraday signals →
          position management.
        </p>
        <p className="mt-1">
          All positions are squared off at EOD (intraday mode). Capital compounds day-to-day.
        </p>
      </div>
    </form>
  );
}
