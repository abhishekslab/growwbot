"use client";

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

interface AlgoPerformanceTableProps {
  data: AlgoPerf[];
  algoNames: Record<string, string>;
}

export default function AlgoPerformanceTable({
  data,
  algoNames,
}: AlgoPerformanceTableProps) {
  if (data.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
        No closed trades yet. Performance data will appear after algo trades are completed.
      </div>
    );
  }

  const fmt = (n: number) =>
    (n >= 0 ? "+" : "") + "\u20B9" + n.toLocaleString("en-IN");

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
        <thead className="bg-gray-50 dark:bg-gray-800">
          <tr>
            {[
              "Algorithm",
              "Version",
              "Trades",
              "Won",
              "Lost",
              "Win %",
              "Net P&L",
              "Avg Profit",
              "Avg Loss",
              "Fees",
              "Worst",
            ].map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500 dark:text-gray-400"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white dark:divide-gray-700 dark:bg-gray-900">
          {data.map((row) => (
            <tr key={row.algo_id}>
              <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">
                {algoNames[row.algo_id] || row.algo_id}
              </td>
              <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                {row.algo_version ? `v${row.algo_version}` : "-"}
              </td>
              <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                {row.total_trades}
              </td>
              <td className="px-4 py-3 text-sm text-green-600 dark:text-green-400">
                {row.won}
              </td>
              <td className="px-4 py-3 text-sm text-red-600 dark:text-red-400">
                {row.lost}
              </td>
              <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                {row.win_rate}%
              </td>
              <td
                className={`px-4 py-3 text-sm font-medium ${
                  row.net_pnl >= 0
                    ? "text-green-600 dark:text-green-400"
                    : "text-red-600 dark:text-red-400"
                }`}
              >
                {fmt(row.net_pnl)}
              </td>
              <td className="px-4 py-3 text-sm text-green-600 dark:text-green-400">
                {row.avg_profit ? fmt(row.avg_profit) : "-"}
              </td>
              <td className="px-4 py-3 text-sm text-red-600 dark:text-red-400">
                {row.avg_loss ? fmt(row.avg_loss) : "-"}
              </td>
              <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                {"\u20B9"}{row.total_fees.toLocaleString("en-IN")}
              </td>
              <td className="px-4 py-3 text-sm text-red-600 dark:text-red-400">
                {row.worst_trade ? fmt(row.worst_trade) : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
