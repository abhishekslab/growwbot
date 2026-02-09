"use client";

import { useState } from "react";

interface Trade {
  id: number;
  symbol: string;
  trade_type: string;
  entry_price: number;
  stop_loss: number;
  target: number;
  quantity: number;
  capital_used: number;
  risk_amount: number;
  status: string;
  exit_price: number | null;
  actual_pnl: number | null;
  actual_fees: number | null;
  entry_date: string;
  exit_date: string | null;
  notes: string;
}

type SortKey = "symbol" | "entry_date" | "entry_price" | "quantity" | "status" | "actual_pnl";

const fmt = (n: number) =>
  "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const statusBadge: Record<string, string> = {
  OPEN: "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300",
  WON: "bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300",
  LOST: "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300",
  CLOSED: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
};

interface Props {
  trades: Trade[];
  onClose: (trade: Trade) => void;
  onDelete: (id: number) => void;
}

export default function TradeHistoryTable({ trades, onClose, onDelete }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("entry_date");
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = [...trades].sort((a, b) => {
    const aVal = a[sortKey];
    const bVal = b[sortKey];
    if (aVal === null && bVal === null) return 0;
    if (aVal === null) return 1;
    if (bVal === null) return -1;
    if (typeof aVal === "string" && typeof bVal === "string") {
      return sortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    }
    return sortAsc ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
  });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else {
      setSortKey(key);
      setSortAsc(key === "symbol");
    }
  };

  const columns: { key: SortKey; label: string }[] = [
    { key: "symbol", label: "Symbol" },
    { key: "entry_date", label: "Date" },
    { key: "entry_price", label: "Entry" },
    { key: "quantity", label: "Qty" },
    { key: "status", label: "Status" },
    { key: "actual_pnl", label: "P&L" },
  ];

  if (trades.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 text-center dark:border-gray-800 dark:bg-gray-900">
        <p className="text-gray-500 dark:text-gray-400">
          No trades yet. Go to Daily Picks and click a symbol to plan your first trade.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-800">
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className="cursor-pointer px-4 py-3 text-left font-medium text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
              >
                {col.label}
                {sortKey === col.key && (sortAsc ? " ▲" : " ▼")}
              </th>
            ))}
            <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">
              Target / SL
            </th>
            <th className="px-4 py-3 text-right font-medium text-gray-500 dark:text-gray-400">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((t) => (
            <tr
              key={t.id}
              className="border-b border-gray-100 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800/50"
            >
              <td className="px-4 py-3">
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {t.symbol}
                </span>
                <span className="ml-2 text-xs text-gray-400">{t.trade_type}</span>
              </td>
              <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                {new Date(t.entry_date).toLocaleDateString("en-IN")}
              </td>
              <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                {fmt(t.entry_price)}
              </td>
              <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{t.quantity}</td>
              <td className="px-4 py-3">
                <span
                  className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                    statusBadge[t.status] || statusBadge.CLOSED
                  }`}
                >
                  {t.status}
                </span>
              </td>
              <td className="px-4 py-3">
                {t.actual_pnl !== null ? (
                  <span
                    className={`font-medium ${
                      t.actual_pnl >= 0 ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    {t.actual_pnl >= 0 ? "+" : ""}
                    {fmt(t.actual_pnl)}
                  </span>
                ) : (
                  <span className="text-gray-400">—</span>
                )}
              </td>
              <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                T: {fmt(t.target)} / SL: {fmt(t.stop_loss)}
              </td>
              <td className="px-4 py-3 text-right">
                <div className="flex justify-end gap-2">
                  {t.status === "OPEN" && (
                    <button
                      onClick={() => onClose(t)}
                      className="rounded-lg bg-amber-100 px-3 py-1 text-xs font-medium text-amber-700 hover:bg-amber-200 dark:bg-amber-900/50 dark:text-amber-300 dark:hover:bg-amber-900"
                    >
                      Close
                    </button>
                  )}
                  <button
                    onClick={() => onDelete(t.id)}
                    className="rounded-lg bg-red-100 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-200 dark:bg-red-900/50 dark:text-red-300 dark:hover:bg-red-900"
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
