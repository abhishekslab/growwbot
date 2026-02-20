"use client";

const fmt = (n: number) =>
  "₹" + Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export interface ActiveTrade {
  id: number;
  symbol: string;
  trade_type: string;
  entry_price: number;
  stop_loss: number;
  target: number;
  quantity: number;
  capital_used: number;
  current_ltp: number;
  unrealized_pnl: number;
  distance_to_target_pct: number;
  distance_to_sl_pct: number;
  is_paper?: number;
}

interface Props {
  trades: ActiveTrade[];
  flashSymbols: Set<string>;
  onSell: (trade: ActiveTrade) => void;
}

export default function ActivePositionsTable({ trades, flashSymbols, onSell }: Props) {
  if (trades.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white px-4 py-6 text-center dark:border-gray-800 dark:bg-gray-900">
        <p className="text-sm text-gray-500 dark:text-gray-400">No active positions</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-800">
            <th className="px-3 py-2 text-left font-medium text-gray-500 dark:text-gray-400">
              Symbol
            </th>
            <th className="px-3 py-2 text-right font-medium text-gray-500 dark:text-gray-400">
              Entry
            </th>
            <th className="px-3 py-2 text-right font-medium text-gray-500 dark:text-gray-400">
              LTP
            </th>
            <th className="px-3 py-2 text-right font-medium text-gray-500 dark:text-gray-400">
              Qty
            </th>
            <th className="px-3 py-2 text-right font-medium text-gray-500 dark:text-gray-400">
              Capital
            </th>
            <th className="px-3 py-2 text-right font-medium text-gray-500 dark:text-gray-400">
              Target
            </th>
            <th className="px-3 py-2 text-right font-medium text-gray-500 dark:text-gray-400">
              SL
            </th>
            <th className="px-3 py-2 text-right font-medium text-gray-500 dark:text-gray-400">
              Unrealized P&L
            </th>
            <th className="px-3 py-2 text-right font-medium text-gray-500 dark:text-gray-400"></th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => {
            const isUp = t.current_ltp >= t.entry_price;
            const isFlashing = flashSymbols.has(t.symbol);

            return (
              <tr
                key={t.id}
                className={`border-b border-gray-100 transition-colors duration-500 dark:border-gray-800 ${
                  isFlashing
                    ? isUp
                      ? "bg-green-50 dark:bg-green-900/20"
                      : "bg-red-50 dark:bg-red-900/20"
                    : "hover:bg-gray-50 dark:hover:bg-gray-800/50"
                }`}
              >
                <td className="px-3 py-2">
                  <span className="font-medium text-gray-900 dark:text-gray-100">{t.symbol}</span>
                  <span className="ml-1.5 text-xs text-gray-400">{t.trade_type}</span>
                  {t.is_paper ? (
                    <span className="ml-1.5 rounded-full bg-orange-100 px-1.5 py-0.5 text-[10px] font-semibold text-orange-700 dark:bg-orange-900/50 dark:text-orange-300">
                      PAPER
                    </span>
                  ) : null}
                </td>
                <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">
                  {fmt(t.entry_price)}
                </td>
                <td className="px-3 py-2 text-right">
                  <span className="font-semibold text-gray-900 dark:text-gray-100">
                    {t.current_ltp > 0 ? fmt(t.current_ltp) : "—"}
                  </span>
                  {t.current_ltp > 0 && (
                    <span className={`ml-1 text-xs ${isUp ? "text-green-600" : "text-red-600"}`}>
                      {isUp ? "▲" : "▼"}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">
                  {t.quantity}
                </td>
                <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">
                  {fmt(t.capital_used)}
                </td>
                <td className="px-3 py-2 text-right">
                  <span className="text-gray-700 dark:text-gray-300">{fmt(t.target)}</span>
                  <span className="ml-1 text-xs text-green-600 dark:text-green-400">
                    (+{t.distance_to_target_pct}%)
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  <span className="text-gray-700 dark:text-gray-300">{fmt(t.stop_loss)}</span>
                  <span className="ml-1 text-xs text-red-600 dark:text-red-400">
                    (-{Math.abs(t.distance_to_sl_pct)}%)
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  <span
                    className={`font-semibold ${
                      t.unrealized_pnl >= 0
                        ? "text-green-600 dark:text-green-400"
                        : "text-red-600 dark:text-red-400"
                    }`}
                  >
                    {t.unrealized_pnl >= 0 ? "+" : "-"}
                    {fmt(t.unrealized_pnl)}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() => onSell(t)}
                    className="rounded-lg bg-green-600 px-3 py-1 text-xs font-semibold text-white hover:bg-green-700"
                  >
                    Sell
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
