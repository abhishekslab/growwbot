"use client";

import BacktestEquityCurve from "./BacktestEquityCurve";
import BacktestTradeTable from "./BacktestTradeTable";

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

export default function BacktestResults({
  metrics,
  trades,
  equityCurve,
  error,
  signalAnalysis,
}: {
  metrics: BacktestMetrics | null;
  trades: BacktestTrade[];
  equityCurve: EquityPoint[];
  error: string | null;
  signalAnalysis?: Record<string, number> | null;
}) {
  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 dark:border-red-900 dark:bg-red-900/20">
        <p className="text-red-700 dark:text-red-300">{error}</p>
      </div>
    );
  }

  if (!metrics) {
    return null;
  }

  const cards = [
    { label: "Total Return", value: `${metrics.total_return_pct ?? 0}%` },
    {
      label: "Net P&L",
      value: `₹${(metrics.net_pnl ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`,
    },
    { label: "Trades", value: String(metrics.trade_count ?? 0) },
    { label: "Win Rate", value: `${metrics.win_rate_pct ?? 0}%` },
    { label: "Max Drawdown", value: `${metrics.max_drawdown_pct ?? 0}%` },
    { label: "Sharpe", value: String(metrics.sharpe_ratio ?? 0) },
    {
      label: "Profit Factor",
      value: metrics.profit_factor != null ? String(metrics.profit_factor) : "—",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7">
        {cards.map((c) => (
          <div
            key={c.label}
            className="rounded-lg border border-gray-200 bg-white p-3 shadow-sm dark:border-gray-800 dark:bg-gray-900"
          >
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{c.label}</p>
            <p className="mt-0.5 text-sm font-semibold text-gray-900 dark:text-gray-100">
              {c.value}
            </p>
          </div>
        ))}
      </div>
      {equityCurve.length > 0 && <BacktestEquityCurve data={equityCurve} />}
      <BacktestTradeTable trades={trades} />
      {signalAnalysis && Object.keys(signalAnalysis).length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-900/20">
          <p className="mb-3 text-sm font-semibold text-amber-800 dark:text-amber-300">
            Signal Analysis — Why the algo filtered out signals
          </p>
          <div className="space-y-1.5">
            {Object.entries(signalAnalysis)
              .sort(([, a], [, b]) => b - a)
              .map(([reason, count]) => {
                const total = Object.values(signalAnalysis).reduce((s, v) => s + v, 0);
                const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                return (
                  <div key={reason} className="flex items-center gap-2 text-xs">
                    <div className="w-48 shrink-0 text-amber-700 dark:text-amber-400">{reason}</div>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-amber-100 dark:bg-amber-900/40">
                      <div
                        className="h-full rounded-full bg-amber-400 dark:bg-amber-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="w-20 shrink-0 text-right font-mono text-amber-800 dark:text-amber-300">
                      {count.toLocaleString()} ({pct}%)
                    </div>
                  </div>
                );
              })}
          </div>
          {(metrics?.trade_count ?? 0) === 0 && (
            <p className="mt-3 text-xs text-amber-600 dark:text-amber-400">
              Tip: try a longer date range, a more volatile period, or the Mean Reversion algo which
              has less strict entry conditions.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
