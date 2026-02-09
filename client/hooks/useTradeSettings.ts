"use client";

import { useState, useEffect, useCallback } from "react";
import { FeeConfig, DEFAULT_FEE_CONFIG } from "@/lib/feeDefaults";

const STORAGE_KEY = "groww_trade_settings";

interface TradeSettings {
  capital: number;
  riskPercent: number;
  feeConfig: FeeConfig;
}

const DEFAULTS: TradeSettings = {
  capital: 100000,
  riskPercent: 1,
  feeConfig: DEFAULT_FEE_CONFIG,
};

export function useTradeSettings() {
  const [settings, setSettings] = useState<TradeSettings>(DEFAULTS);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Partial<TradeSettings>;
        setSettings({ ...DEFAULTS, ...parsed });
      }
    } catch {
      // ignore corrupt data
    }
    setLoaded(true);
  }, []);

  const persist = useCallback((next: TradeSettings) => {
    setSettings(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // storage full — silently ignore
    }
  }, []);

  const setCapital = useCallback(
    (capital: number) => persist({ ...settings, capital }),
    [settings, persist]
  );

  const setRiskPercent = useCallback(
    (riskPercent: number) => persist({ ...settings, riskPercent }),
    [settings, persist]
  );

  const setFeeConfig = useCallback(
    (feeConfig: FeeConfig) => persist({ ...settings, feeConfig }),
    [settings, persist]
  );

  return {
    ...settings,
    loaded,
    setCapital,
    setRiskPercent,
    setFeeConfig,
  };
}
