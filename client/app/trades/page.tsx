"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import TradeStatsBar from "@/components/TradeStatsBar";
import ActivePositionsTable, { ActiveTrade } from "@/components/ActivePositionsTable";
import TradeHistoryTable from "@/components/TradeHistoryTable";
import TradeAnalyticsDashboard from "@/components/TradeAnalyticsDashboard";
import SellConfirmDialog from "@/components/SellConfirmDialog";
import GoalProgressBar from "@/components/GoalProgressBar";
import { useTradeSettings, useCompoundedCapital } from "@/hooks/useTradeSettings";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Trade {
  id: number;
  symbol: string;
  trade_type: string;
  entry_price: number;
  stop_loss: number;
  target: number;
  quantity: number;
  capital_used: number;
  risk_amount: number;
  status: string;
  exit_price: number | null;
  actual_pnl: number | null;
  actual_fees: number | null;
  entry_date: string;
  exit_date: string | null;
  notes: string;
}

interface Summary {
  total_trades: number;
  open_trades: number;
  won: number;
  lost: number;
  closed: number;
  win_rate: number;
  net_pnl: number;
  total_fees: number;
}

export default function TradesPage() {
  const { capital, targetCapital, autoCompound, paperMode, loaded } = useTradeSettings();
  const { realizedPnl } = useCompoundedCapital(capital, autoCompound, paperMode);
  const [activeTrades, setActiveTrades] = useState<ActiveTrade[]>([]);
  const [historyTrades, setHistoryTrades] = useState<Trade[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [flashSymbols, setFlashSymbols] = useState<Set<string>>(new Set());
  const [sellingTrade, setSellingTrade] = useState<ActiveTrade | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const prevLtpRef = useRef<Record<string, number>>({});

  const fetchHistory = useCallback(() => {
    const paperParam = `is_paper=${paperMode}`;
    Promise.all([
      fetch(`${API_URL}/api/trades?${paperParam}`).then((r) => r.json()),
      fetch(`${API_URL}/api/trades/summary?${paperParam}`).then((r) => r.json()),
    ])
      .then(([tradeList, sum]) => {
        // Filter out OPEN trades — only show closed in history
        setHistoryTrades(tradeList.filter((t: Trade) => t.status !== "OPEN"));
        setSummary(sum);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [paperMode]);

  // Clear stale data when paperMode changes (or on initial load)
  useEffect(() => {
    if (!loaded) return;
    setActiveTrades([]);
    setHistoryTrades([]);
    setSummary(null);
    setLoading(true);
  }, [loaded, paperMode]);

  // Poll active trades every 5s
  useEffect(() => {
    if (!loaded) return;
    const poll = () => {
      fetch(`${API_URL}/api/trades/active?is_paper=${paperMode}`)
        .then((r) => r.json())
        .then((newTrades: ActiveTrade[]) => {
          // Flash detection
          const prevLtp = prevLtpRef.current;
          const changed = new Set<string>();
          for (const t of newTrades) {
            if (prevLtp[t.symbol] && prevLtp[t.symbol] !== t.current_ltp) {
              changed.add(t.symbol);
            }
            prevLtp[t.symbol] = t.current_ltp;
          }
          if (changed.size > 0) {
            setFlashSymbols(changed);
            setTimeout(() => setFlashSymbols(new Set()), 500);
          }

          setActiveTrades(newTrades);
        })
        .catch(() => {});
    };

    poll();
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, [loaded, paperMode]);

  // Initial fetch for history + summary
  useEffect(() => {
    if (!loaded) return;
    fetchHistory();
  }, [loaded, fetchHistory]);

  // Toast auto-dismiss
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(timer);
  }, [toast]);

  const handleSell = async (tradeId: number) => {
    const res = await fetch(`${API_URL}/api/trades/${tradeId}/close`, {
      method: "POST",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Sell failed" }));
      throw new Error(err.detail || "Sell failed");
    }

    // Optimistically remove from active list
    setActiveTrades((prev) => prev.filter((t) => t.id !== tradeId));
    setSellingTrade(null);
    setToast({ message: "Sell order placed successfully", type: "success" });

    // Refetch history and summary
    fetchHistory();
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Trades</h1>

      {paperMode && (
        <div className="mt-2 rounded-lg border border-orange-300 bg-orange-50 px-4 py-2 text-sm font-medium text-orange-800 dark:border-orange-700 dark:bg-orange-950 dark:text-orange-200">
          Viewing paper trades
        </div>
      )}

      {/* Goal Progress */}
      {targetCapital > capital && (
        <div className="mt-4">
          <GoalProgressBar
            baseCapital={capital}
            realizedPnl={realizedPnl}
            targetCapital={targetCapital}
          />
        </div>
      )}

      {/* Stats Bar */}
      <div className="mt-4">
        {summary && <TradeStatsBar summary={summary} paperMode={paperMode} />}
      </div>

      {/* Active Positions */}
      <div className="mt-6">
        <h2 className="mb-3 text-lg font-semibold text-gray-900 dark:text-gray-100">
          Active Positions
        </h2>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600" />
          </div>
        ) : (
          <ActivePositionsTable
            trades={activeTrades}
            flashSymbols={flashSymbols}
            onSell={(t) => setSellingTrade(t)}
          />
        )}
      </div>

      {/* Trade History */}
      <div className="mt-8">
        <TradeHistoryTable trades={historyTrades} />
      </div>

      {/* Trade Analytics */}
      <div className="mt-8">
        <TradeAnalyticsDashboard paperMode={paperMode} />
      </div>

      {/* Sell Confirm Dialog */}
      {sellingTrade && (
        <SellConfirmDialog
          trade={sellingTrade}
          onConfirm={handleSell}
          onCancel={() => setSellingTrade(null)}
        />
      )}

      {/* Toast */}
      {toast && (
        <div
          className={`fixed right-4 bottom-4 z-50 rounded-lg px-4 py-2 text-sm font-medium text-white shadow-lg ${
            toast.type === "success" ? "bg-green-600" : "bg-red-600"
          }`}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}
