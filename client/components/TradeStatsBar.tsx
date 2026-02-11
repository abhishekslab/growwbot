"use client";

const fmt = (n: number) =>
  "₹" + Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

interface Summary {
  total_trades: number;
  open_trades: number;
  won: number;
  lost: number;
  closed: number;
  win_rate: number;
  net_pnl: number;
  total_fees: number;
}

export default function TradeStatsBar({ summary, paperMode }: { summary: Summary; paperMode?: boolean }) {
  const stats = [
    { label: "Open", value: String(summary.open_trades) },
    { label: "Won", value: String(summary.won) },
    { label: "Lost", value: String(summary.lost) },
    { label: "Win Rate", value: `${summary.win_rate}%` },
    {
      label: "Net P&L",
      value: `${summary.net_pnl >= 0 ? "+" : "-"}${fmt(summary.net_pnl)}`,
      color: summary.net_pnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400",
    },
    { label: "Fees", value: fmt(summary.total_fees) },
  ];

  return (
    <div className="flex flex-wrap items-center gap-6 rounded-xl border border-gray-200 bg-white px-5 py-3 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      {paperMode && (
        <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-semibold text-orange-700 dark:bg-orange-900/50 dark:text-orange-300">
          Paper
        </span>
      )}
      {stats.map((s, i) => (
        <div key={s.label} className="flex items-center gap-6">
          {i > 0 && (
            <div className="hidden h-5 border-l border-gray-200 dark:border-gray-700 sm:block" />
          )}
          <div className="flex items-baseline gap-1.5">
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
              {s.label}:
            </span>
            <span className={`text-sm font-semibold ${s.color || "text-gray-900 dark:text-gray-100"}`}>
              {s.value}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
