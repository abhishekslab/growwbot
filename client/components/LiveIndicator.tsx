"use client";

import { useEffect, useState } from "react";

interface Props {
  lastUpdateTime: number | null; // Unix timestamp in seconds
  staleThresholdMs?: number; // default 30000
}

export default function LiveIndicator({
  lastUpdateTime,
  staleThresholdMs = 30000,
}: Props) {
  const [isStale, setIsStale] = useState(true);

  useEffect(() => {
    if (lastUpdateTime === null) {
      setIsStale(true);
      return;
    }

    const check = () => {
      const age = Date.now() - lastUpdateTime * 1000;
      setIsStale(age > staleThresholdMs);
    };

    check();
    const interval = setInterval(check, 5000);
    return () => clearInterval(interval);
  }, [lastUpdateTime, staleThresholdMs]);

  if (lastUpdateTime === null) return null;

  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`inline-block h-2 w-2 rounded-full ${
          isStale ? "bg-red-500" : "animate-pulse bg-green-500"
        }`}
      />
      <span
        className={`text-xs font-medium ${
          isStale
            ? "text-red-600 dark:text-red-400"
            : "text-green-600 dark:text-green-400"
        }`}
      >
        {isStale ? "Stale" : "Live"}
      </span>
    </div>
  );
}
