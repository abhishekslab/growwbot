"use client";

import { useState } from "react";

interface Holding {
  symbol: string;
  quantity: number;
  average_price: number;
  ltp: number;
  current_value: number;
  invested_value: number;
  pnl: number;
  pnl_percentage: number;
}

type SortKey = keyof Holding;

export default function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("symbol");
  const [sortAsc, setSortAsc] = useState(true);

  const sorted = [...holdings].sort((a, b) => {
    const aVal = a[sortKey];
    const bVal = b[sortKey];
    if (typeof aVal === "string" && typeof bVal === "string") {
      return sortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    }
    return sortAsc ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
  });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  const formatCurrency = (val: number) =>
    "₹" + val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const columns: { key: SortKey; label: string }[] = [
    { key: "symbol", label: "Symbol" },
    { key: "quantity", label: "Qty" },
    { key: "average_price", label: "Avg Price" },
    { key: "ltp", label: "LTP" },
    { key: "current_value", label: "Current Value" },
    { key: "pnl", label: "P&L" },
    { key: "pnl_percentage", label: "P&L %" },
  ];

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
          </tr>
        </thead>
        <tbody>
          {sorted.map((h) => (
            <tr
              key={h.symbol}
              className="border-b border-gray-100 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800/50"
            >
              <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{h.symbol}</td>
              <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{h.quantity}</td>
              <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{formatCurrency(h.average_price)}</td>
              <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{formatCurrency(h.ltp)}</td>
              <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{formatCurrency(h.current_value)}</td>
              <td className={`px-4 py-3 font-medium ${h.pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                {formatCurrency(h.pnl)}
              </td>
              <td className={`px-4 py-3 font-medium ${h.pnl_percentage >= 0 ? "text-green-600" : "text-red-600"}`}>
                {h.pnl_percentage >= 0 ? "+" : ""}{h.pnl_percentage.toFixed(2)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
