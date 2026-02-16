"use client";

import { useState, useEffect, useCallback } from "react";
import AlgoCard from "@/components/AlgoCard";
import AlgoPerformanceTable from "@/components/AlgoPerformanceTable";
import AlgoSignalFeed from "@/components/AlgoSignalFeed";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AlgoInfo {
  algo_id: string;
  name: string;
  description: string;
  version?: string;
  enabled: boolean;
  open_trades?: number;
  capital: number;
  risk_percent: number;
  compounding: boolean;
  effective_capital: number;
  compounding_pnl: number;
}

interface CycleStats {
  candidates: number;
  evaluated: number;
  candle_hits: number;
  candle_api: number;
  candle_fails: number;
  signals: number;
  entries: number;
  stale_closed: number;
}

interface EngineStatus {
  running: boolean;
  cycle_interval: number;
  cycle_count: number;
  last_cycle_time: number;
  last_cycle_at?: string;
  market_status?: string;
  last_cycle_stats?: CycleStats;
  algos: AlgoInfo[];
}

interface AlgoPerf {
  algo_id: string;
  algo_version?: string;
  total_trades: number;
  won: number;
  lost: number;
  win_rate: number;
  net_pnl: number;
  avg_profit: number;
  avg_loss: number;
  total_fees: number;
  worst_trade: number;
}

interface Signal {
  algo_id: string;
  symbol: string;
  signal_type: string;
  reason: string;
  trade_id?: number;
  timestamp?: number;
  created_at?: string;
}

export default function AlgosPage() {
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [performance, setPerformance] = useState<AlgoPerf[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [statusRes, perfRes] = await Promise.all([
        fetch(`${API}/api/algos`),
        fetch(`${API}/api/algos/performance?is_paper=true`),
      ]);
      if (statusRes.ok) setStatus(await statusRes.json());
      if (perfRes.ok) setPerformance(await perfRes.json());
      setError(null);
    } catch (e) {
      setError("Failed to connect to server");
    }
  }, []);

  const fetchSignals = useCallback(async () => {
    try {
      // Fetch signals for all algos combined (use first algo or all)
      if (!status?.algos.length) return;
      const allSignals: Signal[] = [];
      for (const algo of status.algos) {
        const res = await fetch(
          `${API}/api/algos/${algo.algo_id}/signals?limit=30`
        );
        if (res.ok) {
          const data = await res.json();
          allSignals.push(...data);
        }
      }
      // Sort by created_at desc
      allSignals.sort((a, b) => {
        const ta = a.timestamp || new Date(a.created_at || 0).getTime() / 1000;
        const tb = b.timestamp || new Date(b.created_at || 0).getTime() / 1000;
        return tb - ta;
      });
      setSignals(allSignals.slice(0, 50));
    } catch {
      // silently ignore signal fetch errors
    }
  }, [status?.algos]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 5000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  useEffect(() => {
    if (status?.algos.length) fetchSignals();
    const interval = setInterval(fetchSignals, 10000);
    return () => clearInterval(interval);
  }, [status?.algos.length, fetchSignals]);

  const handleToggle = async (algoId: string, enable: boolean) => {
    try {
      await fetch(`${API}/api/algos/${algoId}/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: enable }),
      });
      fetchAll();
    } catch {
      // ignore
    }
  };

  const handleCapitalChange = async (algoId: string, capital: number) => {
    try {
      await fetch(`${API}/api/algos/${algoId}/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ capital }),
      });
      fetchAll();
    } catch {
      // ignore
    }
  };

  const handleCompoundingToggle = async (
    algoId: string,
    compounding: boolean
  ) => {
    try {
      await fetch(`${API}/api/algos/${algoId}/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ compounding }),
      });
      fetchAll();
    } catch {
      // ignore
    }
  };

  const algoNames: Record<string, string> = {};
  if (status?.algos) {
    for (const a of status.algos) {
      algoNames[a.algo_id] = a.name;
    }
  }

  const perfMap: Record<string, AlgoPerf> = {};
  for (const p of performance) {
    perfMap[p.algo_id] = p;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Algo Trading
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Automated paper trading strategies on 1-minute candles
          </p>
        </div>
        {status && (
          <div className="text-right text-xs text-gray-500 dark:text-gray-400">
            <p>
              Engine:{" "}
              <span
                className={
                  status.running
                    ? "font-medium text-green-600 dark:text-green-400"
                    : "font-medium text-red-600 dark:text-red-400"
                }
              >
                {status.running ? "Running" : "Stopped"}
              </span>
            </p>
            {status.market_status && (
              <p>
                Market:{" "}
                <span
                  className={
                    status.market_status === "scanning"
                      ? "font-medium text-blue-600 dark:text-blue-400"
                      : status.market_status === "trading"
                        ? "font-medium text-green-600 dark:text-green-400"
                        : "font-medium text-gray-500"
                  }
                >
                  {status.market_status === "scanning"
                    ? "Scanning..."
                    : status.market_status === "trading"
                      ? "Trading"
                      : status.market_status === "waiting"
                        ? "Waiting for window"
                        : status.market_status === "force_closing"
                          ? "Force closing"
                          : "Closed"}
                </span>
              </p>
            )}
            <p>Cycles: {status.cycle_count}</p>
            {status.last_cycle_at && (
              <p>
                Last scan:{" "}
                {new Date(status.last_cycle_at).toLocaleTimeString("en-IN", {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </p>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Live Cycle Stats */}
      {status?.last_cycle_stats && status.last_cycle_stats.candidates > 0 && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {[
            {
              label: "Candidates",
              value: status.last_cycle_stats.candidates,
              color: "text-gray-900 dark:text-gray-100",
            },
            {
              label: "Evaluated",
              value: status.last_cycle_stats.evaluated,
              color: "text-blue-600 dark:text-blue-400",
            },
            {
              label: "Cache Hits",
              value: status.last_cycle_stats.candle_hits,
              color: "text-green-600 dark:text-green-400",
            },
            {
              label: "API Calls",
              value: status.last_cycle_stats.candle_api,
              color: "text-orange-600 dark:text-orange-400",
            },
            {
              label: "Signals",
              value: status.last_cycle_stats.signals,
              color: "text-purple-600 dark:text-purple-400",
            },
            {
              label: "Entries",
              value: status.last_cycle_stats.entries,
              color: "text-green-600 dark:text-green-400",
            },
            {
              label: "Cycle Time",
              value: status.last_cycle_time.toFixed(1) + "s",
              color: "text-gray-900 dark:text-gray-100",
            },
          ].map((stat) => (
            <div
              key={stat.label}
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-700 dark:bg-gray-800"
            >
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {stat.label}
              </p>
              <p className={`text-lg font-semibold ${stat.color}`}>
                {stat.value}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Algo Cards */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {status?.algos.map((algo) => (
          <AlgoCard
            key={algo.algo_id}
            algo={algo}
            perf={perfMap[algo.algo_id]}
            onToggle={handleToggle}
            onCapitalChange={handleCapitalChange}
            onCompoundingToggle={handleCompoundingToggle}
          />
        ))}
      </div>

      {/* Performance Table */}
      <div className="mb-8">
        <h2 className="mb-3 text-lg font-semibold text-gray-900 dark:text-gray-100">
          Performance Comparison
        </h2>
        <AlgoPerformanceTable data={performance} algoNames={algoNames} />
      </div>

      {/* Signal Feed */}
      <div>
        <h2 className="mb-3 text-lg font-semibold text-gray-900 dark:text-gray-100">
          Signal Feed
        </h2>
        <AlgoSignalFeed signals={signals} algoNames={algoNames} />
      </div>
    </div>
  );
}
