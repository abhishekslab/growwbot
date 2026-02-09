"use client";

import { useState, useMemo } from "react";
import { calculatePositionSize, PositionResult } from "@/lib/tradeCalculator";
import { FeeConfig } from "@/lib/feeDefaults";
import TradeSettingsBar from "./TradeSettingsBar";
import FeeBreakdownTable from "./FeeBreakdownTable";
import TradeOutcomeCards from "./TradeOutcomeCards";

const fmt = (n: number) =>
  "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

interface Props {
  symbol: string;
  ltp: number;
  capital: number;
  riskPercent: number;
  feeConfig: FeeConfig;
  onCapitalChange: (v: number) => void;
  onRiskChange: (v: number) => void;
  onEnterTrade: (trade: {
    symbol: string;
    tradeType: string;
    entryPrice: number;
    stopLoss: number;
    target: number;
    quantity: number;
    capitalUsed: number;
    riskAmount: number;
    feesEntry: number;
    feesExitTarget: number;
    feesExitSL: number;
  }) => void;
  entering?: boolean;
}

export default function TradeCalculator({
  symbol,
  ltp,
  capital,
  riskPercent,
  feeConfig,
  onCapitalChange,
  onRiskChange,
  onEnterTrade,
  entering = false,
}: Props) {
  const [entryPrice, setEntryPrice] = useState(ltp);
  const [slOffset, setSlOffset] = useState(2); // % below entry
  const [tradeType, setTradeType] = useState<"INTRADAY" | "DELIVERY">("INTRADAY");

  // Keep entry price synced if user hasn't changed it
  const [priceEdited, setPriceEdited] = useState(false);
  const displayEntry = priceEdited ? entryPrice : ltp;

  const stopLoss = Math.round((displayEntry * (1 - slOffset / 100)) * 100) / 100;

  const result: PositionResult = useMemo(
    () =>
      calculatePositionSize(
        capital,
        riskPercent,
        displayEntry,
        stopLoss,
        tradeType,
        feeConfig
      ),
    [capital, riskPercent, displayEntry, stopLoss, tradeType, feeConfig]
  );

  const handleEnterTrade = () => {
    if (result.quantity <= 0) return;
    onEnterTrade({
      symbol,
      tradeType,
      entryPrice: displayEntry,
      stopLoss,
      target: result.target,
      quantity: result.quantity,
      capitalUsed: result.capitalUsed,
      riskAmount: result.riskAmount,
      feesEntry: result.feesEntry.total,
      feesExitTarget: result.feesExitTarget.total,
      feesExitSL: result.feesExitSL.total,
    });
  };

  return (
    <div className="space-y-6">
      <TradeSettingsBar
        capital={capital}
        riskPercent={riskPercent}
        tradeType={tradeType}
        onCapitalChange={onCapitalChange}
        onRiskChange={onRiskChange}
        onTradeTypeChange={setTradeType}
      />

      {/* Price inputs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
            Entry Price
          </label>
          <input
            type="number"
            step="0.05"
            value={displayEntry}
            onChange={(e) => {
              setPriceEdited(true);
              setEntryPrice(Number(e.target.value));
            }}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-lg font-semibold dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
          />
          {priceEdited && (
            <button
              onClick={() => setPriceEdited(false)}
              className="mt-1 text-xs text-blue-600 hover:underline dark:text-blue-400"
            >
              Reset to LTP ({fmt(ltp)})
            </button>
          )}
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
            Stop-Loss Offset
          </label>
          <div className="flex items-center gap-2">
            <input
              type="range"
              min="0.5"
              max="10"
              step="0.5"
              value={slOffset}
              onChange={(e) => setSlOffset(Number(e.target.value))}
              className="flex-1"
            />
            <span className="w-12 text-right text-sm font-medium text-gray-700 dark:text-gray-300">
              {slOffset}%
            </span>
          </div>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            SL: {fmt(stopLoss)}
          </p>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
            Target (1:2 RR)
          </label>
          <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {fmt(result.target)}
          </p>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            +{((result.target / displayEntry - 1) * 100).toFixed(1)}% from entry
          </p>
        </div>
      </div>

      {/* Position summary */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Quantity" value={result.quantity.toString()} />
        <StatCard label="Capital Used" value={fmt(result.capitalUsed)} />
        <StatCard label="Risk Amount" value={fmt(result.riskAmount)} />
        <StatCard
          label="Risk/Reward"
          value={result.riskAmount > 0 ? "1:2" : "—"}
        />
      </div>

      {/* Fee breakdowns */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FeeBreakdownTable label="Entry Fees (Buy)" fees={result.feesEntry} />
        <FeeBreakdownTable label="Exit Fees (Sell at Target)" fees={result.feesExitTarget} />
      </div>

      {/* Outcome cards */}
      <TradeOutcomeCards
        netProfitIfTarget={result.netProfitIfTarget}
        netLossIfSL={result.netLossIfSL}
        target={result.target}
        stopLoss={stopLoss}
        feesTotalTarget={result.feesEntry.total + result.feesExitTarget.total}
        feesTotalSL={result.feesEntry.total + result.feesExitSL.total}
      />

      {/* Enter trade button */}
      <button
        onClick={handleEnterTrade}
        disabled={result.quantity <= 0 || entering}
        className="w-full rounded-xl bg-blue-600 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {entering
          ? "Entering Trade..."
          : `Enter Trade — ${result.quantity} shares of ${symbol}`}
      </button>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400">{label}</p>
      <p className="mt-1 text-lg font-bold text-gray-900 dark:text-gray-100">{value}</p>
    </div>
  );
}
