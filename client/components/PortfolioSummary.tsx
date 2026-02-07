"use client";

interface Summary {
  total_current_value: number;
  total_invested_value: number;
  total_pnl: number;
  total_pnl_percentage: number;
}

export default function PortfolioSummary({ summary }: { summary: Summary }) {
  const formatCurrency = (val: number) =>
    "₹" + val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const pnlColor = summary.total_pnl >= 0 ? "text-green-600" : "text-red-600";
  const pnlBg = summary.total_pnl >= 0 ? "bg-green-50 dark:bg-green-950" : "bg-red-50 dark:bg-red-950";

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <p className="text-sm text-gray-500 dark:text-gray-400">Total Current Value</p>
        <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">
          {formatCurrency(summary.total_current_value)}
        </p>
      </div>
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <p className="text-sm text-gray-500 dark:text-gray-400">Total Invested</p>
        <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">
          {formatCurrency(summary.total_invested_value)}
        </p>
      </div>
      <div className={`rounded-xl border border-gray-200 p-6 shadow-sm dark:border-gray-800 ${pnlBg}`}>
        <p className="text-sm text-gray-500 dark:text-gray-400">Total P&L</p>
        <p className={`mt-1 text-2xl font-bold ${pnlColor}`}>
          {formatCurrency(summary.total_pnl)}
        </p>
        <p className={`text-sm ${pnlColor}`}>
          ({summary.total_pnl >= 0 ? "+" : ""}{summary.total_pnl_percentage.toFixed(2)}%)
        </p>
      </div>
    </div>
  );
}
