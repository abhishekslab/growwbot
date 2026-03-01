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
          <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--chart-axis-tick)" }} />
          <YAxis
            tick={{ fontSize: 11, fill: "var(--chart-axis-tick)" }}
            tickFormatter={(val) => "₹" + val.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
          />
          <Tooltip
            formatter={(value) =>
              "₹" + Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2 })
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
