"use client";

import { useCallback, useEffect, useState } from "react";
import DailyPicksBacktestConfig from "@/components/DailyPicksBacktestConfig";
import BacktestResults from "@/components/BacktestResults";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface BacktestMetrics {
  initial_capital?: number;
  final_equity?: number;
  total_return_pct?: number;
  total_fees?: number;
  net_pnl?: number;
  trade_count?: number;
  wins?: number;
  losses?: number;
  win_rate_pct?: number;
  profit_factor?: number | null;
  max_drawdown?: number;
  max_drawdown_pct?: number;
  sharpe_ratio?: number;
  sortino_ratio?: number;
  avg_win?: number;
  avg_loss?: number;
  best_trade?: number;
  worst_trade?: number;
  start_date?: string;
  end_date?: string;
  total_days?: number;
}

interface BacktestTrade {
  symbol: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  entry_time: number;
  exit_time: number;
  pnl: number;
  fees: number;
  exit_trigger: string;
  reason?: string;
  date: string;
}

interface EquityPoint {
  date: string;
  equity: number;
  daily_pnl?: number;
  daily_fees?: number;
}

interface DailySummary {
  date: string;
  candidates_count: number;
  trades_count: number;
  daily_pnl: number;
  daily_fees: number;
  current_equity: number;
}

export interface DailyPicksBacktestRequest {
  algo_id: string;
  start_date: string;
  end_date: string;
  candle_interval: string;
  initial_capital: number;
  max_positions_per_day: number;
  risk_percent: number;
  max_trade_duration_minutes: number;
  use_cached_snapshots: boolean;
}

export default function DailyPicksBacktestPage() {
  const [metrics, setMetrics] = useState<BacktestMetrics | null>(null);
  const [trades, setTrades] = useState<BacktestTrade[]>([]);
  const [equityCurve, setEquityCurve] = useState<EquityPoint[]>([]);
  const [dailySummaries, setDailySummaries] = useState<DailySummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [currentDay, setCurrentDay] = useState<number>(0);
  const [totalDays, setTotalDays] = useState<number>(0);
  const [currentDate, setCurrentDate] = useState<string | null>(null);

  const handleRun = useCallback((body: DailyPicksBacktestRequest) => {
    setRunning(true);
    setError(null);
    setMetrics(null);
    setTrades([]);
    setEquityCurve([]);
    setDailySummaries([]);
    setCurrentDay(0);
    setTotalDays(0);
    setCurrentDate(null);

    fetch(`${API}/api/backtest/daily-picks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
      .then((res) => {
        if (!res.ok) throw new Error(res.statusText);
        return res.body?.getReader();
      })
      .then((reader) => {
        if (!reader) throw new Error("No body");
        const decoder = new TextDecoder();
        let buffer = "";

        function read(): Promise<void> {
          return reader.read().then(({ done, value }) => {
            if (done) return;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() ?? "";

            for (const line of lines) {
              if (line.startsWith("data: ")) {
                try {
                  const ev = JSON.parse(line.slice(6));

                  if (ev.event_type === "day_start") {
                    setCurrentDay(ev.day ?? 0);
                    setTotalDays(ev.total_days ?? 0);
                    setCurrentDate(ev.date);
                  } else if (ev.event_type === "trade" && ev.trade) {
                    setTrades((prev) => [...prev, ev.trade]);
                  } else if (ev.event_type === "day_complete") {
                    setDailySummaries((prev) => [
                      ...prev,
                      {
                        date: ev.date,
                        candidates_count: ev.candidates_count ?? 0,
                        trades_count: ev.trades_count ?? 0,
                        daily_pnl: ev.daily_pnl ?? 0,
                        daily_fees: ev.daily_fees ?? 0,
                        current_equity: ev.current_equity ?? 0,
                      },
                    ]);
                    setCurrentDay(ev.day ?? 0);
                  } else if (ev.event_type === "complete") {
                    if (ev.error) {
                      setError(ev.error);
                    } else {
                      setMetrics(ev.metrics ?? null);
                      setTrades(ev.trades ?? []);
                      setEquityCurve(ev.equity_curve ?? []);
                    }
                    setRunning(false);
                  }
                } catch (e) {
                  console.error("Parse error:", e);
                }
              }
            }
            return read();
          });
        }
        return read();
      })
      .catch((e) => {
        setError(e.message || "Request failed");
        setRunning(false);
      });
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 p-6 dark:bg-gray-900">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Daily Picks Pipeline Backtest
            </h1>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              Backtest the complete trading pipeline: daily picks → intraday signals → position
              management
            </p>
          </div>
          <a
            href="/backtest"
            className="rounded-lg bg-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            Single Symbol Backtest →
          </a>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
            {error}
          </div>
        )}

        <DailyPicksBacktestConfig onRun={handleRun} running={running} />

        {running && (
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-900/20">
            <div className="flex items-center gap-3">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent dark:border-blue-400" />
              <div className="flex-1">
                <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                  Processing Day {currentDay} of {totalDays}
                  {currentDate && ` (${currentDate})`}
                </p>
                <div className="mt-2 h-2 w-full rounded-full bg-blue-200 dark:bg-blue-800">
                  <div
                    className="h-2 rounded-full bg-blue-600 transition-all dark:bg-blue-400"
                    style={{
                      width: totalDays > 0 ? `${(currentDay / totalDays) * 100}%` : "0%",
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {dailySummaries.length > 0 && (
          <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
            <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">
              Daily Summary
            </h3>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="py-2 text-left font-medium text-gray-600 dark:text-gray-400">
                      Date
                    </th>
                    <th className="py-2 text-right font-medium text-gray-600 dark:text-gray-400">
                      Candidates
                    </th>
                    <th className="py-2 text-right font-medium text-gray-600 dark:text-gray-400">
                      Trades
                    </th>
                    <th className="py-2 text-right font-medium text-gray-600 dark:text-gray-400">
                      P&L
                    </th>
                    <th className="py-2 text-right font-medium text-gray-600 dark:text-gray-400">
                      Equity
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {dailySummaries.map((day) => (
                    <tr key={day.date} className="border-b border-gray-100 dark:border-gray-800">
                      <td className="py-2 text-gray-900 dark:text-gray-300">{day.date}</td>
                      <td className="py-2 text-right text-gray-600 dark:text-gray-400">
                        {day.candidates_count}
                      </td>
                      <td className="py-2 text-right text-gray-600 dark:text-gray-400">
                        {day.trades_count}
                      </td>
                      <td
                        className={`py-2 text-right font-medium ${day.daily_pnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
                      >
                        ₹{day.daily_pnl.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                      </td>
                      <td className="py-2 text-right text-gray-900 dark:text-gray-300">
                        ₹{day.current_equity.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {metrics && (
          <BacktestResults
            metrics={metrics}
            trades={trades}
            equityCurve={equityCurve.map((p) => ({
              time: new Date(p.date).getTime() / 1000,
              equity: p.equity,
            }))}
            signalAnalysis={null}
          />
        )}
      </div>
    </div>
  );
}
