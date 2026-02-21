"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface EquityPoint {
  time: number;
  equity: number;
}

export default function BacktestEquityCurve({ data }: { data: EquityPoint[] }) {
  const chartData = data.map((d) => ({
    ...d,
    date: new Date(d.time * 1000).toLocaleDateString("en-IN", {
      month: "short",
      day: "numeric",
      year: "2-digit",
    }),
  }));

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-gray-100">Equity Curve</h3>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            className="text-gray-600 dark:text-gray-400"
          />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={(val) => "₹" + val.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
            className="text-gray-600 dark:text-gray-400"
          />
          <Tooltip
            formatter={(value: number) =>
              "₹" + value.toLocaleString("en-IN", { minimumFractionDigits: 2 })
            }
            labelFormatter={(label) => label}
          />
          <Area
            type="monotone"
            dataKey="equity"
            stroke="rgb(59, 130, 246)"
            fill="rgba(59, 130, 246, 0.2)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
