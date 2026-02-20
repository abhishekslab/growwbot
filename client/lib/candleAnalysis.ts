import { Candle } from "@/types/symbol";
import { calculateFees } from "@/lib/tradeCalculator";
import { FeeConfig, DEFAULT_FEE_CONFIG } from "@/lib/feeDefaults";

// ── Trade Guardrail Types ───────────────────────────────────────────

export interface TradeWarning {
  id: string;
  severity: "CAUTION" | "WARNING" | "DANGER";
  title: string;
  detail: string;
}

export interface EntrySnapshot {
  verdict: string;
  score: number;
  confidence: string;
  trend: string;
  rsi: number;
  rsiZone: string;
  volumeRatio: number;
  volumeConfirmed: boolean;
  vwap: number;
  aboveVwap: boolean;
  atr: number;
  patterns: string[];
  reasons: string[];
  dayChangePct: number;
  sessionHigh: number;
  entryPrice: number;
  target: number;
  stopLoss: number;
  warnings: string[];
  warningDetails: string[];
}

// ── Interfaces ──────────────────────────────────────────────────────

export interface DetectedPattern {
  name: string;
  displayName: string;
  sentiment: "BULLISH" | "BEARISH";
  score: number;
}

export interface AnalysisResult {
  verdict: "BUY" | "WAIT" | "AVOID";
  score: number;
  confidence: "LOW" | "MEDIUM" | "HIGH";
  trend: "BULLISH" | "BEARISH" | "NEUTRAL";
  recentCrossover: boolean;
  rsi: number;
  rsiZone: "OVERSOLD" | "NEUTRAL" | "OVERBOUGHT";
  rsiTurningUp: boolean;
  volumeRatio: number;
  volumeConfirmed: boolean;
  vwap: number;
  aboveVwap: boolean;
  atr: number;
  patterns: DetectedPattern[];
  reasons: { label: string; sentiment: "BULLISH" | "BEARISH" | "NEUTRAL" }[];
  suggestedEntry: number;
  suggestedSL: number;
}

// ── EMA ─────────────────────────────────────────────────────────────

export function calculateEMA(closes: number[], period: number): number[] {
  const ema: number[] = new Array(closes.length).fill(NaN);
  if (closes.length < period) return ema;

  // Seed with SMA of first `period` values
  let sum = 0;
  for (let i = 0; i < period; i++) sum += closes[i];
  ema[period - 1] = sum / period;

  const k = 2 / (period + 1);
  for (let i = period; i < closes.length; i++) {
    ema[i] = closes[i] * k + ema[i - 1] * (1 - k);
  }
  return ema;
}

// ── RSI (Wilder's smoothing) ────────────────────────────────────────

export function calculateRSI(
  candles: Candle[],
  period = 14,
): { values: number[]; current: number; zone: "OVERSOLD" | "NEUTRAL" | "OVERBOUGHT" } {
  const closes = candles.map((c) => c.close);
  const values: number[] = new Array(closes.length).fill(NaN);

  if (closes.length < period + 1) {
    return { values, current: 50, zone: "NEUTRAL" };
  }

  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff > 0) avgGain += diff;
    else avgLoss += Math.abs(diff);
  }
  avgGain /= period;
  avgLoss /= period;

  const rs0 = avgLoss === 0 ? 100 : avgGain / avgLoss;
  values[period] = 100 - 100 / (1 + rs0);

  for (let i = period + 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? Math.abs(diff) : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    values[i] = 100 - 100 / (1 + rs);
  }

  const current = values[values.length - 1] ?? 50;
  const zone: "OVERSOLD" | "NEUTRAL" | "OVERBOUGHT" =
    current < 30 ? "OVERSOLD" : current > 65 ? "OVERBOUGHT" : "NEUTRAL";

  return { values, current: Math.round(current * 10) / 10, zone };
}

// ── Volume analysis ─────────────────────────────────────────────────

export function analyzeVolume(
  candles: Candle[],
  lookback = 20,
): { current: number; average: number; ratio: number; confirmed: boolean } {
  if (candles.length < 2) {
    return { current: 0, average: 0, ratio: 0, confirmed: false };
  }

  const current = candles[candles.length - 1].volume;
  const slice = candles.slice(-lookback - 1, -1); // exclude last candle from average
  const average =
    slice.length > 0 ? slice.reduce((s, c) => s + c.volume, 0) / slice.length : current;
  const ratio = average > 0 ? Math.round((current / average) * 10) / 10 : 0;

  return { current, average: Math.round(average), ratio, confirmed: ratio >= 2.0 };
}

// ── VWAP (session-anchored) ─────────────────────────────────────────

export function calculateVWAP(
  candles: Candle[],
  ltp?: number,
): { vwap: number; aboveVwap: boolean } {
  if (candles.length === 0) return { vwap: 0, aboveVwap: false };

  // IST session start = 9:15 AM IST = 03:45 UTC
  const IST_SESSION_START_UTC_HOURS = 3;
  const IST_SESSION_START_UTC_MINUTES = 45;

  // Find the latest session start boundary
  let sessionStartIdx = 0;
  for (let i = candles.length - 1; i >= 0; i--) {
    const d = new Date(candles[i].time * 1000);
    const utcH = d.getUTCHours();
    const utcM = d.getUTCMinutes();
    // First candle at or after 03:45 UTC on the same day
    if (
      utcH === IST_SESSION_START_UTC_HOURS &&
      utcM >= IST_SESSION_START_UTC_MINUTES &&
      utcM < IST_SESSION_START_UTC_MINUTES + 5
    ) {
      sessionStartIdx = i;
      break;
    }
    // If we cross a day boundary (previous candle was previous day's close), reset
    if (i > 0) {
      const prevD = new Date(candles[i - 1].time * 1000);
      if (d.getUTCDate() !== prevD.getUTCDate()) {
        sessionStartIdx = i;
        break;
      }
    }
  }

  let cumTPV = 0; // cumulative (typicalPrice * volume)
  let cumVol = 0;
  for (let i = sessionStartIdx; i < candles.length; i++) {
    const c = candles[i];
    const typicalPrice = (c.high + c.low + c.close) / 3;
    cumTPV += typicalPrice * c.volume;
    cumVol += c.volume;
  }

  const vwap = cumVol > 0 ? Math.round((cumTPV / cumVol) * 100) / 100 : 0;
  const currentPrice = ltp ?? candles[candles.length - 1].close;
  return { vwap, aboveVwap: currentPrice > vwap };
}

// ── ATR (Wilder's smoothing) ────────────────────────────────────────

export function calculateATR(candles: Candle[], period = 14): number {
  if (candles.length < period + 1) return 0;

  const trueRanges: number[] = [];
  for (let i = 1; i < candles.length; i++) {
    const high = candles[i].high;
    const low = candles[i].low;
    const prevClose = candles[i - 1].close;
    const tr = Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose));
    trueRanges.push(tr);
  }

  // Seed ATR with SMA of first `period` TRs
  let atr = 0;
  for (let i = 0; i < period; i++) atr += trueRanges[i];
  atr /= period;

  // Wilder's smoothing for remaining
  for (let i = period; i < trueRanges.length; i++) {
    atr = (atr * (period - 1) + trueRanges[i]) / period;
  }

  return Math.round(atr * 100) / 100;
}

// ── Pattern detection ───────────────────────────────────────────────

export function detectPatterns(candles: Candle[]): DetectedPattern[] {
  const patterns: DetectedPattern[] = [];
  if (candles.length < 5) return patterns;

  const recent = candles.slice(-5);

  for (let i = 1; i < recent.length; i++) {
    const prev = recent[i - 1];
    const curr = recent[i];
    const prevBody = Math.abs(prev.close - prev.open);
    const currBody = Math.abs(curr.close - curr.open);
    const prevIsRed = prev.close < prev.open;
    const currIsGreen = curr.close > curr.open;
    const currIsRed = curr.close < curr.open;
    const prevIsGreen = prev.close > prev.open;

    // Bullish Engulfing
    if (
      prevIsRed &&
      currIsGreen &&
      curr.close > prev.open &&
      curr.open < prev.close &&
      currBody > prevBody
    ) {
      patterns.push({
        name: "BULLISH_ENGULFING",
        displayName: "Bullish Engulfing",
        sentiment: "BULLISH",
        score: 15,
      });
    }

    // Bearish Engulfing
    if (
      prevIsGreen &&
      currIsRed &&
      curr.open > prev.close &&
      curr.close < prev.open &&
      currBody > prevBody
    ) {
      patterns.push({
        name: "BEARISH_ENGULFING",
        displayName: "Bearish Engulfing",
        sentiment: "BEARISH",
        score: -15,
      });
    }

    // Hammer (after 2+ red candles)
    if (i >= 2) {
      const twoBack = recent[i - 2];
      const lowerWick = Math.min(curr.open, curr.close) - curr.low;
      const upperWick = curr.high - Math.max(curr.open, curr.close);
      const body = currBody || 0.01; // avoid division by zero

      if (
        lowerWick >= 2 * body &&
        upperWick <= 0.3 * body &&
        twoBack.close < twoBack.open &&
        prevIsRed
      ) {
        patterns.push({
          name: "HAMMER",
          displayName: "Hammer",
          sentiment: "BULLISH",
          score: 10,
        });
      }

      // Shooting Star (after 2+ green candles)
      if (
        upperWick >= 2 * body &&
        lowerWick <= 0.3 * body &&
        twoBack.close > twoBack.open &&
        prevIsGreen
      ) {
        patterns.push({
          name: "SHOOTING_STAR",
          displayName: "Shooting Star",
          sentiment: "BEARISH",
          score: -10,
        });
      }
    }

    // Morning Star (3-candle pattern)
    if (i >= 2) {
      const first = recent[i - 2];
      const middle = recent[i - 1];
      const third = curr;
      const firstBody = Math.abs(first.close - first.open);
      const middleBody = Math.abs(middle.close - middle.open);
      const firstMidpoint = (first.open + first.close) / 2;

      if (
        first.close < first.open && // first is red
        middleBody < firstBody * 0.3 && // middle is small body
        third.close > third.open && // third is green
        third.close > firstMidpoint // third closes above first's midpoint
      ) {
        patterns.push({
          name: "MORNING_STAR",
          displayName: "Morning Star",
          sentiment: "BULLISH",
          score: 20,
        });
      }

      // Evening Star
      if (
        first.close > first.open && // first is green
        middleBody < firstBody * 0.3 && // middle is small body
        third.close < third.open && // third is red
        third.close < firstMidpoint // third closes below first's midpoint
      ) {
        patterns.push({
          name: "EVENING_STAR",
          displayName: "Evening Star",
          sentiment: "BEARISH",
          score: -20,
        });
      }
    }
  }

  return patterns;
}

// ── Swing low ───────────────────────────────────────────────────────

export function findSwingLow(candles: Candle[], lookback = 10): number {
  if (candles.length === 0) return 0;

  const slice = candles.slice(-lookback);
  const minLow = Math.min(...slice.map((c) => c.low));
  const lastClose = candles[candles.length - 1].close;

  // If swing low is too tight (< 0.3%), widen to 1%
  if ((lastClose - minLow) / lastClose < 0.003) {
    return Math.round(lastClose * 0.99 * 100) / 100;
  }
  return Math.round(minLow * 100) / 100;
}

// ── Min profitable quantity ─────────────────────────────────────────

export function findMinProfitableQty(
  entry: number,
  sl: number,
  tradeType: "INTRADAY" | "DELIVERY" = "DELIVERY",
  config: FeeConfig = DEFAULT_FEE_CONFIG,
  rrRatio: number = 2,
): number {
  if (entry <= 0 || sl >= entry) return -1;

  const riskPerShare = entry - sl;
  const naiveTarget = entry + riskPerShare * rrRatio;

  for (let qty = 1; qty <= 10000; qty++) {
    const grossProfit = (naiveTarget - entry) * qty;
    const feeBuy = calculateFees(entry, qty, "BUY", tradeType, config);
    const feeSell = calculateFees(naiveTarget, qty, "SELL", tradeType, config);
    const netProfit = grossProfit - feeBuy.total - feeSell.total;
    if (netProfit > 0) return qty;
  }
  return -1;
}

// ── Capital filter ──────────────────────────────────────────────────

export interface CapitalFilterResult {
  verdict: "BUY" | "WAIT" | "AVOID";
  feeWarning: boolean;
  feeWarningReason: string | null;
}

export function applyCapitalFilter(
  analysis: AnalysisResult,
  entry: number,
  sl: number,
  capital: number,
  tradeType: "INTRADAY" | "DELIVERY",
  feeConfig: FeeConfig,
  riskPercent: number,
  rrRatio: number,
  smallCapitalMode: boolean,
): CapitalFilterResult {
  let verdict = analysis.verdict;
  let feeWarning = false;
  let feeWarningReason: string | null = null;

  if (verdict === "BUY" && entry > 0 && sl > 0 && sl < entry) {
    const minQty = findMinProfitableQty(entry, sl, tradeType, feeConfig, rrRatio);
    const riskPerShare = entry - sl;
    const maxRisk = capital * (riskPercent / 100);
    const affordableQty = Math.floor(maxRisk / riskPerShare);

    if (minQty > 0 && affordableQty < minQty) {
      verdict = "WAIT";
      feeWarning = true;
      feeWarningReason = `Need ${minQty} shares for profit after fees, but can only afford ${affordableQty}`;
    }

    if (smallCapitalMode && analysis.score < 50) {
      verdict = "WAIT";
      feeWarning = true;
      feeWarningReason = feeWarningReason
        ? feeWarningReason + ". Small cap mode requires HIGH confidence (score 50+)"
        : "Small cap mode requires HIGH confidence (score 50+)";
    }
  }

  return { verdict, feeWarning, feeWarningReason };
}

// ── Main analysis ───────────────────────────────────────────────────

export function analyzeCandles(candles: Candle[], ltp?: number): AnalysisResult {
  const neutral: AnalysisResult = {
    verdict: "WAIT",
    score: 0,
    confidence: "LOW",
    trend: "NEUTRAL",
    recentCrossover: false,
    rsi: 50,
    rsiZone: "NEUTRAL",
    rsiTurningUp: false,
    volumeRatio: 0,
    volumeConfirmed: false,
    vwap: 0,
    aboveVwap: false,
    atr: 0,
    patterns: [],
    reasons: [],
    suggestedEntry: ltp ?? candles[candles.length - 1]?.close ?? 0,
    suggestedSL: 0,
  };

  if (candles.length < 21) {
    neutral.reasons = [{ label: "Insufficient data (need 21+ candles)", sentiment: "NEUTRAL" }];
    return neutral;
  }

  const closes = candles.map((c) => c.close);
  const ema9 = calculateEMA(closes, 9);
  const ema21 = calculateEMA(closes, 21);
  const rsiResult = calculateRSI(candles);
  const vol = analyzeVolume(candles);
  const patterns = detectPatterns(candles);
  const vwapResult = calculateVWAP(candles, ltp);
  const atr = calculateATR(candles);

  let score = 0;
  const reasons: { label: string; sentiment: "BULLISH" | "BEARISH" | "NEUTRAL" }[] = [];

  // ── EMA trend (±30) ──────────────────────────────────────────────
  const lastEma9 = ema9[ema9.length - 1];
  const lastEma21 = ema21[ema21.length - 1];
  let trend: "BULLISH" | "BEARISH" | "NEUTRAL" = "NEUTRAL";
  const lastPrice = closes[closes.length - 1];

  if (!isNaN(lastEma9) && !isNaN(lastEma21)) {
    if (lastEma9 > lastEma21) {
      score += 30;
      trend = "BULLISH";
      reasons.push({ label: "EMA 9 > 21 (bullish trend)", sentiment: "BULLISH" });
    } else {
      score -= 30;
      trend = "BEARISH";
      reasons.push({ label: "EMA 9 < 21 (bearish trend)", sentiment: "BEARISH" });
    }
  }

  // ── EMA crossover with confirmation gate (+10) ────────────────────
  let recentCrossover = false;
  const emaGapPct = lastPrice > 0 ? Math.abs(lastEma9 - lastEma21) / lastPrice : 0;

  for (let i = ema9.length - 3; i < ema9.length; i++) {
    if (i < 1 || isNaN(ema9[i]) || isNaN(ema21[i]) || isNaN(ema9[i - 1]) || isNaN(ema21[i - 1]))
      continue;
    if (ema9[i] > ema21[i] && ema9[i - 1] <= ema21[i - 1]) {
      recentCrossover = true;
      // Only award score if EMAs have separated enough (> 0.1% of price)
      if (emaGapPct > 0.001) {
        score += 10;
        reasons.push({ label: "EMA 9/21 bullish crossover (confirmed)", sentiment: "BULLISH" });
      } else {
        reasons.push({
          label: "EMA 9/21 crossover (unconfirmed, EMAs tight)",
          sentiment: "NEUTRAL",
        });
      }
      break;
    }
  }

  // ── VWAP position (±15) ───────────────────────────────────────────
  if (vwapResult.vwap > 0) {
    if (vwapResult.aboveVwap) {
      score += 15;
      reasons.push({
        label: `Above VWAP ${vwapResult.vwap.toLocaleString("en-IN")} (buyers in control)`,
        sentiment: "BULLISH",
      });
    } else {
      score -= 15;
      reasons.push({
        label: `Below VWAP ${vwapResult.vwap.toLocaleString("en-IN")} (sellers in control)`,
        sentiment: "BEARISH",
      });
    }
  }

  // ── RSI with reversal detection ───────────────────────────────────
  const { current: rsi, zone: rsiZone, values: rsiValues } = rsiResult;

  // Detect RSI turning up from oversold (crossed above 30 in last 3 candles)
  let rsiTurningUp = false;
  for (let i = rsiValues.length - 3; i < rsiValues.length; i++) {
    if (i < 1 || isNaN(rsiValues[i]) || isNaN(rsiValues[i - 1])) continue;
    if (rsiValues[i] > 30 && rsiValues[i - 1] <= 30) {
      rsiTurningUp = true;
      break;
    }
  }

  if (rsi < 30) {
    // Falling knife — only minor score, not a buy signal
    score += 5;
    reasons.push({ label: `RSI ${rsi} (oversold — falling knife risk)`, sentiment: "NEUTRAL" });
  } else if (rsi < 50) {
    if (rsiTurningUp) {
      // RSI just crossed back above 30 — confirmed reversal
      score += 15;
      reasons.push({ label: `RSI ${rsi} (reversal from oversold)`, sentiment: "BULLISH" });
    } else {
      score -= 5;
      reasons.push({ label: `RSI ${rsi} (weak)`, sentiment: "BEARISH" });
    }
  } else if (rsi <= 65) {
    score += 10;
    reasons.push({ label: `RSI ${rsi} (healthy)`, sentiment: "BULLISH" });
  } else if (rsi <= 75) {
    score -= 15;
    reasons.push({ label: `RSI ${rsi} (approaching overbought)`, sentiment: "BEARISH" });
  } else if (rsi <= 85) {
    score -= 30;
    reasons.push({ label: `RSI ${rsi} (overbought — high reversion risk)`, sentiment: "BEARISH" });
  } else {
    score -= 40;
    reasons.push({
      label: `RSI ${rsi} (extremely overbought — pullback imminent)`,
      sentiment: "BEARISH",
    });
  }

  // ── Volume (tiered: 3x, 2x, <0.8x) — flipped when overbought ───
  if (rsi > 70 && vol.ratio >= 2.0) {
    // High volume + overbought = likely distribution, not accumulation
    score -= 10;
    reasons.push({
      label: `Volume ${vol.ratio}x avg + RSI ${rsi} (distribution signal)`,
      sentiment: "BEARISH",
    });
  } else if (vol.ratio >= 3.0) {
    score += 20;
    reasons.push({ label: `Volume ${vol.ratio}x avg (very strong)`, sentiment: "BULLISH" });
  } else if (vol.ratio >= 2.0) {
    score += 15;
    reasons.push({ label: `Volume ${vol.ratio}x avg (strong)`, sentiment: "BULLISH" });
  } else if (vol.ratio < 0.8) {
    score -= 10;
    reasons.push({ label: `Volume ${vol.ratio}x avg (weak)`, sentiment: "BEARISH" });
  } else {
    reasons.push({ label: `Volume ${vol.ratio}x avg`, sentiment: "NEUTRAL" });
  }

  // ── Volume-gated patterns ─────────────────────────────────────────
  for (const p of patterns) {
    // Halve pattern score if volume is below average
    const effectiveScore = vol.ratio < 1.0 ? Math.round(p.score * 0.5) : p.score;
    score += effectiveScore;
    const volNote = vol.ratio < 1.0 ? " (low vol, half weight)" : "";
    reasons.push({ label: `${p.displayName} detected${volNote}`, sentiment: p.sentiment });
  }

  // ── Time-of-day filter (intraday candles only) ────────────────────
  if (candles.length >= 2) {
    const lastCandle = candles[candles.length - 1];
    const prevCandle = candles[candles.length - 2];
    const spacing = lastCandle.time - prevCandle.time;

    // Only apply to 5-minute or shorter intervals (spacing ≤ 600s)
    if (spacing > 0 && spacing <= 600) {
      const d = new Date(lastCandle.time * 1000);
      const utcH = d.getUTCHours();
      const utcM = d.getUTCMinutes();
      const utcMinutes = utcH * 60 + utcM;

      // 9:15-9:45 AM IST = 03:45-04:15 UTC = 225-255 UTC minutes
      if (utcMinutes >= 225 && utcMinutes < 255) {
        score -= 10;
        reasons.push({ label: "Opening volatility (9:15-9:45 IST)", sentiment: "BEARISH" });
      }
      // 2:45-3:30 PM IST = 09:15-10:00 UTC = 555-600 UTC minutes
      else if (utcMinutes >= 555 && utcMinutes < 600) {
        score -= 5;
        reasons.push({ label: "Closing session (2:45-3:30 IST)", sentiment: "BEARISH" });
      }
      // 10:00-11:30 AM IST = 04:30-06:00 UTC = 270-360 UTC minutes
      else if (utcMinutes >= 270 && utcMinutes < 360) {
        score += 5;
        reasons.push({ label: "Prime trading window (10:00-11:30 IST)", sentiment: "BULLISH" });
      }
    }
  }

  // Clamp
  score = Math.max(-100, Math.min(100, score));

  // Verdict — with hard overbought gate
  let verdict: "BUY" | "WAIT" | "AVOID" = score >= 30 ? "BUY" : score >= -10 ? "WAIT" : "AVOID";

  if (rsi > 85) {
    verdict = "AVOID";
    reasons.push({ label: `RSI ${rsi} > 85 — verdict forced to AVOID`, sentiment: "BEARISH" });
  } else if (rsi > 75 && verdict === "BUY") {
    verdict = "WAIT";
    reasons.push({ label: `RSI ${rsi} > 75 — verdict capped at WAIT`, sentiment: "BEARISH" });
  }

  // Confidence
  const absScore = Math.abs(score);
  const confidence: "LOW" | "MEDIUM" | "HIGH" =
    absScore >= 60 ? "HIGH" : absScore >= 30 ? "MEDIUM" : "LOW";

  // ── ATR-based stop-loss ───────────────────────────────────────────
  const entry = ltp ?? closes[closes.length - 1];
  const swingLow = findSwingLow(candles, 10);

  let suggestedSL: number;
  if (atr > 0) {
    // Primary: ATR × 2.0 below entry (wider SL avoids noise stops)
    const atrSL = Math.round((entry - atr * 2.0) * 100) / 100;
    // Floor: never place SL above the swing low
    suggestedSL = Math.min(atrSL, swingLow);
  } else {
    suggestedSL = swingLow;
  }

  // Minimum distance: 0.5% (up from 0.3%)
  if (entry > 0 && (entry - suggestedSL) / entry < 0.005) {
    suggestedSL = Math.round(entry * 0.995 * 100) / 100;
  }

  return {
    verdict,
    score,
    confidence,
    trend,
    recentCrossover,
    rsi,
    rsiZone,
    rsiTurningUp,
    volumeRatio: vol.ratio,
    volumeConfirmed: vol.confirmed,
    vwap: vwapResult.vwap,
    aboveVwap: vwapResult.aboveVwap,
    atr,
    patterns,
    reasons,
    suggestedEntry: Math.round(entry * 100) / 100,
    suggestedSL,
  };
}

// ── Trade Guardrails ────────────────────────────────────────────────

export function computeTradeWarnings(
  entryPrice: number,
  target: number,
  stopLoss: number,
  sessionHigh: number,
  dayChangePct: number,
  atr: number,
  isFnO: boolean,
): TradeWarning[] {
  const warnings: TradeWarning[] = [];

  // 1. Target above session high
  if (sessionHigh > 0 && target > sessionHigh) {
    warnings.push({
      id: "TARGET_ABOVE_SESSION_HIGH",
      severity: "WARNING",
      title: "Target above session high",
      detail: `Target ₹${target.toFixed(2)} is above today's high ₹${sessionHigh.toFixed(2)}. Price may face resistance.`,
    });
  }

  // 2. Exceeds typical range
  const targetPct = entryPrice > 0 ? ((target - entryPrice) / entryPrice) * 100 : 0;
  const totalMove = Math.abs(dayChangePct) + Math.abs(targetPct);
  const threshold = isFnO ? 4 : 6;
  if (totalMove > threshold) {
    warnings.push({
      id: "EXCEEDS_TYPICAL_RANGE",
      severity: totalMove > threshold * 1.5 ? "DANGER" : "WARNING",
      title: "Move exceeds typical range",
      detail: `Total predicted move ${totalMove.toFixed(1)}% (day ${dayChangePct.toFixed(1)}% + target ${targetPct.toFixed(1)}%) exceeds ${threshold}% typical for ${isFnO ? "F&O" : "non-F&O"} stocks.`,
    });
  }

  // 3. Large-cap overextended (F&O already up significantly)
  if (isFnO && dayChangePct > 3) {
    warnings.push({
      id: "LARGE_CAP_OVEREXTENDED",
      severity: dayChangePct > 5 ? "DANGER" : "CAUTION",
      title: "Already extended",
      detail: `F&O stock already up ${dayChangePct.toFixed(1)}% today. Late entries carry reversion risk.`,
    });
  }

  // 4. Target beyond 3x ATR
  if (atr > 0) {
    const targetDist = Math.abs(target - entryPrice);
    if (targetDist > 3 * atr) {
      warnings.push({
        id: "TARGET_BEYOND_ATR",
        severity: "CAUTION",
        title: "Target beyond 3× ATR",
        detail: `Target distance ₹${targetDist.toFixed(2)} exceeds 3× ATR (₹${(3 * atr).toFixed(2)}). May not reach in one session.`,
      });
    }
  }

  return warnings;
}

export function buildEntrySnapshot(
  analysis: AnalysisResult,
  entryPrice: number,
  target: number,
  stopLoss: number,
  dayChangePct: number,
  sessionHigh: number,
  warnings: TradeWarning[],
): EntrySnapshot {
  return {
    verdict: analysis.verdict,
    score: analysis.score,
    confidence: analysis.confidence,
    trend: analysis.trend,
    rsi: analysis.rsi,
    rsiZone: analysis.rsiZone,
    volumeRatio: analysis.volumeRatio,
    volumeConfirmed: analysis.volumeConfirmed,
    vwap: analysis.vwap,
    aboveVwap: analysis.aboveVwap,
    atr: analysis.atr,
    patterns: analysis.patterns.map((p) => p.displayName),
    reasons: analysis.reasons.map((r) => r.label),
    dayChangePct,
    sessionHigh,
    entryPrice,
    target,
    stopLoss,
    warnings: warnings.map((w) => w.id),
    warningDetails: warnings.map((w) => `${w.severity}: ${w.title}`),
  };
}
