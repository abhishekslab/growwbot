"use client";

import { useState, useMemo } from "react";
import { calculateTradeExit } from "@/lib/tradeCalculator";
import { DEFAULT_FEE_CONFIG } from "@/lib/feeDefaults";

interface Trade {
  id: number;
  symbol: string;
  trade_type: string;
  entry_price: number;
  quantity: number;
  target: number;
  stop_loss: number;
}

interface Props {
  trade: Trade;
  onConfirm: (data: {
    id: number;
    exitPrice: number;
    actualPnl: number;
    actualFees: number;
    status: string;
  }) => void;
  onCancel: () => void;
}

const fmt = (n: number) =>
  "₹" + Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function CloseTradeModal({ trade, onConfirm, onCancel }: Props) {
  const [exitPrice, setExitPrice] = useState(trade.target);

  const exitResult = useMemo(
    () =>
      calculateTradeExit(
        trade.entry_price,
        exitPrice,
        trade.quantity,
        trade.trade_type as "INTRADAY" | "DELIVERY",
        DEFAULT_FEE_CONFIG
      ),
    [trade, exitPrice]
  );

  const status =
    exitResult.netPnl > 0 ? "WON" : exitResult.netPnl < 0 ? "LOST" : "CLOSED";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-gray-900">
        <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">
          Close Trade — {trade.symbol}
        </h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Entry: {fmt(trade.entry_price)} | Qty: {trade.quantity}
        </p>

        <div className="mt-4">
          <label className="mb-1 block text-sm font-medium text-gray-600 dark:text-gray-400">
            Exit Price
          </label>
          <input
            type="number"
            step="0.05"
            value={exitPrice}
            onChange={(e) => setExitPrice(Number(e.target.value))}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-lg font-semibold dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
          />
        </div>

        <div className="mt-4 space-y-2 rounded-lg border border-gray-200 p-3 dark:border-gray-800">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 dark:text-gray-400">Gross P&L</span>
            <span
              className={
                exitResult.grossPnl >= 0 ? "text-green-600" : "text-red-600"
              }
            >
              {exitResult.grossPnl >= 0 ? "+" : "-"}
              {fmt(exitResult.grossPnl)}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 dark:text-gray-400">Total Fees</span>
            <span className="text-gray-700 dark:text-gray-300">
              {fmt(exitResult.totalFees)}
            </span>
          </div>
          <div className="flex justify-between border-t border-gray-200 pt-2 text-sm font-semibold dark:border-gray-800">
            <span className="text-gray-900 dark:text-gray-100">Net P&L</span>
            <span
              className={
                exitResult.netPnl >= 0
                  ? "text-green-600 dark:text-green-400"
                  : "text-red-600 dark:text-red-400"
              }
            >
              {exitResult.netPnl >= 0 ? "+" : "-"}
              {fmt(exitResult.netPnl)}
            </span>
          </div>
        </div>

        <div className="mt-5 flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 rounded-lg border border-gray-300 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={() =>
              onConfirm({
                id: trade.id,
                exitPrice,
                actualPnl: exitResult.netPnl,
                actualFees: exitResult.totalFees,
                status,
              })
            }
            className={`flex-1 rounded-lg py-2 text-sm font-semibold text-white ${
              exitResult.netPnl >= 0
                ? "bg-green-600 hover:bg-green-700"
                : "bg-red-600 hover:bg-red-700"
            }`}
          >
            Close as {status}
          </button>
        </div>
      </div>
    </div>
  );
}
