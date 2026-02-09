"use client";

interface Meta {
  total_instruments_scanned: number;
  after_price_filter: number;
  after_volume_filter: number;
  after_news_filter: number;
  scan_time_seconds: number;
  float_filter_available: boolean;
}

export default function ScreenerMeta({ meta }: { meta: Meta }) {
  const cards = [
    { label: "Instruments Scanned", value: meta.total_instruments_scanned.toLocaleString("en-IN") },
    { label: "After Price Filter", value: meta.after_price_filter.toString() },
    { label: "After Volume Filter", value: meta.after_volume_filter.toString() },
    { label: "Final Results", value: meta.after_news_filter.toString() },
    { label: "Scan Time", value: `${meta.scan_time_seconds}s` },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900"
        >
          <p className="text-sm text-gray-500 dark:text-gray-400">{card.label}</p>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">
            {card.value}
          </p>
        </div>
      ))}
    </div>
  );
}
