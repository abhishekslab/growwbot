"use client";

import { useState, useEffect, useMemo } from "react";
import { useTradeSettings, useCompoundedCapital } from "@/hooks/useTradeSettings";
import {
  calculatePositionSize,
  calculateFeeAdjustedTarget,
} from "@/lib/tradeCalculator";
import { Candle } from "@/types/symbol";
import {
  analyzeCandles,
  findMinProfitableQty,
  applyCapitalFilter,
  AnalysisResult,
} from "@/lib/candleAnalysis";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ActiveTrade {
  id: number;
  symbol: string;
  entry_price: number;
  stop_loss: number;
  target: number;
  quantity: number;
  status: string;
}

interface Props {
  symbol: string;
  ltp: number;
  candles: Candle[];
}

export default function TradePanel({ symbol, ltp, candles }: Props) {
  const { capital, riskPercent, feeConfig, rrRatio, tradeType, setTradeType, smallCapitalMode, autoCompound, maxPositions, paperMode } = useTradeSettings();
  const { effectiveCapital, realizedPnl } = useCompoundedCapital(capital, autoCompound, paperMode);

  const [entryPrice, setEntryPrice] = useState(0);
  const [userEdited, setUserEdited] = useState(false);
  const [slOffsetPct, setSlOffsetPct] = useState(2);
  const [slMode, setSlMode] = useState<"auto" | "manual">("auto");
  const [buying, setBuying] = useState(false);
  const [toast, setToast] = useState<{
    msg: string;
    type: "success" | "error";
  } | null>(null);
  const [activeTrade, setActiveTrade] = useState<ActiveTrade | null>(null);
  const [closing, setClosing] = useState(false);
  const [activePositionCount, setActivePositionCount] = useState(0);

  // Analysis
  const analysis: AnalysisResult | null = useMemo(() => {
    if (candles.length < 21) return null;
    return analyzeCandles(candles, ltp);
  }, [candles, ltp]);

  // Auto-update entry price from LTP if user hasn't manually edited
  useEffect(() => {
    if (!userEdited && ltp > 0) {
      setEntryPrice(ltp);
    }
  }, [ltp, userEdited]);

  // Auto-populate SL from swing low when in auto mode
  useEffect(() => {
    if (slMode !== "auto" || !analysis || entryPrice <= 0) return;
    const slDiff = entryPrice - analysis.suggestedSL;
    const pct = (slDiff / entryPrice) * 100;
    // Clamp to slider range and round to 0.5 step
    const clamped = Math.max(0.5, Math.min(10, pct));
    const rounded = Math.round(clamped * 2) / 2;
    setSlOffsetPct(rounded);
  }, [slMode, analysis, entryPrice]);

  // Check for active trade on mount and after buy
  useEffect(() => {
    if (!symbol) return;
    fetch(`${API_URL}/api/trades/active?is_paper=${paperMode}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((trades: ActiveTrade[]) => {
        const match = trades.find(
          (t: ActiveTrade) => t.symbol === symbol && t.status === "OPEN"
        );
        setActiveTrade(match || null);
        setActivePositionCount(trades.length);
      })
      .catch(() => {});
  }, [symbol, buying, paperMode]);

  // Computed values
  const slPrice = useMemo(
    () => Math.round(entryPrice * (1 - slOffsetPct / 100) * 100) / 100,
    [entryPrice, slOffsetPct]
  );

  const position = useMemo(
    () =>
      calculatePositionSize(
        effectiveCapital,
        riskPercent,
        entryPrice,
        slPrice,
        tradeType,
        feeConfig,
        rrRatio
      ),
    [effectiveCapital, riskPercent, entryPrice, slPrice, tradeType, feeConfig, rrRatio]
  );

  const feeAdjusted = useMemo(
    () =>
      calculateFeeAdjustedTarget(
        entryPrice,
        slPrice,
        position.quantity,
        tradeType,
        feeConfig,
        rrRatio
      ),
    [entryPrice, slPrice, position.quantity, tradeType, feeConfig, rrRatio]
  );

  const minProfitableQty = useMemo(() => {
    if (entryPrice <= 0 || slPrice >= entryPrice) return -1;
    return findMinProfitableQty(entryPrice, slPrice, tradeType, feeConfig, rrRatio);
  }, [entryPrice, slPrice, tradeType, feeConfig, rrRatio]);

  // Fee-aware capital filter
  const capitalFilter = useMemo(() => {
    if (!analysis) return null;
    return applyCapitalFilter(
      analysis,
      entryPrice,
      slPrice,
      effectiveCapital,
      tradeType,
      feeConfig,
      riskPercent,
      rrRatio,
      smallCapitalMode
    );
  }, [analysis, entryPrice, slPrice, effectiveCapital, tradeType, feeConfig, riskPercent, rrRatio, smallCapitalMode]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  const fmt = (n: number) => `\u20B9${n.toLocaleString("en-IN")}`;

  const handleBuy = async () => {
    if (position.quantity <= 0) return;
    setBuying(true);
    try {
      const res = await fetch(`${API_URL}/api/trades/buy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          entry_price: entryPrice,
          stop_loss: slPrice,
          target: feeAdjusted.target,
          quantity: position.quantity,
          capital_used: position.capitalUsed,
          risk_amount: position.riskAmount,
          fees_entry: position.feesEntry.total,
          fees_exit_target: position.feesExitTarget.total,
          fees_exit_sl: position.feesExitSL.total,
          trade_type: tradeType,
          is_paper: paperMode,
        }),
      });
      const data = await res.json();
      if (!res.ok)
        throw new Error(data.detail || "Buy failed");
      setToast({
        msg: `Order placed! Trade #${data.trade?.id || "—"}`,
        type: "success",
      });
      setActiveTrade(data.trade || null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Buy failed";
      setToast({ msg: message, type: "error" });
    } finally {
      setBuying(false);
    }
  };

  const handleClose = async () => {
    if (!activeTrade) return;
    setClosing(true);
    try {
      const res = await fetch(
        `${API_URL}/api/trades/${activeTrade.id}/close`,
        { method: "POST" }
      );
      const data = await res.json();
      if (!res.ok)
        throw new Error(data.detail || "Close failed");
      setToast({ msg: "Position closed", type: "success" });
      setActiveTrade(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Close failed";
      setToast({ msg: message, type: "error" });
    } finally {
      setClosing(false);
    }
  };

  // Active trade view
  if (activeTrade) {
    const unrealizedPnl =
      (ltp - activeTrade.entry_price) * activeTrade.quantity;
    const isProfit = unrealizedPnl >= 0;

    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            Active Position
          </h3>
          <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
            Monitoring
          </span>
        </div>

        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Entry</span>
            <span className="text-gray-900 dark:text-gray-100">
              {fmt(activeTrade.entry_price)} x {activeTrade.quantity}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">SL</span>
            <span className="text-red-600 dark:text-red-400">
              {fmt(activeTrade.stop_loss)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Target</span>
            <span className="text-green-600 dark:text-green-400">
              {fmt(activeTrade.target)}
            </span>
          </div>
          <div className="flex justify-between border-t border-gray-100 pt-2 dark:border-gray-800">
            <span className="text-gray-500 dark:text-gray-400">
              Unrealized P&L
            </span>
            <span
              className={`font-semibold ${
                isProfit
                  ? "text-green-600 dark:text-green-400"
                  : "text-red-600 dark:text-red-400"
              }`}
            >
              {isProfit ? "+" : ""}
              {fmt(Math.round(unrealizedPnl * 100) / 100)}
            </span>
          </div>
        </div>

        <p className="mt-3 text-center text-xs text-gray-400 dark:text-gray-500">
          Auto-exit on SL/Target breach
        </p>

        <button
          onClick={handleClose}
          disabled={closing}
          className="mt-3 w-full rounded-lg bg-gray-600 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
        >
          {closing ? "Closing..." : "Close Position"}
        </button>

        {toast && (
          <div
            className={`mt-2 rounded-lg px-3 py-2 text-xs font-medium text-white ${
              toast.type === "success" ? "bg-green-600" : "bg-red-600"
            }`}
          >
            {toast.msg}
          </div>
        )}
      </div>
    );
  }

  // Verdict styling
  const verdictStyles = {
    BUY: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    WAIT: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
    AVOID: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  };

  const trendArrow = {
    BULLISH: { icon: "\u25B2", color: "text-green-600 dark:text-green-400" },
    BEARISH: { icon: "\u25BC", color: "text-red-600 dark:text-red-400" },
    NEUTRAL: { icon: "~", color: "text-gray-500 dark:text-gray-400" },
  };

  const sentimentPrefix = {
    BULLISH: { char: "+", color: "text-green-600 dark:text-green-400" },
    BEARISH: { char: "-", color: "text-red-600 dark:text-red-400" },
    NEUTRAL: { char: "~", color: "text-gray-500 dark:text-gray-400" },
  };

  const effectiveVerdict = capitalFilter?.verdict ?? analysis?.verdict ?? "WAIT";

  // Buy form view
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
        Buy ({tradeType === "INTRADAY" ? "MIS / Intraday" : "CNC / Delivery"})
      </h3>

      {paperMode && (
        <div className="mb-3 rounded-lg border border-orange-300 bg-orange-50 px-3 py-2 text-xs font-medium text-orange-800 dark:border-orange-700 dark:bg-orange-950 dark:text-orange-200">
          Paper Mode — No real money
        </div>
      )}

      {/* MIS/CNC toggle */}
      <div className="mb-3 flex items-center gap-1">
        <button
          onClick={() => setTradeType("INTRADAY")}
          className={`rounded-l-lg px-3 py-1 text-xs font-medium transition-colors ${
            tradeType === "INTRADAY"
              ? "bg-blue-600 text-white"
              : "border border-gray-300 bg-white text-gray-500 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
          }`}
        >
          MIS
        </button>
        <button
          onClick={() => setTradeType("DELIVERY")}
          className={`rounded-r-lg px-3 py-1 text-xs font-medium transition-colors ${
            tradeType === "DELIVERY"
              ? "bg-blue-600 text-white"
              : "border border-gray-300 bg-white text-gray-500 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
          }`}
        >
          CNC
        </button>
      </div>

      {/* Signal Card */}
      {analysis ? (
        <div className="mb-3 rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800">
          {/* Verdict header */}
          <div className="mb-2 flex items-center justify-between">
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${verdictStyles[effectiveVerdict]}`}
            >
              {effectiveVerdict}
            </span>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              Score: {analysis.score > 0 ? "+" : ""}
              {analysis.score} ({analysis.confidence})
            </span>
          </div>

          {/* Indicators grid */}
          <div className="mb-2 space-y-1 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-gray-500 dark:text-gray-400">Trend</span>
              <span className={trendArrow[analysis.trend].color}>
                EMA 9{analysis.trend === "BULLISH" ? " > " : analysis.trend === "BEARISH" ? " < " : " = "}21{" "}
                {trendArrow[analysis.trend].icon} {analysis.trend.charAt(0) + analysis.trend.slice(1).toLowerCase()}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-500 dark:text-gray-400">RSI</span>
              <span
                className={
                  analysis.rsiZone === "OVERSOLD"
                    ? "text-green-600 dark:text-green-400"
                    : analysis.rsiZone === "OVERBOUGHT"
                      ? "text-red-600 dark:text-red-400"
                      : "text-gray-600 dark:text-gray-300"
                }
              >
                {analysis.rsi}{" "}
                {analysis.rsiZone === "NEUTRAL"
                  ? "~ Neutral"
                  : analysis.rsiZone === "OVERSOLD"
                    ? "\u25B2 Oversold"
                    : "\u25BC Overbought"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-500 dark:text-gray-400">Volume</span>
              <span
                className={
                  analysis.volumeConfirmed
                    ? "text-green-600 dark:text-green-400"
                    : analysis.volumeRatio < 0.8
                      ? "text-red-600 dark:text-red-400"
                      : "text-gray-600 dark:text-gray-300"
                }
              >
                {analysis.volumeRatio}x avg{" "}
                {analysis.volumeRatio >= 3.0 ? "\u25B2 Very Strong" : analysis.volumeConfirmed ? "\u25B2 Strong" : analysis.volumeRatio < 0.8 ? "\u25BC Weak" : ""}
              </span>
            </div>
            {analysis.vwap > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-gray-500 dark:text-gray-400">VWAP</span>
                <span
                  className={
                    analysis.aboveVwap
                      ? "text-green-600 dark:text-green-400"
                      : "text-red-600 dark:text-red-400"
                  }
                >
                  {`\u20B9${analysis.vwap.toLocaleString("en-IN")}`}{" "}
                  {analysis.aboveVwap ? "\u25B2 Above" : "\u25BC Below"}
                </span>
              </div>
            )}
          </div>

          {/* Patterns */}
          {analysis.patterns.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1">
              {analysis.patterns.map((p, i) => (
                <span
                  key={i}
                  className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    p.sentiment === "BULLISH"
                      ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                      : "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                  }`}
                >
                  {p.displayName}
                </span>
              ))}
            </div>
          )}

          {/* Reasons */}
          <div className="space-y-0.5 text-[11px]">
            {analysis.reasons.map((r, i) => (
              <div key={i} className="flex items-start gap-1">
                <span className={`font-bold ${sentimentPrefix[r.sentiment].color}`}>
                  {sentimentPrefix[r.sentiment].char}
                </span>
                <span className="text-gray-600 dark:text-gray-300">{r.label}</span>
              </div>
            ))}
          </div>

          {/* Suggested SL and min qty */}
          <div className="mt-2 space-y-0.5 border-t border-gray-200 pt-2 text-xs dark:border-gray-600">
            <div className="flex justify-between">
              <span className="text-gray-500 dark:text-gray-400">Suggested SL {analysis.atr > 0 ? "(ATR)" : "(swing)"}</span>
              <span className="font-medium text-gray-900 dark:text-gray-100">
                {fmt(analysis.suggestedSL)}
              </span>
            </div>
            {minProfitableQty > 0 && (
              <div className="flex justify-between">
                <span className="text-gray-500 dark:text-gray-400">Min profitable</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {minProfitableQty} shares
                </span>
              </div>
            )}
            {minProfitableQty > 0 &&
              position.quantity > 0 &&
              position.quantity < minProfitableQty && (
                <p className="mt-1 text-[11px] font-medium text-orange-600 dark:text-orange-400">
                  Position ({position.quantity}) is below min profitable qty ({minProfitableQty})
                </p>
              )}
          </div>
        </div>
      ) : (
        <p className="mb-3 text-xs text-gray-400 dark:text-gray-500">
          Need 21+ candles for analysis
        </p>
      )}

      {/* Fee warning */}
      {capitalFilter?.feeWarning && capitalFilter.feeWarningReason && (
        <div className="mb-3 rounded-lg border border-orange-300 bg-orange-50 p-3 text-xs text-orange-800 dark:border-orange-700 dark:bg-orange-950 dark:text-orange-200">
          <span className="font-semibold">Fee Warning:</span> {capitalFilter.feeWarningReason}
        </div>
      )}

      {/* Entry Price */}
      <div className="mb-3">
        <label className="mb-1 block text-xs text-gray-500 dark:text-gray-400">
          Entry Price
        </label>
        <input
          type="number"
          step="0.05"
          value={entryPrice}
          onChange={(e) => {
            setUserEdited(true);
            setEntryPrice(Number(e.target.value));
          }}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100"
        />
        {userEdited && (
          <button
            onClick={() => {
              setUserEdited(false);
              setEntryPrice(ltp);
            }}
            className="mt-1 text-xs text-blue-500 hover:underline"
          >
            Reset to LTP
          </button>
        )}
      </div>

      {/* SL Offset Slider */}
      <div className="mb-3">
        <label className="mb-1 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
          <span>
            SL Offset
            {slMode === "manual" && analysis && (
              <button
                onClick={() => setSlMode("auto")}
                className="ml-2 text-blue-500 hover:underline"
              >
                Reset to suggested
              </button>
            )}
          </span>
          <span className="font-medium text-gray-900 dark:text-gray-100">
            {slOffsetPct}% &rarr; {fmt(slPrice)}
          </span>
        </label>
        <input
          type="range"
          min="0.5"
          max="10"
          step="0.5"
          value={slOffsetPct}
          onChange={(e) => {
            setSlMode("manual");
            setSlOffsetPct(Number(e.target.value));
          }}
          className="w-full accent-blue-600"
        />
      </div>

      {/* Computed Display */}
      <div className="mb-3 space-y-1.5 rounded-lg bg-gray-50 p-3 text-xs dark:bg-gray-800">
        {autoCompound && realizedPnl !== 0 && (
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Effective Capital</span>
            <span className="font-medium text-purple-600 dark:text-purple-400">
              {fmt(effectiveCapital)} <span className="text-[10px] text-gray-400">({realizedPnl >= 0 ? "+" : ""}{fmt(realizedPnl)})</span>
            </span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Target (1:{rrRatio} net)</span>
          <span className="font-medium text-green-600 dark:text-green-400">
            {fmt(feeAdjusted.target)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Quantity</span>
          <span className="text-gray-900 dark:text-gray-100">
            {position.quantity}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Capital Used</span>
          <span className="text-gray-900 dark:text-gray-100">
            {fmt(position.capitalUsed)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">Est. Fees</span>
          <span className="text-gray-900 dark:text-gray-100">
            {fmt(
              position.feesEntry.total +
                position.feesExitTarget.total
            )}
          </span>
        </div>
        <div className="flex justify-between border-t border-gray-200 pt-1.5 dark:border-gray-700">
          <span className="text-gray-500 dark:text-gray-400">
            Net P&L at Target
          </span>
          <span className="font-medium text-green-600 dark:text-green-400">
            +{fmt(feeAdjusted.netProfit)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">
            Net Loss at SL
          </span>
          <span className="font-medium text-red-600 dark:text-red-400">
            {fmt(feeAdjusted.netLoss)}
          </span>
        </div>
      </div>

      {/* Positions counter */}
      <div className="mb-2 text-center text-xs text-gray-500 dark:text-gray-400">
        {activePositionCount}/{maxPositions} positions
      </div>

      {/* Buy Button */}
      <button
        onClick={handleBuy}
        disabled={buying || position.quantity <= 0 || activePositionCount >= maxPositions}
        className="w-full rounded-lg bg-green-600 py-2.5 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50"
      >
        {buying
          ? "Placing Order..."
          : activePositionCount >= maxPositions
            ? `Max ${maxPositions} positions reached`
            : paperMode
              ? `Paper Buy ${position.quantity} @ ${fmt(entryPrice)}`
              : `Buy ${position.quantity} @ ${fmt(entryPrice)}`}
      </button>

      {position.quantity <= 0 && entryPrice > 0 && activePositionCount < maxPositions && (
        <p className="mt-2 text-center text-xs text-red-500">
          Insufficient capital or SL too tight
        </p>
      )}

      {toast && (
        <div
          className={`mt-2 rounded-lg px-3 py-2 text-xs font-medium text-white ${
            toast.type === "success" ? "bg-green-600" : "bg-red-600"
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
