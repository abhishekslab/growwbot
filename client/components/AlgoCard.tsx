"use client";

import { useState, useEffect, useCallback } from "react";
import ConfirmModal from "@/components/ConfirmModal";

interface AlgoInfo {
  algo_id: string;
  name: string;
  description: string;
  enabled: boolean;
  open_trades?: number;
  capital: number;
  risk_percent: number;
  compounding: boolean;
  effective_capital: number;
  compounding_pnl: number;
}

interface AlgoPerf {
  algo_id: string;
  total_trades: number;
  won: number;
  lost: number;
  win_rate: number;
  net_pnl: number;
}

interface AlgoCardProps {
  algo: AlgoInfo;
  perf?: AlgoPerf;
  onToggle: (algoId: string, enable: boolean) => void;
  onCapitalChange: (algoId: string, capital: number) => void;
  onCompoundingToggle: (algoId: string, compounding: boolean) => void;
}

type PendingAction =
  | { type: "toggle"; enable: boolean }
  | { type: "capital"; value: number }
  | { type: "compounding"; enable: boolean };

const fmt = (n: number) =>
  "\u20B9" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });

export default function AlgoCard({
  algo,
  perf,
  onToggle,
  onCapitalChange,
  onCompoundingToggle,
}: AlgoCardProps) {
  const [capitalInput, setCapitalInput] = useState(String(algo.capital));
  const [pending, setPending] = useState<PendingAction | null>(null);

  useEffect(() => {
    setCapitalInput(String(algo.capital));
  }, [algo.capital]);

  const handleCapitalBlur = () => {
    const val = parseFloat(capitalInput);
    if (!isNaN(val) && val > 0 && val !== algo.capital) {
      setPending({ type: "capital", value: val });
    } else {
      setCapitalInput(String(algo.capital));
    }
  };

  const handleConfirm = useCallback(() => {
    if (!pending) return;
    if (pending.type === "toggle") {
      onToggle(algo.algo_id, pending.enable);
    } else if (pending.type === "capital") {
      onCapitalChange(algo.algo_id, pending.value);
    } else if (pending.type === "compounding") {
      onCompoundingToggle(algo.algo_id, pending.enable);
    }
    setPending(null);
  }, [pending, algo.algo_id, onToggle, onCapitalChange, onCompoundingToggle]);

  const handleCancel = useCallback(() => {
    if (pending?.type === "capital") {
      setCapitalInput(String(algo.capital));
    }
    setPending(null);
  }, [pending, algo.capital]);

  // Build modal content based on pending action
  let modalTitle = "";
  let modalMessage = "";
  let modalDetail = "";
  let modalConfirmLabel = "";
  let modalColor: "red" | "green" | "blue" = "blue";

  if (pending?.type === "toggle") {
    if (pending.enable) {
      modalTitle = "Enable Algorithm";
      modalMessage = `This will start ${algo.name} with automatic trade execution.`;
      modalDetail = `Capital at risk: ${fmt(algo.capital)}`;
      modalConfirmLabel = "Enable";
      modalColor = "green";
    } else {
      modalTitle = "Disable Algorithm";
      modalMessage = `This will stop ${algo.name} from placing new trades.`;
      if ((algo.open_trades ?? 0) > 0) {
        modalDetail = `${algo.open_trades} open position${(algo.open_trades ?? 0) === 1 ? "" : "s"} will remain active until closed.`;
      }
      modalConfirmLabel = "Disable";
      modalColor = "red";
    }
  } else if (pending?.type === "capital") {
    const diff = pending.value - algo.capital;
    modalTitle = "Change Capital Allocation";
    modalMessage = `Update ${algo.name} capital from ${fmt(algo.capital)} to ${fmt(pending.value)}.`;
    modalDetail = `${diff > 0 ? "Increase" : "Decrease"} of ${fmt(Math.abs(diff))}. This affects position sizing for all future trades.`;
    modalConfirmLabel = "Update Capital";
    modalColor = "blue";
  } else if (pending?.type === "compounding") {
    if (pending.enable) {
      modalTitle = "Enable Compounding";
      modalMessage = `Profits from ${algo.name} will increase capital available for future trades.`;
      modalDetail = `Base: ${fmt(algo.capital)}. Effective capital will grow with net profits (never drops below base).`;
      modalConfirmLabel = "Enable";
      modalColor = "blue";
    } else {
      modalTitle = "Disable Compounding";
      modalMessage = `${algo.name} will use fixed capital of ${fmt(algo.capital)} for all trades, ignoring accumulated profits.`;
      modalConfirmLabel = "Disable";
      modalColor = "red";
    }
  }

  return (
    <>
      <ConfirmModal
        open={pending !== null}
        title={modalTitle}
        message={modalMessage}
        detail={modalDetail || undefined}
        confirmLabel={modalConfirmLabel}
        confirmColor={modalColor}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />

      <div className="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
        {/* Header: Name + Toggle */}
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {algo.name}
            </h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {algo.description}
            </p>
          </div>
          <button
            role="switch"
            aria-checked={algo.enabled}
            onClick={() =>
              setPending({ type: "toggle", enable: !algo.enabled })
            }
            className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${
              algo.enabled ? "bg-green-500" : "bg-gray-300 dark:bg-gray-600"
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
                algo.enabled ? "translate-x-4" : "translate-x-0"
              }`}
            />
          </button>
        </div>

        {/* Stats row */}
        <div className="mt-4 grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">Trades</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {perf?.total_trades ?? 0}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Win Rate
            </p>
            <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {perf?.win_rate ?? 0}%
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Net P&L
            </p>
            <p
              className={`text-lg font-semibold ${
                (perf?.net_pnl ?? 0) >= 0
                  ? "text-green-600 dark:text-green-400"
                  : "text-red-600 dark:text-red-400"
              }`}
            >
              {(perf?.net_pnl ?? 0) >= 0 ? "+" : ""}
              {"\u20B9"}
              {(perf?.net_pnl ?? 0).toLocaleString("en-IN")}
            </p>
          </div>
        </div>

        {(algo.open_trades ?? 0) > 0 && (
          <p className="mt-3 text-xs text-blue-600 dark:text-blue-400">
            {algo.open_trades} open position
            {algo.open_trades === 1 ? "" : "s"}
          </p>
        )}

        {/* Capital & Compounding settings */}
        <div className="mt-4 border-t border-gray-100 pt-4 dark:border-gray-700">
          {/* Capital input */}
          <div className="flex items-center justify-between">
            <label className="text-xs text-gray-500 dark:text-gray-400">
              Capital
            </label>
            <div className="flex items-center gap-1">
              <span className="text-xs text-gray-400">{"\u20B9"}</span>
              <input
                type="number"
                value={capitalInput}
                onChange={(e) => setCapitalInput(e.target.value)}
                onBlur={handleCapitalBlur}
                onKeyDown={(e) => {
                  if (e.key === "Enter") e.currentTarget.blur();
                }}
                className="w-28 rounded border border-gray-200 bg-gray-50 px-2 py-1 text-right text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
                min="1"
                step="1000"
              />
            </div>
          </div>

          {/* Effective capital (shown when compounding is on) */}
          {algo.compounding && (
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xs text-gray-500 dark:text-gray-400">
                Effective
              </span>
              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {"\u20B9"}
                {algo.effective_capital.toLocaleString("en-IN")}
                {algo.compounding_pnl !== 0 && (
                  <span
                    className={`ml-1 text-xs ${
                      algo.compounding_pnl >= 0
                        ? "text-green-600 dark:text-green-400"
                        : "text-red-600 dark:text-red-400"
                    }`}
                  >
                    ({algo.compounding_pnl >= 0 ? "+" : ""}
                    {"\u20B9"}
                    {algo.compounding_pnl.toLocaleString("en-IN")})
                  </span>
                )}
              </span>
            </div>
          )}

          {/* Compounding toggle */}
          <div className="mt-3 flex items-center justify-between">
            <span className="text-xs text-gray-500 dark:text-gray-400">
              Compounding
            </span>
            <button
              role="switch"
              aria-checked={algo.compounding}
              onClick={() =>
                setPending({
                  type: "compounding",
                  enable: !algo.compounding,
                })
              }
              className={`relative h-5 w-9 rounded-full transition-colors ${
                algo.compounding
                  ? "bg-blue-500"
                  : "bg-gray-300 dark:bg-gray-600"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
                  algo.compounding ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
