"use client";

interface RunSummary {
  id: number;
  algo_id: string;
  groww_symbol: string;
  segment: string;
  interval: string;
  start_date: string;
  end_date: string;
  metrics: {
    total_return_pct?: number;
    net_pnl?: number;
    trade_count?: number;
    win_rate_pct?: number;
  };
  created_at: string;
}

export default function BacktestHistoryList({
  runs,
  selectedId,
  onSelect,
  onDelete,
}: {
  runs: RunSummary[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
}) {
  if (!runs.length) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-gray-100">Past Runs</h3>
        <p className="text-xs text-gray-500 dark:text-gray-400">No backtest runs yet.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <h3 className="border-b border-gray-200 p-3 text-sm font-semibold text-gray-900 dark:border-gray-800 dark:text-gray-100">
        Past Runs
      </h3>
      <ul className="max-h-96 overflow-y-auto">
        {runs.map((r) => (
          <li
            key={r.id}
            className={`relative border-b border-gray-100 dark:border-gray-800 ${
              selectedId === r.id ? "bg-blue-50 dark:bg-blue-900/20" : ""
            }`}
          >
            <button
              type="button"
              onClick={() => onSelect(r.id)}
              className="w-full px-3 py-2 pr-16 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-xs font-medium text-gray-900 dark:text-gray-100">
                  {r.algo_id} · {r.groww_symbol}
                </span>
                <span className="shrink-0 text-xs text-gray-500 dark:text-gray-400">
                  {r.start_date} → {r.end_date}
                </span>
              </div>
              <div className="mt-0.5 flex gap-2 text-xs text-gray-600 dark:text-gray-400">
                {r.metrics?.total_return_pct != null && (
                  <span>
                    Return: {r.metrics.total_return_pct >= 0 ? "+" : ""}
                    {r.metrics.total_return_pct.toFixed(1)}%
                  </span>
                )}
                {r.metrics?.trade_count != null && <span>Trades: {r.metrics.trade_count}</span>}
              </div>
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(r.id);
              }}
              className="absolute top-1/2 right-2 -translate-y-1/2 text-xs text-red-500 hover:underline"
              aria-label="Delete run"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
