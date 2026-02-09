"use client";

import { useEffect, useState, useCallback } from "react";
import TradeSummaryCards from "@/components/TradeSummaryCards";
import TradeHistoryTable from "@/components/TradeHistoryTable";
import CloseTradeModal from "@/components/CloseTradeModal";

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

type StatusFilter = "ALL" | "OPEN" | "WON" | "LOST";

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const [symbolSearch, setSymbolSearch] = useState("");
  const [closingTrade, setClosingTrade] = useState<Trade | null>(null);

  const fetchData = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (statusFilter !== "ALL") params.set("status", statusFilter);
    if (symbolSearch.trim()) params.set("symbol", symbolSearch.trim());

    Promise.all([
      fetch(`${API_URL}/api/trades?${params}`).then((r) => r.json()),
      fetch(`${API_URL}/api/trades/summary`).then((r) => r.json()),
    ])
      .then(([tradeList, sum]) => {
        setTrades(tradeList);
        setSummary(sum);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [statusFilter, symbolSearch]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCloseTrade = async (data: {
    id: number;
    exitPrice: number;
    actualPnl: number;
    actualFees: number;
    status: string;
  }) => {
    await fetch(`${API_URL}/api/trades/${data.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: data.status,
        exit_price: data.exitPrice,
        actual_pnl: data.actualPnl,
        actual_fees: data.actualFees,
        exit_date: new Date().toISOString(),
      }),
    });
    setClosingTrade(null);
    fetchData();
  };

  const handleDeleteTrade = async (id: number) => {
    await fetch(`${API_URL}/api/trades/${id}`, { method: "DELETE" });
    fetchData();
  };

  const statusOptions: StatusFilter[] = ["ALL", "OPEN", "WON", "LOST"];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
          Trade Ledger
        </h1>
        <p className="mt-1 text-gray-500 dark:text-gray-400">
          Track your trades, win rate, and net P&L
        </p>
      </header>

      {summary && <TradeSummaryCards summary={summary} />}

      {/* Filters */}
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-1 rounded-lg border border-gray-300 dark:border-gray-700">
          {statusOptions.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                s === statusOptions[0] ? "rounded-l-lg" : ""
              } ${s === statusOptions[statusOptions.length - 1] ? "rounded-r-lg" : ""} ${
                statusFilter === s
                  ? "bg-blue-600 text-white"
                  : "bg-white text-gray-600 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <input
          type="text"
          placeholder="Search symbol..."
          value={symbolSearch}
          onChange={(e) => setSymbolSearch(e.target.value)}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
        />
      </div>

      <div className="mt-6">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600" />
          </div>
        ) : (
          <TradeHistoryTable
            trades={trades}
            onClose={(t) => setClosingTrade(t)}
            onDelete={handleDeleteTrade}
          />
        )}
      </div>

      {closingTrade && (
        <CloseTradeModal
          trade={closingTrade}
          onConfirm={handleCloseTrade}
          onCancel={() => setClosingTrade(null)}
        />
      )}
    </div>
  );
}
