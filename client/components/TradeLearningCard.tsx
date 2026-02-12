"use client";

import { useMemo } from "react";

interface EntrySnapshot {
  verdict: string;
  score: number;
  confidence: string;
  trend: string;
  rsi: number;
  rsiZone: string;
  volumeRatio: number;
  volumeConfirmed: boolean;
  vwap: number;
  aboveVwap: boolean;
  atr: number;
  patterns: string[];
  reasons: string[];
  dayChangePct: number;
  sessionHigh: number;
  entryPrice: number;
  target: number;
  stopLoss: number;
  warnings: string[];
  warningDetails: string[];
}

interface Trade {
  id: number;
  entry_price: number;
  exit_price: number | null;
  actual_pnl: number | null;
  status: string;
  entry_date: string;
  exit_date: string | null;
  exit_trigger?: string;
  entry_snapshot?: string;
}

const fmt = (n: number) =>
  "₹" + Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const verdictColors: Record<string, string> = {
  BUY: "bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300",
  WAIT: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/50 dark:text-yellow-300",
  AVOID: "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300",
};

const confidenceColors: Record<string, string> = {
  HIGH: "text-green-600 dark:text-green-400",
  MEDIUM: "text-yellow-600 dark:text-yellow-400",
  LOW: "text-red-600 dark:text-red-400",
};

export default function TradeLearningCard({ trade }: { trade: Trade }) {
  const snapshot: EntrySnapshot | null = useMemo(() => {
    if (!trade.entry_snapshot) return null;
    try {
      return JSON.parse(trade.entry_snapshot);
    } catch {
      return null;
    }
  }, [trade.entry_snapshot]);

  if (!snapshot) {
    return (
      <div className="px-4 py-3 text-xs text-gray-400 dark:text-gray-500">
        No analysis data recorded for this trade.
      </div>
    );
  }

  const pnl = trade.actual_pnl ?? 0;
  const won = trade.status === "WON";
  const lost = trade.status === "LOST";

  // Generate insights
  const insights: string[] = [];

  // Signal strength vs result
  if (snapshot.confidence === "HIGH" && won) {
    insights.push("Strong signal confirmed — high confidence entry worked.");
  } else if (snapshot.confidence === "HIGH" && lost) {
    insights.push("High confidence signal failed — review market conditions.");
  } else if (snapshot.confidence === "LOW" && lost) {
    insights.push("Weak signal, weak outcome. Consider waiting for stronger setups.");
  } else if (snapshot.confidence === "LOW" && won) {
    insights.push("Won despite low confidence — might have been lucky.");
  }

  // Warning accuracy
  if (snapshot.warnings.length > 0 && lost) {
    insights.push(
      `Had ${snapshot.warnings.length} warning(s) at entry — and it didn't work out.`
    );
  }
  if (snapshot.warnings.includes("TARGET_ABOVE_SESSION_HIGH") && lost) {
    insights.push("Target was above session high — price couldn't break through.");
  }

  // Volume confirmation
  if (!snapshot.volumeConfirmed && lost) {
    insights.push("Entered without volume confirmation — consider requiring 2x+ volume.");
  }

  // Trend alignment
  if (snapshot.trend === "BEARISH" && snapshot.verdict === "BUY" && lost) {
    insights.push("Bought against a bearish trend — avoid counter-trend entries.");
  }

  // Duration
  let durationStr = "";
  if (trade.entry_date && trade.exit_date) {
    const diffMs = new Date(trade.exit_date).getTime() - new Date(trade.entry_date).getTime();
    const hours = Math.floor(diffMs / 3600000);
    const mins = Math.floor((diffMs % 3600000) / 60000);
    if (hours > 24) {
      durationStr = `${Math.floor(hours / 24)}d ${hours % 24}h`;
    } else if (hours > 0) {
      durationStr = `${hours}h ${mins}m`;
    } else {
      durationStr = `${mins}m`;
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 px-4 py-3 sm:grid-cols-3">
      {/* Why I Entered */}
      <div>
        <h4 className="mb-2 text-xs font-semibold text-gray-700 dark:text-gray-300">
          Why I Entered
        </h4>
        <div className="space-y-1.5 text-xs">
          <div className="flex items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${verdictColors[snapshot.verdict] || verdictColors.WAIT}`}>
              {snapshot.verdict}
            </span>
            <span className="text-gray-600 dark:text-gray-400">
              Score {snapshot.score > 0 ? "+" : ""}{snapshot.score}
            </span>
            <span className={`font-medium ${confidenceColors[snapshot.confidence] || ""}`}>
              {snapshot.confidence}
            </span>
          </div>
          <div className="flex justify-between text-gray-600 dark:text-gray-400">
            <span>Trend</span>
            <span className={snapshot.trend === "BULLISH" ? "text-green-600 dark:text-green-400" : snapshot.trend === "BEARISH" ? "text-red-600 dark:text-red-400" : ""}>
              {snapshot.trend}
            </span>
          </div>
          <div className="flex justify-between text-gray-600 dark:text-gray-400">
            <span>RSI</span>
            <span>{snapshot.rsi} ({snapshot.rsiZone})</span>
          </div>
          <div className="flex justify-between text-gray-600 dark:text-gray-400">
            <span>Volume</span>
            <span>{snapshot.volumeRatio}x {snapshot.volumeConfirmed ? "✓" : ""}</span>
          </div>
          {snapshot.vwap > 0 && (
            <div className="flex justify-between text-gray-600 dark:text-gray-400">
              <span>VWAP</span>
              <span>{snapshot.aboveVwap ? "Above" : "Below"} {fmt(snapshot.vwap)}</span>
            </div>
          )}
          {snapshot.patterns.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1">
              {snapshot.patterns.map((p, i) => (
                <span key={i} className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] dark:bg-gray-700">
                  {p}
                </span>
              ))}
            </div>
          )}
          {snapshot.dayChangePct !== 0 && (
            <div className="flex justify-between text-gray-600 dark:text-gray-400">
              <span>Day change at entry</span>
              <span className={snapshot.dayChangePct >= 0 ? "text-green-600" : "text-red-600"}>
                {snapshot.dayChangePct >= 0 ? "+" : ""}{snapshot.dayChangePct.toFixed(1)}%
              </span>
            </div>
          )}
          {snapshot.warnings.length > 0 && (
            <div className="mt-1 space-y-0.5">
              {snapshot.warningDetails.map((w, i) => (
                <div key={i} className="text-[10px] text-orange-600 dark:text-orange-400">
                  ⚠ {w}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* What Happened */}
      <div>
        <h4 className="mb-2 text-xs font-semibold text-gray-700 dark:text-gray-300">
          What Happened
        </h4>
        <div className="space-y-1.5 text-xs">
          <div className="flex justify-between text-gray-600 dark:text-gray-400">
            <span>Entry</span>
            <span>{fmt(trade.entry_price)}</span>
          </div>
          {trade.exit_price !== null && (
            <div className="flex justify-between text-gray-600 dark:text-gray-400">
              <span>Exit</span>
              <span>{fmt(trade.exit_price)}</span>
            </div>
          )}
          {trade.exit_trigger && (
            <div className="flex justify-between text-gray-600 dark:text-gray-400">
              <span>Exit Trigger</span>
              <span className={`font-medium ${
                trade.exit_trigger === "TARGET" ? "text-green-600 dark:text-green-400"
                  : trade.exit_trigger === "SL" ? "text-red-600 dark:text-red-400"
                    : "text-gray-600 dark:text-gray-400"
              }`}>
                {trade.exit_trigger}
              </span>
            </div>
          )}
          {durationStr && (
            <div className="flex justify-between text-gray-600 dark:text-gray-400">
              <span>Duration</span>
              <span>{durationStr}</span>
            </div>
          )}
          <div className="flex justify-between border-t border-gray-100 pt-1.5 dark:border-gray-700">
            <span className="text-gray-600 dark:text-gray-400">Net P&L</span>
            <span className={`font-semibold ${pnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
              {pnl >= 0 ? "+" : "-"}{fmt(pnl)}
            </span>
          </div>
        </div>
      </div>

      {/* Insights */}
      <div>
        <h4 className="mb-2 text-xs font-semibold text-gray-700 dark:text-gray-300">
          Insights
        </h4>
        {insights.length > 0 ? (
          <ul className="space-y-1.5 text-xs text-gray-600 dark:text-gray-400">
            {insights.map((insight, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="mt-0.5 text-[10px] text-blue-500">●</span>
                <span>{insight}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-gray-400 dark:text-gray-500">
            Not enough data for insights yet.
          </p>
        )}
      </div>
    </div>
  );
}
