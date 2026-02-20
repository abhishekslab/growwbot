"use client";

import { useEffect, useState } from "react";
import PortfolioSummary from "@/components/PortfolioSummary";
import HoldingsTable from "@/components/HoldingsTable";
import AllocationChart from "@/components/AllocationChart";
import PnLChart from "@/components/PnLChart";

interface Holding {
  symbol: string;
  quantity: number;
  average_price: number;
  ltp: number;
  current_value: number;
  invested_value: number;
  pnl: number;
  pnl_percentage: number;
}

interface Summary {
  total_current_value: number;
  total_invested_value: number;
  total_pnl: number;
  total_pnl_percentage: number;
}

interface ApiResponse {
  holdings: Holding[];
  summary: Summary;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function PortfolioPage() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_URL}/api/holdings`)
      .then((res) => {
        if (!res.ok) return res.json().then((err) => Promise.reject(err));
        return res.json();
      })
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        const message = err?.detail || err?.message || "Failed to connect to the backend server.";
        setError(message);
        setLoading(false);
      });
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">GrowwBot Portfolio</h1>
        <p className="mt-1 text-gray-500 dark:text-gray-400">
          Track your stock holdings and performance
        </p>
      </header>

      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600" />
          <span className="ml-3 text-gray-500">Loading portfolio data...</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-800 dark:bg-red-950">
          <h2 className="text-lg font-semibold text-red-800 dark:text-red-200">
            Unable to load portfolio
          </h2>
          <p className="mt-2 text-red-600 dark:text-red-400">{error}</p>
          <p className="mt-4 text-sm text-red-500 dark:text-red-400">
            Make sure the backend is running at {API_URL} and your API credentials are configured in{" "}
            <code className="rounded bg-red-100 px-1 dark:bg-red-900">server/.env</code>.
          </p>
        </div>
      )}

      {data && (
        <div className="space-y-8">
          <PortfolioSummary summary={data.summary} />
          <HoldingsTable holdings={data.holdings} />
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
            <AllocationChart holdings={data.holdings} />
            <PnLChart holdings={data.holdings} />
          </div>
        </div>
      )}
    </div>
  );
}
