import { Candle } from "@/types/symbol";
import { calculateFees } from "@/lib/tradeCalculator";
import { FeeConfig, DEFAULT_FEE_CONFIG } from "@/lib/feeDefaults";

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
  volumeRatio: number;
  volumeConfirmed: boolean;
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
  period = 14
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
    current < 30 ? "OVERSOLD" : current > 70 ? "OVERBOUGHT" : "NEUTRAL";

  return { values, current: Math.round(current * 10) / 10, zone };
}

// ── Volume analysis ─────────────────────────────────────────────────

export function analyzeVolume(
  candles: Candle[],
  lookback = 20
): { current: number; average: number; ratio: number; confirmed: boolean } {
  if (candles.length < 2) {
    return { current: 0, average: 0, ratio: 0, confirmed: false };
  }

  const current = candles[candles.length - 1].volume;
  const slice = candles.slice(-lookback - 1, -1); // exclude last candle from average
  const average =
    slice.length > 0 ? slice.reduce((s, c) => s + c.volume, 0) / slice.length : current;
  const ratio = average > 0 ? Math.round((current / average) * 10) / 10 : 0;

  return { current, average: Math.round(average), ratio, confirmed: ratio >= 1.5 };
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
        score: 20,
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
        score: -20,
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
          score: 15,
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
          score: -15,
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
          score: 25,
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
          score: -25,
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
  config: FeeConfig = DEFAULT_FEE_CONFIG
): number {
  if (entry <= 0 || sl >= entry) return -1;

  const riskPerShare = entry - sl;
  const naiveTarget = entry + riskPerShare * 2; // 1:2 R:R

  for (let qty = 1; qty <= 10000; qty++) {
    const grossProfit = (naiveTarget - entry) * qty;
    const feeBuy = calculateFees(entry, qty, "BUY", tradeType, config);
    const feeSell = calculateFees(naiveTarget, qty, "SELL", tradeType, config);
    const netProfit = grossProfit - feeBuy.total - feeSell.total;
    if (netProfit > 0) return qty;
  }
  return -1;
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
    volumeRatio: 0,
    volumeConfirmed: false,
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

  let score = 0;
  const reasons: { label: string; sentiment: "BULLISH" | "BEARISH" | "NEUTRAL" }[] = [];

  // EMA trend
  const lastEma9 = ema9[ema9.length - 1];
  const lastEma21 = ema21[ema21.length - 1];
  let trend: "BULLISH" | "BEARISH" | "NEUTRAL" = "NEUTRAL";

  if (!isNaN(lastEma9) && !isNaN(lastEma21)) {
    if (lastEma9 > lastEma21) {
      score += 25;
      trend = "BULLISH";
      reasons.push({ label: "EMA 9 > 21 (bullish trend)", sentiment: "BULLISH" });
    } else {
      score -= 25;
      trend = "BEARISH";
      reasons.push({ label: "EMA 9 < 21 (bearish trend)", sentiment: "BEARISH" });
    }
  }

  // Recent crossover (last 3 bars)
  let recentCrossover = false;
  for (let i = ema9.length - 3; i < ema9.length; i++) {
    if (i < 1 || isNaN(ema9[i]) || isNaN(ema21[i]) || isNaN(ema9[i - 1]) || isNaN(ema21[i - 1]))
      continue;
    if (ema9[i] > ema21[i] && ema9[i - 1] <= ema21[i - 1]) {
      recentCrossover = true;
      score += 10;
      reasons.push({ label: "EMA 9/21 bullish crossover (recent)", sentiment: "BULLISH" });
      break;
    }
  }

  // RSI
  const { current: rsi, zone: rsiZone } = rsiResult;
  if (rsi < 30) {
    score += 20;
    reasons.push({ label: `RSI ${rsi} (oversold)`, sentiment: "BULLISH" });
  } else if (rsi < 50) {
    score -= 5;
    reasons.push({ label: `RSI ${rsi} (weak)`, sentiment: "BEARISH" });
  } else if (rsi <= 70) {
    score += 10;
    reasons.push({ label: `RSI ${rsi} (healthy)`, sentiment: "BULLISH" });
  } else {
    score -= 20;
    reasons.push({ label: `RSI ${rsi} (overbought)`, sentiment: "BEARISH" });
  }

  // Volume
  if (vol.ratio >= 1.5) {
    score += 15;
    reasons.push({ label: `Volume ${vol.ratio}x avg (strong)`, sentiment: "BULLISH" });
  } else if (vol.ratio < 0.8) {
    score -= 10;
    reasons.push({ label: `Volume ${vol.ratio}x avg (weak)`, sentiment: "BEARISH" });
  } else {
    reasons.push({ label: `Volume ${vol.ratio}x avg`, sentiment: "NEUTRAL" });
  }

  // Patterns
  for (const p of patterns) {
    score += p.score;
    reasons.push({ label: `${p.displayName} detected`, sentiment: p.sentiment });
  }

  // Clamp
  score = Math.max(-100, Math.min(100, score));

  // Verdict
  const verdict: "BUY" | "WAIT" | "AVOID" =
    score >= 30 ? "BUY" : score >= -10 ? "WAIT" : "AVOID";

  // Confidence
  const absScore = Math.abs(score);
  const confidence: "LOW" | "MEDIUM" | "HIGH" =
    absScore >= 60 ? "HIGH" : absScore >= 30 ? "MEDIUM" : "LOW";

  // Suggested trade params
  const entry = ltp ?? closes[closes.length - 1];
  let suggestedSL = findSwingLow(candles, 10);
  if ((entry - suggestedSL) / entry < 0.003) {
    suggestedSL = Math.round(entry * 0.99 * 100) / 100;
  }

  return {
    verdict,
    score,
    confidence,
    trend,
    recentCrossover,
    rsi,
    rsiZone,
    volumeRatio: vol.ratio,
    volumeConfirmed: vol.confirmed,
    patterns,
    reasons,
    suggestedEntry: Math.round(entry * 100) / 100,
    suggestedSL,
  };
}
