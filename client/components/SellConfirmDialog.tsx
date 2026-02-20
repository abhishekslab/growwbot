"use client";

import { useState } from "react";

const fmt = (n: number) =>
  "₹" + Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

interface Trade {
  id: number;
  symbol: string;
  quantity: number;
  current_ltp: number;
  is_paper?: number;
}

interface Props {
  trade: Trade;
  onConfirm: (tradeId: number) => Promise<void>;
  onCancel: () => void;
}

export default function SellConfirmDialog({ trade, onConfirm, onCancel }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleConfirm = async () => {
    setLoading(true);
    setError("");
    try {
      await onConfirm(trade.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sell order failed");
      setLoading(false);
    }
  };

  const proceeds = trade.current_ltp * trade.quantity;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl dark:bg-gray-900">
        <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">
          {trade.is_paper
            ? `Close paper position — ${trade.quantity} shares of ${trade.symbol}?`
            : `Sell ${trade.quantity} shares of ${trade.symbol} at market?`}
        </h3>

        <div className="mt-4 space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Current LTP</span>
            <span className="font-medium text-gray-900 dark:text-gray-100">
              {fmt(trade.current_ltp)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Estimated proceeds</span>
            <span className="font-medium text-gray-900 dark:text-gray-100">{fmt(proceeds)}</span>
          </div>
        </div>

        {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}

        <div className="mt-5 flex gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="flex-1 rounded-lg border border-gray-300 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={loading}
            className="flex-1 rounded-lg bg-green-600 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50"
          >
            {loading ? "Closing..." : trade.is_paper ? "Close Paper Position" : "Confirm Sell"}
          </button>
        </div>
      </div>
    </div>
  );
}
