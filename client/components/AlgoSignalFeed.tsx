"use client";

interface Signal {
  algo_id: string;
  symbol: string;
  signal_type: string;
  reason: string;
  trade_id?: number;
  timestamp?: number;
  created_at?: string;
}

interface AlgoSignalFeedProps {
  signals: Signal[];
  algoNames: Record<string, string>;
}

const ALGO_COLORS: Record<string, string> = {
  momentum_scalp:
    "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  mean_reversion:
    "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
};

const SIGNAL_COLORS: Record<string, string> = {
  ENTRY: "text-green-600 dark:text-green-400",
  SKIP: "text-yellow-600 dark:text-yellow-400",
  ERROR: "text-red-600 dark:text-red-400",
  FORCE_CLOSE: "text-orange-600 dark:text-orange-400",
  TIME_EXIT: "text-orange-600 dark:text-orange-400",
};

function formatTime(signal: Signal): string {
  if (signal.timestamp) {
    return new Date(signal.timestamp * 1000).toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }
  if (signal.created_at) {
    return new Date(signal.created_at).toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }
  return "";
}

export default function AlgoSignalFeed({
  signals,
  algoNames,
}: AlgoSignalFeedProps) {
  if (signals.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
        No signals yet. Signals will appear when the engine evaluates symbols during market hours.
      </div>
    );
  }

  return (
    <div className="max-h-96 overflow-y-auto rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
      <div className="divide-y divide-gray-100 dark:divide-gray-700">
        {signals.map((signal, idx) => (
          <div
            key={idx}
            className="flex items-start gap-3 px-4 py-3"
          >
            <span className="mt-0.5 shrink-0 text-xs text-gray-400 dark:text-gray-500">
              {formatTime(signal)}
            </span>
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                ALGO_COLORS[signal.algo_id] ||
                "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
              }`}
            >
              {algoNames[signal.algo_id] || signal.algo_id}
            </span>
            <span className="shrink-0 text-sm font-medium text-gray-900 dark:text-gray-100">
              {signal.symbol}
            </span>
            <span
              className={`shrink-0 text-xs font-semibold ${
                SIGNAL_COLORS[signal.signal_type] || "text-gray-500"
              }`}
            >
              {signal.signal_type}
            </span>
            <span className="min-w-0 truncate text-xs text-gray-500 dark:text-gray-400">
              {signal.reason}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
