"use client";

interface Props {
  baseCapital: number;
  realizedPnl: number;
  targetCapital: number;
}

export default function GoalProgressBar({ baseCapital, realizedPnl, targetCapital }: Props) {
  const gap = targetCapital - baseCapital;
  if (gap <= 0) return null;

  const progress = Math.max(0, Math.min(100, (realizedPnl / gap) * 100));
  const currentCapital = baseCapital + realizedPnl;
  const fmt = (n: number) =>
    "\u20B9" + n.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <div className="mb-2 flex items-center justify-between text-xs">
        <span className="text-gray-500 dark:text-gray-400">
          {fmt(baseCapital)}
        </span>
        <span className="font-medium text-gray-700 dark:text-gray-300">
          Goal: {fmt(targetCapital)}
        </span>
      </div>
      <div className="relative h-3 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className="h-full rounded-full bg-gradient-to-r from-blue-500 via-green-500 to-emerald-500 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="mt-2 flex items-center justify-between text-xs">
        <span className={`font-medium ${realizedPnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
          Current: {fmt(currentCapital)} ({realizedPnl >= 0 ? "+" : ""}{fmt(realizedPnl)})
        </span>
        <span className="text-gray-400 dark:text-gray-500">
          {progress.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}
