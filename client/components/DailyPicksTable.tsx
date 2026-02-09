"use client";

import { useState } from "react";
import Link from "next/link";

interface DailyPick {
  symbol: string;
  name: string;
  ltp: number;
  open: number;
  day_change_pct: number;
  volume: number;
  turnover: number;
  fno_eligible: boolean;
  meets_gainer_criteria: boolean;
  meets_volume_leader_criteria: boolean;
  high_conviction: boolean;
  news_headline: string;
  news_link: string;
}

type SortKey = "symbol" | "name" | "ltp" | "day_change_pct" | "volume" | "turnover";

const columns: { key: SortKey; label: string }[] = [
  { key: "symbol", label: "Symbol" },
  { key: "name", label: "Name" },
  { key: "ltp", label: "LTP" },
  { key: "day_change_pct", label: "Day Change %" },
  { key: "volume", label: "Volume" },
  { key: "turnover", label: "Turnover" },
];

function formatCompactIndian(val: number): string {
  if (val >= 1_00_00_000) return (val / 1_00_00_000).toFixed(1) + "Cr";
  if (val >= 1_00_000) return (val / 1_00_000).toFixed(1) + "L";
  if (val >= 1_000) return (val / 1_000).toFixed(1) + "K";
  return val.toLocaleString("en-IN");
}

interface Props {
  results: DailyPick[];
  criteriaKey: keyof DailyPick;
  stage: string;
  flashSymbols?: Set<string>;
}

export default function DailyPicksTable({ results, criteriaKey, stage, flashSymbols }: Props) {
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

  // Volume/turnover not yet enriched during ohlc stage
  const volumeEnriched = stage !== "ohlc" && stage !== "starting";
  // News not yet enriched during ohlc/volume stages
  const newsEnriched = stage === "done";

  if (results.length === 0) {
    return (
      <div className="rounded-xl border border-blue-200 bg-blue-50 p-6 text-center dark:border-blue-800 dark:bg-blue-950">
        <p className="text-blue-800 dark:text-blue-200">
          No stocks found. Try refreshing during market hours.
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
              News
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const passes = Boolean(r[criteriaKey]);
            const isFlashing = flashSymbols?.has(r.symbol) ?? false;
            return (
              <tr
                key={r.symbol}
                className={`transition-all duration-300 ${
                  passes
                    ? "border-b border-gray-100 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800/50"
                    : "border-b border-red-200 bg-red-50/60 hover:bg-red-100/60 dark:border-red-900 dark:bg-red-950/40 dark:hover:bg-red-950/60"
                }`}
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/symbol/${r.symbol}`}
                    className={passes ? "font-medium text-blue-600 hover:underline dark:text-blue-400" : "font-medium text-red-800 hover:text-blue-600 dark:text-red-300 dark:hover:text-blue-400"}
                  >
                    {r.symbol}
                  </Link>
                  {r.fno_eligible && (
                    <span className="ml-2 inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/50 dark:text-green-400">
                      F&O
                    </span>
                  )}
                  {r.high_conviction && (
                    <span className="ml-1 inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/50 dark:text-amber-400">
                      HC
                    </span>
                  )}
                </td>
                <td className={`px-4 py-3 ${passes ? "text-gray-700 dark:text-gray-300" : "text-red-700 dark:text-red-400"}`}>
                  {r.name}
                </td>
                <td
                  className={`px-4 py-3 transition-colors duration-500 ${
                    isFlashing
                      ? "bg-yellow-100 dark:bg-yellow-900/30"
                      : ""
                  } ${passes ? "text-gray-700 dark:text-gray-300" : "text-red-700 dark:text-red-400"}`}
                >
                  {formatCurrency(r.ltp)}
                </td>
                <td className={`px-4 py-3 font-medium ${passes ? "text-green-600" : "text-red-600 dark:text-red-400"}`}>
                  +{r.day_change_pct.toFixed(2)}%
                </td>
                <td className={`px-4 py-3 ${passes ? "text-gray-700 dark:text-gray-300" : "text-red-700 dark:text-red-400"}`}>
                  {!volumeEnriched || r.volume === 0 ? (
                    <span className="animate-pulse text-gray-400">&mdash;</span>
                  ) : (
                    formatCompactIndian(r.volume)
                  )}
                </td>
                <td className={`px-4 py-3 ${passes ? "text-gray-700 dark:text-gray-300" : "text-red-700 dark:text-red-400"}`}>
                  {!volumeEnriched || r.turnover === 0 ? (
                    <span className="animate-pulse text-gray-400">&mdash;</span>
                  ) : (
                    <>₹{formatCompactIndian(r.turnover)}</>
                  )}
                </td>
                <td className="max-w-xs truncate px-4 py-3">
                  {!newsEnriched && volumeEnriched ? (
                    <span className="animate-pulse text-gray-400 text-xs">Loading...</span>
                  ) : r.news_link ? (
                    <a
                      href={r.news_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline dark:text-blue-400"
                    >
                      {r.news_headline || "Link"}
                    </a>
                  ) : (
                    <span className="text-gray-400">&mdash;</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
