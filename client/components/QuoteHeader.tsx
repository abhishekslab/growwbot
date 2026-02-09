"use client";

import { Quote } from "@/types/symbol";

interface Props {
  quote: Quote | null;
  liveLtp: number | null;
}

export default function QuoteHeader({ quote, liveLtp }: Props) {
  const ltp = liveLtp ?? quote?.ltp ?? 0;
  const prevClose = quote?.prev_close ?? 0;
  const change = prevClose ? ltp - prevClose : quote?.change ?? 0;
  const changePct = prevClose ? (change / prevClose) * 100 : quote?.change_pct ?? 0;
  const positive = change >= 0;

  const fmt = (val: number) =>
    "\u20B9" + val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const stats = [
    { label: "Open", value: quote?.open },
    { label: "High", value: quote?.high },
    { label: "Low", value: quote?.low },
    { label: "Prev Close", value: quote?.prev_close },
    { label: "Volume", value: quote?.volume },
  ];

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <div className="flex flex-wrap items-baseline gap-4">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          {quote?.symbol ?? "—"}
        </h1>
        <span
          key={ltp}
          className="animate-pulse text-3xl font-semibold text-gray-900 dark:text-gray-100"
        >
          {fmt(ltp)}
        </span>
        <span
          className={`text-lg font-medium ${positive ? "text-green-600" : "text-red-600"}`}
        >
          {positive ? "+" : ""}
          {fmt(change)} ({positive ? "+" : ""}
          {changePct.toFixed(2)}%)
        </span>
      </div>

      <div className="mt-4 flex flex-wrap gap-6 text-sm text-gray-600 dark:text-gray-400">
        {stats.map((s) => (
          <div key={s.label}>
            <span className="font-medium text-gray-500 dark:text-gray-500">{s.label}: </span>
            <span className="text-gray-900 dark:text-gray-200">
              {s.label === "Volume"
                ? (s.value ?? 0).toLocaleString("en-IN")
                : fmt(s.value ?? 0)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
