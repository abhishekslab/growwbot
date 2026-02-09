"use client";

import { OrderPayload } from "@/types/symbol";

interface Props {
  order: OrderPayload;
  loading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function OrderConfirmDialog({ order, loading, onConfirm, onCancel }: Props) {
  const isBuy = order.transaction_type === "BUY";
  const estValue = order.quantity * (order.price || 0);

  const rows: [string, string][] = [
    ["Symbol", order.trading_symbol],
    ["Transaction", order.transaction_type],
    ["Product", order.product],
    ["Order Type", order.order_type],
    ["Quantity", String(order.quantity)],
  ];
  if (order.order_type === "LIMIT" || order.order_type === "SL") {
    rows.push(["Price", "\u20B9" + order.price.toFixed(2)]);
  }
  if (order.trigger_price) {
    rows.push(["Trigger Price", "\u20B9" + order.trigger_price.toFixed(2)]);
  }
  rows.push(["Validity", order.validity]);
  if (estValue > 0) {
    rows.push([
      "Est. Value",
      "\u20B9" + estValue.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    ]);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-md rounded-xl border border-gray-200 bg-white p-6 shadow-xl dark:border-gray-700 dark:bg-gray-900">
        <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-gray-100">
          Confirm Order
        </h3>

        <table className="mb-4 w-full text-sm">
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label} className="border-b border-gray-100 dark:border-gray-800">
                <td className="py-2 text-gray-500 dark:text-gray-400">{label}</td>
                <td className="py-2 text-right font-medium text-gray-900 dark:text-gray-100">
                  {value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <p className="mb-5 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
          This will place a real order on your Groww account.
        </p>

        <div className="flex gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="flex-1 rounded-lg bg-gray-100 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 disabled:opacity-50 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`flex-1 rounded-lg py-2 text-sm font-semibold text-white disabled:opacity-50 ${
              isBuy ? "bg-green-600 hover:bg-green-700" : "bg-red-600 hover:bg-red-700"
            }`}
          >
            {loading ? (
              <span className="inline-flex items-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Placing...
              </span>
            ) : (
              `Confirm ${order.transaction_type}`
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
