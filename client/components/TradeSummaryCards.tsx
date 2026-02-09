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

export default function TradeSummaryCards({ summary }: { summary: Summary }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Card label="Total Trades" value={summary.total_trades.toString()} />
      <Card label="Open Trades" value={summary.open_trades.toString()} />
      <Card
        label="Win Rate"
        value={`${summary.win_rate}%`}
        sub={`${summary.won}W / ${summary.lost}L`}
      />
      <Card
        label="Net P&L"
        value={`${summary.net_pnl >= 0 ? "+" : "-"}${fmt(summary.net_pnl)}`}
        color={summary.net_pnl >= 0 ? "green" : "red"}
        sub={`Fees: ${fmt(summary.total_fees)}`}
      />
    </div>
  );
}

function Card({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: "green" | "red";
}) {
  const colorClass =
    color === "green"
      ? "text-green-600 dark:text-green-400"
      : color === "red"
      ? "text-red-600 dark:text-red-400"
      : "text-gray-900 dark:text-gray-100";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{label}</p>
      <p className={`mt-1 text-lg font-bold ${colorClass}`}>{value}</p>
      {sub && (
        <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{sub}</p>
      )}
    </div>
  );
}
