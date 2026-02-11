"use client";

import { useState, useEffect, useCallback } from "react";
import { FeeConfig, DEFAULT_FEE_CONFIG } from "@/lib/feeDefaults";

const STORAGE_KEY = "groww_trade_settings";
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface TradeSettings {
  capital: number;
  riskPercent: number;
  feeConfig: FeeConfig;
  tradeType: "INTRADAY" | "DELIVERY";
  rrRatio: number;
  maxPositions: number;
  smallCapitalMode: boolean;
  autoCompound: boolean;
  targetCapital: number;
  paperMode: boolean;
}

const DEFAULTS: TradeSettings = {
  capital: 100000,
  riskPercent: 1,
  feeConfig: DEFAULT_FEE_CONFIG,
  tradeType: "DELIVERY",
  rrRatio: 2,
  maxPositions: 5,
  smallCapitalMode: false,
  autoCompound: false,
  targetCapital: 100000,
  paperMode: false,
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

  const setTradeType = useCallback(
    (tradeType: "INTRADAY" | "DELIVERY") => persist({ ...settings, tradeType }),
    [settings, persist]
  );

  const setRrRatio = useCallback(
    (rrRatio: number) => persist({ ...settings, rrRatio }),
    [settings, persist]
  );

  const setMaxPositions = useCallback(
    (maxPositions: number) => persist({ ...settings, maxPositions }),
    [settings, persist]
  );

  const setAutoCompound = useCallback(
    (autoCompound: boolean) => persist({ ...settings, autoCompound }),
    [settings, persist]
  );

  const setTargetCapital = useCallback(
    (targetCapital: number) => persist({ ...settings, targetCapital }),
    [settings, persist]
  );

  const setPaperMode = useCallback(
    (paperMode: boolean) => persist({ ...settings, paperMode }),
    [settings, persist]
  );

  const setSmallCapitalMode = useCallback(
    (enabled: boolean) => {
      if (enabled) {
        persist({
          ...settings,
          smallCapitalMode: true,
          tradeType: "INTRADAY",
          riskPercent: Math.max(settings.riskPercent, 2),
          rrRatio: Math.max(settings.rrRatio, 3),
          maxPositions: 2,
        });
      } else {
        persist({ ...settings, smallCapitalMode: false });
      }
    },
    [settings, persist]
  );

  return {
    ...settings,
    loaded,
    setCapital,
    setRiskPercent,
    setFeeConfig,
    setTradeType,
    setRrRatio,
    setMaxPositions,
    setSmallCapitalMode,
    setAutoCompound,
    setTargetCapital,
    setPaperMode,
  };
}

export function useCompoundedCapital(baseCapital: number, autoCompound: boolean, paperMode: boolean = false) {
  const [realizedPnl, setRealizedPnl] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!autoCompound) {
      setRealizedPnl(0);
      return;
    }
    setLoading(true);
    const paperParam = paperMode ? "?is_paper=true" : "?is_paper=false";
    fetch(`${API_URL}/api/trades/realized-pnl${paperParam}`)
      .then((r) => (r.ok ? r.json() : { realized_pnl: 0 }))
      .then((data) => {
        setRealizedPnl(data.realized_pnl || 0);
        setLoading(false);
      })
      .catch(() => {
        setRealizedPnl(0);
        setLoading(false);
      });
  }, [autoCompound, paperMode]);

  const effectiveCapital = autoCompound
    ? Math.max(baseCapital, baseCapital + realizedPnl)
    : baseCapital;

  return { effectiveCapital, realizedPnl, loading };
}
