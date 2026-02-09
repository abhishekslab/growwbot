"use client";

interface Meta {
  total_instruments_scanned?: number;
  candidates_after_price_filter?: number;
  candidates_volume_enriched?: number;
  passes_gainer_criteria?: number;
  passes_volume_leader_criteria?: number;
  high_conviction_count?: number;
  fno_eligible_universe?: number;
  scan_time_seconds?: number;
  cache_active?: boolean;
  scan_timestamp?: string;
}

export default function DailyPicksMeta({ meta, stage }: { meta: Meta; stage: string }) {
  const cards = [
    {
      label: "Instruments Scanned",
      value: meta.total_instruments_scanned?.toLocaleString("en-IN") ?? "—",
    },
    {
      label: "Candidates Enriched",
      value: meta.candidates_volume_enriched?.toString() ?? (stage === "done" ? "0" : "—"),
    },
    {
      label: "High Conviction",
      value: meta.high_conviction_count?.toString() ?? (stage === "done" ? "0" : "—"),
      highlight: true,
    },
    {
      label: "FnO Universe",
      value: meta.fno_eligible_universe?.toLocaleString("en-IN") ?? "—",
    },
    {
      label: "Scan Time",
      value: meta.scan_time_seconds != null ? `${meta.scan_time_seconds}s` : "Scanning...",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {cards.map((card) => (
        <div
          key={card.label}
          className={`rounded-xl border p-6 shadow-sm ${
            card.highlight
              ? "border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950"
              : "border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900"
          }`}
        >
          <p className="text-sm text-gray-500 dark:text-gray-400">{card.label}</p>
          <p
            className={`mt-1 text-2xl font-bold ${
              card.highlight
                ? "text-amber-700 dark:text-amber-300"
                : "text-gray-900 dark:text-gray-100"
            }`}
          >
            {card.value}
          </p>
        </div>
      ))}
    </div>
  );
}
