"use client";

import { useCallback, useEffect, useState } from "react";
import BacktestConfigPanel, { type BacktestRunRequest } from "@/components/BacktestConfigPanel";
import BacktestResults from "@/components/BacktestResults";
import BacktestHistoryList from "@/components/BacktestHistoryList";

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
}

interface BacktestTrade {
  entry_price: number;
  exit_price: number;
  quantity: number;
  entry_time: number;
  exit_time: number;
  pnl: number;
  fees: number;
  exit_trigger: string;
  reason?: string;
}

interface EquityPoint {
  time: number;
  equity: number;
}

interface HistoryRun {
  id: number;
  algo_id: string;
  groww_symbol: string;
  segment: string;
  interval: string;
  start_date: string;
  end_date: string;
  metrics: BacktestMetrics;
  created_at: string;
}

interface FullRun extends HistoryRun {
  config?: Record<string, unknown>;
  trades?: BacktestTrade[];
  equity_curve?: EquityPoint[];
}

export default function BacktestPage() {
  const [history, setHistory] = useState<HistoryRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [fullRun, setFullRun] = useState<FullRun | null>(null);
  const [metrics, setMetrics] = useState<BacktestMetrics | null>(null);
  const [trades, setTrades] = useState<BacktestTrade[]>([]);
  const [equityCurve, setEquityCurve] = useState<EquityPoint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [signalAnalysis, setSignalAnalysis] = useState<Record<string, number> | null>(null);
  const [running, setRunning] = useState(false);
  const [progressPercent, setProgressPercent] = useState<number | null>(null);
  const [progressLabel, setProgressLabel] = useState<string | null>(null);

  const fetchHistory = useCallback(() => {
    fetch(`${API}/api/backtest/history`)
      .then((r) => r.json())
      .then(setHistory)
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const loadRun = useCallback((id: number) => {
    setSelectedRunId(id);
    fetch(`${API}/api/backtest/${id}`)
      .then((r) => r.json())
      .then((run: FullRun) => {
        setFullRun(run);
        setMetrics(run.metrics ?? null);
        setTrades(run.trades ?? []);
        setEquityCurve(run.equity_curve ?? []);
        setSignalAnalysis(null);
        setError(null);
      })
      .catch(() => setError("Failed to load run"));
  }, []);

  const handleRun = useCallback(
    (body: BacktestRunRequest) => {
      setRunning(true);
      setError(null);
      setMetrics(null);
      setTrades([]);
      setEquityCurve([]);
      setSignalAnalysis(null);
      setProgressPercent(0);
      setProgressLabel("Loading…");

      fetch(`${API}/api/backtest/run`, {
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
                    if (ev.event_type === "progress") {
                      setProgressPercent(ev.percent ?? null);
                      setProgressLabel(ev.current_date ?? "Running…");
                    } else if (ev.event_type === "trade" && ev.trade) {
                      setTrades((prev) => [...prev, ev.trade]);
                    } else if (ev.event_type === "complete") {
                      if (ev.error) {
                        setError(ev.error);
                      } else {
                        setMetrics(ev.metrics ?? null);
                        setTrades(ev.trades ?? []);
                        setEquityCurve(ev.equity_curve ?? []);
                        setSignalAnalysis(
                          ev.signal_analysis && Object.keys(ev.signal_analysis).length > 0
                            ? ev.signal_analysis
                            : null,
                        );
                        if (ev.run_id) {
                          setSelectedRunId(ev.run_id);
                          fetchHistory();
                        }
                      }
                      setRunning(false);
                      setProgressPercent(null);
                      setProgressLabel(null);
                      return;
                    }
                  } catch {
                    // skip malformed line
                  }
                }
              }
              return read();
            });
          }
          return read();
        })
        .catch((e) => {
          setError(e?.message ?? "Backtest failed");
          setRunning(false);
          setProgressPercent(null);
          setProgressLabel(null);
        });
    },
    [fetchHistory],
  );
  const handleDeleteRun = useCallback(
    (id: number) => {
      fetch(`${API}/api/backtest/${id}`, { method: "DELETE" }).then(() => {
        fetchHistory();
        if (selectedRunId === id) {
          setSelectedRunId(null);
          setFullRun(null);
          setMetrics(null);
          setTrades([]);
          setEquityCurve([]);
        }
      });
    },
    [fetchHistory, selectedRunId],
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <h1 className="mb-6 text-2xl font-bold text-gray-900 dark:text-gray-100">Backtest</h1>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
        <div className="lg:col-span-1">
          <div className="space-y-4">
            <BacktestConfigPanel
              onRun={handleRun}
              running={running}
              progressPercent={progressPercent}
              progressLabel={progressLabel}
            />
            <BacktestHistoryList
              runs={history}
              selectedId={selectedRunId}
              onSelect={loadRun}
              onDelete={handleDeleteRun}
            />
          </div>
        </div>
        <div className="lg:col-span-3">
          <BacktestResults
            metrics={metrics}
            trades={trades}
            equityCurve={equityCurve}
            error={error}
            signalAnalysis={signalAnalysis}
          />
        </div>
      </div>
    </div>
  );
}
