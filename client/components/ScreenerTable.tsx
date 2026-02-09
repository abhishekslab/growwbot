"use client";

import { useState } from "react";

interface ScreenerResult {
  symbol: string;
  name: string;
  ltp: number;
  open: number;
  day_change_pct: number;
  volume: number;
  avg_volume: number;
  relative_volume: number;
  float_shares: number | null;
  news_headline: string;
  news_link: string;
}

type SortKey = "symbol" | "name" | "ltp" | "day_change_pct" | "volume" | "relative_volume";

const columns: { key: SortKey; label: string }[] = [
  { key: "symbol", label: "Symbol" },
  { key: "name", label: "Name" },
  { key: "ltp", label: "LTP" },
  { key: "day_change_pct", label: "Day Change %" },
  { key: "volume", label: "Volume" },
  { key: "relative_volume", label: "Rel Volume" },
];

export default function ScreenerTable({ results }: { results: ScreenerResult[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("day_change_pct");
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = [...results].sort((a, b) => {
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
      setSortAsc(key === "symbol" || key === "name");
    }
  };

  const formatCurrency = (val: number) =>
    "₹" + val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const formatVolume = (val: number) => val.toLocaleString("en-IN");

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
              Float
            </th>
            <th className="px-4 py-3 text-left font-medium text-gray-500 dark:text-gray-400">
              News
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr
              key={r.symbol}
              className="border-b border-gray-100 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800/50"
            >
              <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                {r.symbol}
              </td>
              <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                {r.name}
              </td>
              <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                {formatCurrency(r.ltp)}
              </td>
              <td className="px-4 py-3 font-medium text-green-600">
                +{r.day_change_pct.toFixed(2)}%
              </td>
              <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                {formatVolume(r.volume)}
              </td>
              <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">
                {r.relative_volume.toFixed(1)}x
              </td>
              <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                {r.float_shares != null
                  ? (r.float_shares / 1_000_000).toFixed(1) + "M"
                  : "N/A"}
              </td>
              <td className="max-w-xs truncate px-4 py-3">
                {r.news_link ? (
                  <a
                    href={r.news_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline dark:text-blue-400"
                  >
                    {r.news_headline || "Link"}
                  </a>
                ) : (
                  <span className="text-gray-400">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
