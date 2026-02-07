"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import type { PieLabelRenderProps } from "recharts";

interface Holding {
  symbol: string;
  current_value: number;
}

const COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
  "#14b8a6", "#e11d48", "#a855f7", "#0ea5e9", "#eab308",
];

export default function AllocationChart({ holdings }: { holdings: Holding[] }) {
  const data = holdings.map((h) => ({
    name: h.symbol,
    value: h.current_value,
  }));

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-gray-100">
        Portfolio Allocation
      </h3>
      <ResponsiveContainer width="100%" height={350}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            outerRadius={120}
            dataKey="value"
            label={(props: PieLabelRenderProps) =>
              `${props.name ?? ""} ${(((props.percent as number) ?? 0) * 100).toFixed(1)}%`
            }
          >
            {data.map((_, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value) =>
              "₹" + Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2 })
            }
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
