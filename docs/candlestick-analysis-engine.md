# Candlestick Analysis Engine

Technical documentation for the scoring engine in `client/lib/candleAnalysis.ts`. This engine analyzes 5-minute candle data and produces a composite BUY / WAIT / AVOID verdict tuned for Indian equity (NSE) intraday and BTST trading.

---

## Overview

The engine computes six independent signals, sums their scores into a composite value clamped to [-100, +100], and maps the result to a verdict.

| Composite Score | Verdict |
|-----------------|---------|
| ≥ 30            | BUY     |
| -10 to 29       | WAIT    |
| < -10           | AVOID   |

Confidence is derived from absolute score: **HIGH** (≥ 60), **MEDIUM** (≥ 30), **LOW** (< 30).

Minimum data requirement: **21 candles**.

---

## Signals and Weights

### 1. EMA Trend (±30)

Uses EMA-9 and EMA-21 of closing prices.

| Condition | Score | Reason |
|-----------|-------|--------|
| EMA 9 > EMA 21 | +30 | Bullish trend |
| EMA 9 < EMA 21 | -30 | Bearish trend |

This is the heaviest-weighted factor — trend-following is the most reliable intraday signal.

### 2. EMA Crossover (+10, gated)

Scans the last 3 candles for a bullish crossover (EMA 9 crossing above EMA 21).

**Confirmation gate**: The crossover only receives +10 if the EMA gap exceeds 0.1% of price (`|ema9 - ema21| / price > 0.001`). This prevents scoring whipsaw zones where the EMAs are essentially touching.

| Condition | Score |
|-----------|-------|
| Crossover found AND EMA gap > 0.1% | +10 |
| Crossover found but EMAs tight | 0 (noted in reasons as unconfirmed) |

### 3. VWAP Position (±15)

Session-anchored Volume Weighted Average Price. The session boundary is IST 9:15 AM (03:45 UTC). The engine scans backward through candles to find the latest session start, then computes:

```
typicalPrice = (high + low + close) / 3
VWAP = Σ(typicalPrice × volume) / Σ(volume)   [from session start]
```

| Condition | Score | Reason |
|-----------|-------|--------|
| Price > VWAP | +15 | Buyers in control |
| Price ≤ VWAP | -15 | Sellers in control |

VWAP is the single most-used intraday indicator on Indian institutional and algo desks.

### 4. RSI (variable, with reversal detection)

Standard RSI-14 with Wilder's smoothing.

| Condition | Score | Reason |
|-----------|-------|--------|
| RSI < 30 | +5 | Oversold — falling knife risk, not a buy signal |
| RSI 30–50, turning up from oversold* | +15 | Confirmed reversal from oversold |
| RSI 30–50, not turning up | -5 | Weak momentum |
| RSI 50–70 | +10 | Healthy momentum |
| RSI > 70 | -10 | Overbought (reduced penalty — strong trends sustain high RSI) |

**\*Reversal detection**: RSI is "turning up" if it crossed above 30 within the last 3 candles (was ≤ 30, now > 30). This distinguishes a stock bouncing off oversold from one still in freefall.

### 5. Volume (tiered)

Compares the latest candle's volume against the 20-candle average (excluding the current candle).

| Condition | Score | Reason |
|-----------|-------|--------|
| Ratio ≥ 3.0x | +20 | Very strong volume |
| Ratio ≥ 2.0x | +15 | Strong volume (confirmed) |
| Ratio < 0.8x | -10 | Weak volume |
| 0.8x – 2.0x | 0 | Normal |

The `volumeConfirmed` flag is `true` at ≥ 2.0x (raised from the previous 1.5x threshold to filter noise on Indian mid/small-caps).

### 6. Candlestick Patterns (volume-gated)

Detected over the last 5 candles. Base scores are **halved** if `volumeRatio < 1.0` — a pattern on below-average volume is unreliable.

| Pattern | Base Score | Low-Vol Score |
|---------|-----------|---------------|
| Bullish Engulfing | +15 | +8 |
| Bearish Engulfing | -15 | -8 |
| Hammer | +10 | +5 |
| Shooting Star | -10 | -5 |
| Morning Star | +20 | +10 |
| Evening Star | -20 | -10 |

---

## Score Scenarios

### Strong stock (expected: BUY 60+)
EMA bullish (+30) + above VWAP (+15) + healthy RSI (+10) + volume 2x (+15) = **+70 → BUY HIGH**

### Weak stock (expected: AVOID -40+)
EMA bearish (-30) + below VWAP (-15) + RSI weak (-5) + weak volume (-10) = **-60 → AVOID HIGH**

### Ambiguous stock (expected: WAIT, not BUY)
EMA bullish (+30) + below VWAP (-15) + RSI < 30 (+5) + normal volume (0) = **+20 → WAIT**

### Falling knife test
EMA bearish (-30) + below VWAP (-15) + RSI < 30 (+5) + weak volume (-10) = **-50 → AVOID HIGH**

The old algorithm would have scored the falling knife at -20 (RSI oversold was +20), potentially producing a WAIT. The new scoring correctly identifies it as AVOID.

---

## Stop-Loss Calculation

The engine uses a **three-tier** stop-loss strategy:

1. **Primary: ATR-based**
   - ATR-14 computed using Wilder's smoothing of True Range
   - `suggestedSL = entry - ATR × 1.5`

2. **Floor: Swing low**
   - 10-candle lookback for the lowest low
   - SL is capped to never sit above the swing low: `SL = min(atrSL, swingLow)`

3. **Minimum distance: 0.5%**
   - If SL distance < 0.5% of entry, force SL to `entry × 0.995`
   - This prevents excessively tight stops on low-volatility stocks

The ATR approach adapts to each stock's actual volatility, which is critical for Indian markets where mid-caps can swing 2-3% intraday.

---

## Indicator Functions

### `calculateEMA(closes, period)`
Standard Exponential Moving Average. Seeded with SMA of first `period` values, then applies multiplier `k = 2 / (period + 1)`.

### `calculateRSI(candles, period=14)`
Wilder's RSI. Returns `{ values[], current, zone }`. Zone thresholds: oversold < 30, overbought > 70.

### `analyzeVolume(candles, lookback=20)`
Returns `{ current, average, ratio, confirmed }`. The `confirmed` threshold is 2.0x.

### `calculateVWAP(candles, ltp?)`
Session-anchored VWAP. Finds IST 9:15 AM boundary by scanning candle timestamps (epoch seconds → UTC conversion). Returns `{ vwap, aboveVwap }`.

### `calculateATR(candles, period=14)`
True Range = max(H-L, |H-prevC|, |L-prevC|). Wilder's smoothing: `ATR = (prevATR × (period-1) + TR) / period`.

### `detectPatterns(candles)`
Scans last 5 candles for: Bullish/Bearish Engulfing, Hammer, Shooting Star, Morning/Evening Star. Returns array of `DetectedPattern` with base scores (gating applied in main analysis).

### `findSwingLow(candles, lookback=10)`
Minimum low in the lookback window. If too tight (< 0.3% from close), widens to 1% below close.

### `findMinProfitableQty(entry, sl, tradeType, feeConfig)`
Iterates quantities 1–10,000 to find the smallest position where net profit > 0 at a 1:2 R:R target, accounting for Indian exchange fees (brokerage, STT, exchange txn, SEBI, stamp duty, GST).

---

## AnalysisResult Interface

```typescript
interface AnalysisResult {
  verdict: "BUY" | "WAIT" | "AVOID";
  score: number;                    // -100 to +100
  confidence: "LOW" | "MEDIUM" | "HIGH";
  trend: "BULLISH" | "BEARISH" | "NEUTRAL";
  recentCrossover: boolean;         // EMA 9/21 bullish crossover in last 3 bars
  rsi: number;                      // Current RSI value
  rsiZone: "OVERSOLD" | "NEUTRAL" | "OVERBOUGHT";
  rsiTurningUp: boolean;            // RSI crossed above 30 in last 3 candles
  volumeRatio: number;              // Current vol / 20-candle avg
  volumeConfirmed: boolean;         // volumeRatio >= 2.0
  vwap: number;                     // Session VWAP price
  aboveVwap: boolean;               // LTP > VWAP
  atr: number;                      // ATR-14 value
  patterns: DetectedPattern[];      // Detected candlestick patterns
  reasons: { label, sentiment }[];  // Human-readable scoring breakdown
  suggestedEntry: number;           // LTP or last close
  suggestedSL: number;              // ATR-based, floored at swing low
}
```

---

## UI Integration

The `TradePanel` component (`client/components/TradePanel.tsx`) consumes `AnalysisResult` and renders:

- **Verdict badge** with color coding (green/yellow/red)
- **Score and confidence** display
- **Indicator grid**: EMA trend, RSI zone, Volume ratio, VWAP position
- **Pattern chips** with bullish/bearish coloring
- **Reasons list** with +/- sentiment prefixes
- **Suggested SL** labeled "(ATR)" or "(swing)" based on data availability
- **Min profitable quantity** warning when position size is too small

The SL auto-populates the offset slider when in "auto" mode.
