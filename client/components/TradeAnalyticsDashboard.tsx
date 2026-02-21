"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AnalyticsRow {
  total: number;
  won: number;
  win_pct: number;
  avg_pnl: number;
}

interface Analytics {
  by_confidence: (AnalyticsRow & { confidence: string })[];
  by_verdict: (AnalyticsRow & { verdict: string })[];
  by_trend: (AnalyticsRow & { trend: string })[];
  by_exit_trigger: { trigger: string; total: number }[];
  overreach_stats: { total: number; won: number; win_pct: number };
}

const fmt = (n: number) =>
  "₹" + Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function WinRateTable<T extends AnalyticsRow>({
  title,
  rows,
  labelKey,
}: {
  title: string;
  rows: T[];
  labelKey: keyof T;
}) {
  if (rows.length === 0) return null;
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-gray-800 dark:text-gray-200">{title}</h3>
      <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800">
              <th className="px-3 py-1.5 text-left font-medium text-gray-500 dark:text-gray-400">
                {title.replace("Win Rate by ", "")}
              </th>
              <th className="px-3 py-1.5 text-right font-medium text-gray-500 dark:text-gray-400">
                Trades
              </th>
              <th className="px-3 py-1.5 text-right font-medium text-gray-500 dark:text-gray-400">
                Won
              </th>
              <th className="px-3 py-1.5 text-right font-medium text-gray-500 dark:text-gray-400">
                Win %
              </th>
              <th className="px-3 py-1.5 text-right font-medium text-gray-500 dark:text-gray-400">
                Avg P&L
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={String(r[labelKey])}
                className="border-b border-gray-100 dark:border-gray-700/50"
              >
                <td className="px-3 py-1.5 font-medium text-gray-900 dark:text-gray-100">
                  {String(r[labelKey] as unknown)}
                </td>
                <td className="px-3 py-1.5 text-right text-gray-600 dark:text-gray-400">
                  {r.total}
                </td>
                <td className="px-3 py-1.5 text-right text-gray-600 dark:text-gray-400">{r.won}</td>
                <td className="px-3 py-1.5 text-right">
                  <span
                    className={`font-medium ${r.win_pct >= 50 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
                  >
                    {r.win_pct}%
                  </span>
                </td>
                <td className="px-3 py-1.5 text-right">
                  <span
                    className={`font-medium ${r.avg_pnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
                  >
                    {r.avg_pnl >= 0 ? "+" : "-"}
                    {fmt(r.avg_pnl)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function generateInsight(data: Analytics): string | null {
  // Find the worst trend
  const worstTrend = data.by_trend.reduce<(AnalyticsRow & { trend: string }) | null>((worst, r) => {
    if (r.total >= 2 && (!worst || r.win_pct < worst.win_pct)) return r;
    return worst;
  }, null);

  if (worstTrend && worstTrend.win_pct < 40) {
    return `You lose ${(100 - worstTrend.win_pct).toFixed(0)}% of trades in ${worstTrend.trend} trends (${worstTrend.total} trades).`;
  }

  // Find the worst confidence level
  const worstConf = data.by_confidence.reduce<(AnalyticsRow & { confidence: string }) | null>(
    (worst, r) => {
      if (r.total >= 2 && (!worst || r.win_pct < worst.win_pct)) return r;
      return worst;
    },
    null,
  );

  if (worstConf && worstConf.win_pct < 40) {
    return `${worstConf.confidence} confidence trades win only ${worstConf.win_pct}% of the time. Consider filtering these out.`;
  }

  // Overreach
  if (data.overreach_stats.total >= 2 && data.overreach_stats.win_pct < 30) {
    return `Trades with overreach warnings win only ${data.overreach_stats.win_pct}% — set more realistic targets.`;
  }

  return null;
}

export default function TradeAnalyticsDashboard({ paperMode }: { paperMode: boolean }) {
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/api/trades/analytics?is_paper=${paperMode}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        setData(d?.analytics || d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [paperMode]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
      </div>
    );
  }

  if (!data) return null;

  const hasData =
    data.by_confidence.length > 0 ||
    data.by_trend.length > 0 ||
    data.by_verdict.length > 0 ||
    data.by_exit_trigger.length > 0;

  if (!hasData) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6 text-center dark:border-gray-800 dark:bg-gray-900">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No analytics yet. Close some trades with entry snapshots to see learning insights.
        </p>
      </div>
    );
  }

  const insight = generateInsight(data);
  const totalExits = data.by_exit_trigger.reduce((s, r) => s + r.total, 0);

  const triggerColors: Record<string, string> = {
    TARGET: "bg-green-500",
    SL: "bg-red-500",
    MANUAL: "bg-gray-400",
    UNKNOWN: "bg-gray-300",
  };

  return (
    <div className="space-y-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Trade Analytics</h2>

      {/* Key insight */}
      {insight && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm text-blue-800 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200">
          {insight}
        </div>
      )}

      {/* Exit trigger distribution */}
      {data.by_exit_trigger.length > 0 && totalExits > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-gray-800 dark:text-gray-200">
            Exit Distribution
          </h3>
          <div className="flex h-4 w-full overflow-hidden rounded-full">
            {data.by_exit_trigger.map((r) => (
              <div
                key={r.trigger}
                className={`${triggerColors[r.trigger] || triggerColors.UNKNOWN}`}
                style={{ width: `${(r.total / totalExits) * 100}%` }}
                title={`${r.trigger}: ${r.total} (${Math.round((r.total / totalExits) * 100)}%)`}
              />
            ))}
          </div>
          <div className="mt-1.5 flex gap-4 text-xs text-gray-500 dark:text-gray-400">
            {data.by_exit_trigger.map((r) => (
              <span key={r.trigger} className="flex items-center gap-1">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${triggerColors[r.trigger] || triggerColors.UNKNOWN}`}
                />
                {r.trigger} {Math.round((r.total / totalExits) * 100)}%
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Win rate tables */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <WinRateTable
          title="Win Rate by Confidence"
          rows={data.by_confidence}
          labelKey="confidence"
        />
        <WinRateTable title="Win Rate by Trend" rows={data.by_trend} labelKey="trend" />
        <WinRateTable title="Win Rate by Verdict" rows={data.by_verdict} labelKey="verdict" />
      </div>

      {/* Overreach stats */}
      {data.overreach_stats.total > 0 && (
        <div className="rounded-lg border border-orange-200 bg-orange-50 px-4 py-2.5 text-xs dark:border-orange-800 dark:bg-orange-950">
          <span className="font-semibold text-orange-800 dark:text-orange-200">
            Overreach trades:
          </span>{" "}
          <span className="text-orange-700 dark:text-orange-300">
            {data.overreach_stats.total} trades with target warnings —{" "}
            {data.overreach_stats.win_pct}% win rate
          </span>
        </div>
      )}
    </div>
  );
}
