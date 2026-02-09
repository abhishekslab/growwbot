"use client";

const fmt = (n: number) =>
  "₹" + Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

interface Props {
  netProfitIfTarget: number;
  netLossIfSL: number;
  target: number;
  stopLoss: number;
  feesTotalTarget: number;
  feesTotalSL: number;
}

export default function TradeOutcomeCards({
  netProfitIfTarget,
  netLossIfSL,
  target,
  stopLoss,
  feesTotalTarget,
  feesTotalSL,
}: Props) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div className="rounded-xl border border-green-200 bg-green-50 p-5 dark:border-green-800 dark:bg-green-950/40">
        <h4 className="text-sm font-semibold text-green-800 dark:text-green-300">
          If Target Hit ({fmt(target)})
        </h4>
        <p className="mt-2 text-2xl font-bold text-green-700 dark:text-green-400">
          +{fmt(netProfitIfTarget)}
        </p>
        <p className="mt-1 text-xs text-green-600 dark:text-green-500">
          After fees of {fmt(feesTotalTarget)}
        </p>
      </div>

      <div className="rounded-xl border border-red-200 bg-red-50 p-5 dark:border-red-800 dark:bg-red-950/40">
        <h4 className="text-sm font-semibold text-red-800 dark:text-red-300">
          If Stop-Loss Hit ({fmt(stopLoss)})
        </h4>
        <p className="mt-2 text-2xl font-bold text-red-700 dark:text-red-400">
          -{fmt(Math.abs(netLossIfSL))}
        </p>
        <p className="mt-1 text-xs text-red-600 dark:text-red-500">
          Including fees of {fmt(feesTotalSL)}
        </p>
      </div>
    </div>
  );
}
