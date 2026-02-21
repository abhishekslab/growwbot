"use client";

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

export default function BacktestTradeTable({ trades }: { trades: BacktestTrade[] }) {
  if (!trades.length) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-gray-100">
          Simulated Trades
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">No trades in this backtest.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <h3 className="border-b border-gray-200 p-4 text-lg font-semibold text-gray-900 dark:border-gray-800 dark:text-gray-100">
        Simulated Trades
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-800/50">
              <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Entry</th>
              <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Exit</th>
              <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Qty</th>
              <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">P&L</th>
              <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Fees</th>
              <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Trigger</th>
              <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Duration</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t, i) => {
              const durationSec = t.exit_time - t.entry_time;
              const durationStr =
                durationSec >= 3600
                  ? `${(durationSec / 3600).toFixed(1)}h`
                  : `${Math.round(durationSec / 60)}m`;
              return (
                <tr
                  key={i}
                  className="border-b border-gray-100 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800/30"
                >
                  <td className="px-4 py-2 text-gray-900 dark:text-gray-100">
                    ₹{t.entry_price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-2 text-gray-900 dark:text-gray-100">
                    ₹{t.exit_price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{t.quantity}</td>
                  <td
                    className={`px-4 py-2 font-medium ${
                      t.pnl >= 0
                        ? "text-green-600 dark:text-green-400"
                        : "text-red-600 dark:text-red-400"
                    }`}
                  >
                    ₹{t.pnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-2 text-gray-600 dark:text-gray-400">
                    ₹{t.fees.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{t.exit_trigger}</td>
                  <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{durationStr}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
