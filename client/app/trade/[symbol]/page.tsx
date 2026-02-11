"use client";

import { useEffect, useState, useCallback, use } from "react";
import { useRouter } from "next/navigation";
import TradeCalculator from "@/components/TradeCalculator";
import { useTradeSettings } from "@/hooks/useTradeSettings";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function TradePage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol } = use(params);
  const router = useRouter();
  const { capital, riskPercent, feeConfig, rrRatio, loaded, setCapital, setRiskPercent, setRrRatio, paperMode } =
    useTradeSettings();
  const [ltp, setLtp] = useState(0);
  const [ltpLoading, setLtpLoading] = useState(true);
  const [ltpError, setLtpError] = useState<string | null>(null);
  const [entering, setEntering] = useState(false);

  const fetchLtp = useCallback(() => {
    fetch(`${API_URL}/api/ltp/${symbol}`)
      .then((res) => {
        if (!res.ok) return res.json().then((e) => Promise.reject(e));
        return res.json();
      })
      .then((data) => {
        setLtp(data.ltp);
        setLtpLoading(false);
        setLtpError(null);
      })
      .catch((err) => {
        setLtpError(err?.detail || "Failed to fetch LTP");
        setLtpLoading(false);
      });
  }, [symbol]);

  useEffect(() => {
    fetchLtp();
    const interval = setInterval(fetchLtp, 5000);
    return () => clearInterval(interval);
  }, [fetchLtp]);

  const handleEnterTrade = async (trade: {
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
  }) => {
    setEntering(true);
    try {
      const res = await fetch(`${API_URL}/api/trades`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: trade.symbol,
          trade_type: trade.tradeType,
          entry_price: trade.entryPrice,
          stop_loss: trade.stopLoss,
          target: trade.target,
          quantity: trade.quantity,
          capital_used: trade.capitalUsed,
          risk_amount: trade.riskAmount,
          fees_entry: trade.feesEntry,
          fees_exit_target: trade.feesExitTarget,
          fees_exit_sl: trade.feesExitSL,
          is_paper: paperMode,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create trade");
      }
      router.push("/trades");
    } catch {
      setEntering(false);
    }
  };

  if (!loaded) return null;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            &larr; Back
          </button>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {symbol}
          </h1>
          {ltp > 0 && (
            <span className="rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300">
              LTP: ₹{ltp.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </span>
          )}
        </div>
      </header>

      {ltpLoading && ltp === 0 && (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600" />
          <span className="ml-3 text-gray-500">Fetching live price...</span>
        </div>
      )}

      {ltpError && ltp === 0 && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-800 dark:bg-red-950">
          <p className="text-red-600 dark:text-red-400">{ltpError}</p>
          <button
            onClick={fetchLtp}
            className="mt-3 rounded-lg bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      )}

      {ltp > 0 && (
        <TradeCalculator
          symbol={symbol}
          ltp={ltp}
          capital={capital}
          riskPercent={riskPercent}
          feeConfig={feeConfig}
          rrRatio={rrRatio}
          onCapitalChange={setCapital}
          onRiskChange={setRiskPercent}
          onRrRatioChange={setRrRatio}
          onEnterTrade={handleEnterTrade}
          entering={entering}
        />
      )}
    </div>
  );
}
