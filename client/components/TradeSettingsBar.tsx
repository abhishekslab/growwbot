"use client";

interface Props {
  capital: number;
  riskPercent: number;
  tradeType: "INTRADAY" | "DELIVERY";
  rrRatio: number;
  onCapitalChange: (v: number) => void;
  onRiskChange: (v: number) => void;
  onTradeTypeChange: (v: "INTRADAY" | "DELIVERY") => void;
  onRrRatioChange: (v: number) => void;
  smallCapitalMode?: boolean;
  onSmallCapitalModeChange?: (v: boolean) => void;
  autoCompound?: boolean;
  onAutoCompoundChange?: (v: boolean) => void;
  paperMode?: boolean;
  onPaperModeChange?: (v: boolean) => void;
}

const RR_OPTIONS = [1.5, 2, 2.5, 3];

export default function TradeSettingsBar({
  capital,
  riskPercent,
  tradeType,
  rrRatio,
  onCapitalChange,
  onRiskChange,
  onTradeTypeChange,
  onRrRatioChange,
  smallCapitalMode = false,
  onSmallCapitalModeChange,
  autoCompound = false,
  onAutoCompoundChange,
  paperMode = false,
  onPaperModeChange,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-600 dark:text-gray-400">Capital</label>
        <div className="relative">
          <span className="absolute top-1/2 left-3 -translate-y-1/2 text-sm text-gray-400">₹</span>
          <input
            type="number"
            value={capital}
            onChange={(e) => onCapitalChange(Number(e.target.value))}
            className="w-36 rounded-lg border border-gray-300 bg-white py-1.5 pr-3 pl-7 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-600 dark:text-gray-400">Risk</label>
        <div className="relative">
          <input
            type="number"
            step="0.1"
            min="0.1"
            max="10"
            value={riskPercent}
            onChange={(e) => onRiskChange(Number(e.target.value))}
            className="w-20 rounded-lg border border-gray-300 bg-white py-1.5 pr-7 pl-3 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
          />
          <span className="absolute top-1/2 right-3 -translate-y-1/2 text-sm text-gray-400">%</span>
        </div>
      </div>

      <div className="flex items-center gap-1 rounded-lg border border-gray-300 dark:border-gray-700">
        <button
          onClick={() => onTradeTypeChange("INTRADAY")}
          className={`rounded-l-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            tradeType === "INTRADAY"
              ? "bg-blue-600 text-white"
              : "bg-white text-gray-600 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
          }`}
        >
          Intraday
        </button>
        <button
          onClick={() => onTradeTypeChange("DELIVERY")}
          className={`rounded-r-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            tradeType === "DELIVERY"
              ? "bg-blue-600 text-white"
              : "bg-white text-gray-600 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
          }`}
        >
          Delivery
        </button>
      </div>

      {/* R:R Ratio */}
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-600 dark:text-gray-400">R:R</label>
        <div className="flex items-center gap-1 rounded-lg border border-gray-300 dark:border-gray-700">
          {RR_OPTIONS.map((opt, i) => (
            <button
              key={opt}
              onClick={() => onRrRatioChange(opt)}
              className={`px-2.5 py-1.5 text-sm font-medium transition-colors ${
                i === 0 ? "rounded-l-lg" : ""
              } ${i === RR_OPTIONS.length - 1 ? "rounded-r-lg" : ""} ${
                rrRatio === opt
                  ? "bg-blue-600 text-white"
                  : "bg-white text-gray-600 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
              }`}
            >
              1:{opt}
            </button>
          ))}
        </div>
      </div>

      {/* Small Capital Mode toggle */}
      {onSmallCapitalModeChange && (
        <button
          onClick={() => onSmallCapitalModeChange(!smallCapitalMode)}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            smallCapitalMode
              ? "bg-amber-500 text-white"
              : "border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
          }`}
        >
          Small Cap
        </button>
      )}

      {/* Auto-Compound toggle */}
      {onAutoCompoundChange && (
        <button
          onClick={() => onAutoCompoundChange(!autoCompound)}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            autoCompound
              ? "bg-purple-600 text-white"
              : "border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
          }`}
        >
          Auto-Compound
        </button>
      )}

      {/* Paper Mode toggle */}
      {onPaperModeChange && (
        <button
          onClick={() => onPaperModeChange(!paperMode)}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            paperMode
              ? "bg-orange-500 text-white"
              : "border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
          }`}
        >
          Paper
        </button>
      )}
    </div>
  );
}
