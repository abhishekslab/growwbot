"use client";

import { FeeBreakdown } from "@/lib/tradeCalculator";

interface Props {
  label: string;
  fees: FeeBreakdown;
}

const fmt = (n: number) =>
  "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const rows: { key: keyof FeeBreakdown; label: string }[] = [
  { key: "brokerage", label: "Brokerage" },
  { key: "stt", label: "STT" },
  { key: "exchangeTxn", label: "Exchange Txn" },
  { key: "sebi", label: "SEBI Fee" },
  { key: "stampDuty", label: "Stamp Duty" },
  { key: "gst", label: "GST (18%)" },
];

export default function FeeBreakdownTable({ label, fees }: Props) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-800">
      <div className="border-b border-gray-200 bg-gray-50 px-4 py-2 dark:border-gray-800 dark:bg-gray-800/50">
        <h4 className="text-xs font-semibold tracking-wide text-gray-500 uppercase dark:text-gray-400">
          {label}
        </h4>
      </div>
      <div className="divide-y divide-gray-100 dark:divide-gray-800">
        {rows.map((r) => (
          <div key={r.key} className="flex justify-between px-4 py-1.5 text-sm">
            <span className="text-gray-600 dark:text-gray-400">{r.label}</span>
            <span className="text-gray-900 dark:text-gray-200">{fmt(fees[r.key])}</span>
          </div>
        ))}
        <div className="flex justify-between px-4 py-2 text-sm font-semibold">
          <span className="text-gray-900 dark:text-gray-100">Total</span>
          <span className="text-gray-900 dark:text-gray-100">{fmt(fees.total)}</span>
        </div>
      </div>
    </div>
  );
}
