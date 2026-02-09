"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { RankedPick } from "@/app/page";

type SortKey = "rank" | "symbol" | "ltp" | "day_change_pct" | "volume" | "turnover";

const columns: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: "rank", label: "#", numeric: true },
  { key: "symbol", label: "Symbol" },
  { key: "ltp", label: "LTP", numeric: true },
  { key: "day_change_pct", label: "Chg%", numeric: true },
  { key: "volume", label: "Vol", numeric: true },
  { key: "turnover", label: "Turnover", numeric: true },
];

const tierColors: Record<RankedPick["tier"], string> = {
  hc: "bg-amber-500",
  gainer: "bg-green-500",
  volume: "bg-blue-500",
  other: "bg-gray-400 dark:bg-gray-600",
};

const tierLabels: Record<RankedPick["tier"], string> = {
  hc: "High Conviction",
  gainer: "Gainer",
  volume: "Volume Leader",
  other: "",
};

function formatCompactIndian(val: number): string {
  if (val >= 1_00_00_000) return (val / 1_00_00_000).toFixed(1) + "Cr";
  if (val >= 1_00_000) return (val / 1_00_000).toFixed(1) + "L";
  if (val >= 1_000) return (val / 1_000).toFixed(1) + "K";
  return val.toLocaleString("en-IN");
}

interface Props {
  results: RankedPick[];
  stage: string;
  flashSymbols?: Set<string>;
}

export default function DailyPicksTable({ results, stage, flashSymbols }: Props) {
  const router = useRouter();
  const [sortKey, setSortKey] = useState<SortKey>("rank");
  const [sortAsc, setSortAsc] = useState(true);

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
      setSortAsc(key === "symbol" || key === "rank");
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
                className="cursor-pointer px-3 py-2 text-left font-medium text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
              >
                {col.label}
                {sortKey === col.key && (sortAsc ? " ▲" : " ▼")}
              </th>
            ))}
            <th className="px-3 py-2 text-left font-medium text-gray-500 dark:text-gray-400">
              News
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const isOther = r.tier === "other";
            const isFlashing = flashSymbols?.has(r.symbol) ?? false;
            const isNeg = r.day_change_pct < 0;
            return (
              <tr
                key={r.symbol}
                onClick={() => router.push(`/symbol/${r.symbol}`)}
                className={`cursor-pointer border-b transition-all duration-300 ${
                  isOther
                    ? "border-gray-100 text-gray-500 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-500 dark:hover:bg-gray-800/50"
                    : "border-gray-100 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800/50"
                }`}
              >
                {/* Rank with tier dot */}
                <td className="px-3 py-2 tabular-nums">
                  <span className="flex items-center gap-1.5">
                    <span
                      className={`inline-block h-2 w-2 flex-shrink-0 rounded-full ${tierColors[r.tier]}`}
                      title={tierLabels[r.tier]}
                    />
                    <span className="text-gray-500 dark:text-gray-400">{r.rank}</span>
                  </span>
                </td>

                {/* Symbol */}
                <td className="px-3 py-2">
                  <span className={isOther ? "" : "font-medium text-blue-600 dark:text-blue-400"}>
                    {r.symbol}
                  </span>
                </td>

                {/* LTP */}
                <td
                  className={`px-3 py-2 tabular-nums transition-colors duration-500 ${
                    isFlashing ? "bg-yellow-100 dark:bg-yellow-900/30" : ""
                  } ${isOther ? "" : "text-gray-700 dark:text-gray-300"}`}
                >
                  {formatCurrency(r.ltp)}
                </td>

                {/* Chg% */}
                <td
                  className={`px-3 py-2 tabular-nums font-medium ${
                    isNeg
                      ? "text-red-600 dark:text-red-400"
                      : "text-green-600 dark:text-green-400"
                  }`}
                >
                  {isNeg ? "" : "+"}{r.day_change_pct.toFixed(2)}%
                </td>

                {/* Volume */}
                <td className={`px-3 py-2 tabular-nums ${isOther ? "" : "text-gray-700 dark:text-gray-300"}`}>
                  {!volumeEnriched || r.volume === 0 ? (
                    <span className="animate-pulse text-gray-400">&mdash;</span>
                  ) : (
                    formatCompactIndian(r.volume)
                  )}
                </td>

                {/* Turnover */}
                <td className={`px-3 py-2 tabular-nums ${isOther ? "" : "text-gray-700 dark:text-gray-300"}`}>
                  {!volumeEnriched || r.turnover === 0 ? (
                    <span className="animate-pulse text-gray-400">&mdash;</span>
                  ) : (
                    <>₹{formatCompactIndian(r.turnover)}</>
                  )}
                </td>

                {/* News icon */}
                <td className="px-3 py-2">
                  {!newsEnriched && volumeEnriched ? (
                    <span className="animate-pulse text-gray-400 text-xs">...</span>
                  ) : r.news_link ? (
                    <a
                      href={r.news_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={r.news_headline || "News"}
                      onClick={(e) => e.stopPropagation()}
                      className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-200"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        className="h-4 w-4"
                      >
                        <path
                          fillRule="evenodd"
                          d="M2 3.5A1.5 1.5 0 013.5 2h9A1.5 1.5 0 0114 3.5v11.75A2.75 2.75 0 0016.75 18h-12A2.75 2.75 0 012 15.25V3.5zm3.75 7a.75.75 0 000 1.5h4.5a.75.75 0 000-1.5h-4.5zm0 3a.75.75 0 000 1.5h4.5a.75.75 0 000-1.5h-4.5zM5 5.75A.75.75 0 015.75 5h4.5a.75.75 0 01.75.75v2.5a.75.75 0 01-.75.75h-4.5A.75.75 0 015 8.25v-2.5z"
                          clipRule="evenodd"
                        />
                        <path d="M16.5 6.5h-1v8.75a1.25 1.25 0 102.5 0V8a1.5 1.5 0 00-1.5-1.5z" />
                      </svg>
                    </a>
                  ) : (
                    <span className="text-gray-300 dark:text-gray-700">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        className="h-4 w-4"
                      >
                        <path
                          fillRule="evenodd"
                          d="M2 3.5A1.5 1.5 0 013.5 2h9A1.5 1.5 0 0114 3.5v11.75A2.75 2.75 0 0016.75 18h-12A2.75 2.75 0 012 15.25V3.5zm3.75 7a.75.75 0 000 1.5h4.5a.75.75 0 000-1.5h-4.5zm0 3a.75.75 0 000 1.5h4.5a.75.75 0 000-1.5h-4.5zM5 5.75A.75.75 0 015.75 5h4.5a.75.75 0 01.75.75v2.5a.75.75 0 01-.75.75h-4.5A.75.75 0 015 8.25v-2.5z"
                          clipRule="evenodd"
                        />
                        <path d="M16.5 6.5h-1v8.75a1.25 1.25 0 102.5 0V8a1.5 1.5 0 00-1.5-1.5z" />
                      </svg>
                    </span>
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
