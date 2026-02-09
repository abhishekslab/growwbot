# Candlestick Analysis Engine

Technical documentation for the client-side analysis engine added to the symbol page TradePanel.

## Overview

The engine reads 5-minute candles already loaded by the symbol page, runs EMA/RSI/volume/pattern analysis entirely on the client, and produces a BUY/WAIT/AVOID verdict with auto-suggested entry, stop-loss, and minimum profitable quantity. All values pre-populate the TradePanel form.

**Files:**
- `client/lib/candleAnalysis.ts` — Pure utility module, no React dependencies
- `client/components/TradePanel.tsx` — Signal card UI, auto-SL, min qty warning
- `client/app/symbol/[symbol]/page.tsx` — Passes `candles` prop to TradePanel

## Design Decisions

### 1. Client-side only (no backend)

**Decision:** All analysis runs in the browser via `useMemo`.

**Why:** The candle data is already fetched for the chart. Running analysis client-side avoids an extra API round-trip, keeps the backend stateless, and means the analysis re-computes instantly when LTP changes via WebSocket. The dataset is small (~96 candles for 2 days of 5-min bars), so computation is negligible.

**Tradeoff:** No server-side caching or sharing of analysis results. If we later want to alert on signals across all stocks (not just the one being viewed), this would need to move server-side.

### 2. Minimum 21 candles required

**Decision:** Return a neutral "insufficient data" result if fewer than 21 candles are available.

**Why:** EMA-21 needs 21 data points to produce its first value. RSI-14 needs 15. Rather than show partially computed indicators that could mislead, we gate the entire analysis on the longest dependency (EMA-21). This means the analysis won't appear if the market just opened and only a few candles exist.

**Tradeoff:** Users see "Need 21+ candles for analysis" for roughly the first 105 minutes of a trading day (21 x 5min). We accepted this because showing unreliable signals early in the session is worse than showing nothing.

### 3. Composite scoring system (-100 to +100)

**Decision:** Each factor contributes a fixed score, clamped to [-100, +100], with threshold-based verdict.

| Factor | Score Range |
|--------|-------------|
| EMA trend (9 vs 21) | +/-25 |
| Recent EMA crossover | +10 |
| RSI zones | -20 to +20 |
| Volume ratio | -10 to +15 |
| Candlestick patterns | -25 to +25 each |

**Verdict thresholds:** >= 30 BUY, >= -10 WAIT, < -10 AVOID

**Why:** Simple additive scoring is transparent and debuggable. Every reason that contributed to the score is listed in the UI, so the user can see *why* the engine recommends what it does. Weighted ML models would be opaque.

**Tradeoff:** Fixed scores don't adapt to different stock behaviors. A high-beta stock might trigger AVOID on RSI-72 when it regularly trades at RSI 65-80. We chose simplicity over per-stock calibration since this is a decision *aid*, not an auto-trader.

### 4. Pattern detection: last 5 candles only

**Decision:** Only scan the most recent 5 candles for candlestick patterns.

**Patterns detected:**
- Bullish/Bearish Engulfing (+/-20)
- Hammer/Shooting Star (+/-15)
- Morning/Evening Star (+/-25)

**Why:** On 5-minute charts, patterns older than 25 minutes are stale. Limiting to 5 candles keeps the scan fast and relevant. Morning/Evening Star is the most complex (3-candle pattern) and gets the highest score because it's the most reliable reversal signal.

**Tradeoff:** We miss patterns that formed 6+ candles ago. We also don't detect continuation patterns (three white soldiers, rising three methods) or indecision patterns (doji sequences). These were omitted to keep the initial implementation focused — they can be added later without changing the scoring framework.

### 5. Stop-loss from swing low, not fixed percentage

**Decision:** Default SL is the lowest low of the last 10 candles (swing low), not the previous fixed 2% offset.

**Why:** A percentage-based SL ignores market structure. If the stock has been consolidating in a tight range, 2% might be far too wide. If it just had a big move, 2% might be too tight. Swing low places the SL below a level the market has already respected.

**Tradeoff:** Swing low can produce very tight SLs in low-volatility periods (< 0.3% from entry). We handle this with a floor: if the swing low is within 0.3% of entry, we widen to 1% (`entry * 0.99`). The SL auto-populates but doesn't lock — users can override by dragging the slider, which switches to manual mode. A "Reset to suggested" link restores auto mode.

### 6. Minimum profitable quantity

**Decision:** Iterate quantity from 1 upward until net profit at a naive 1:2 target exceeds zero after all fees (brokerage, STT, exchange txn, SEBI, stamp duty, GST).

**Why:** Indian exchange fees have significant fixed components (especially the flat brokerage per order). For low-priced stocks with tight SLs, even a 1:2 R:R trade can be net-negative after fees if the quantity is too small. Showing this number prevents the user from entering trades that are structurally unprofitable.

**Tradeoff:** The calculation uses a naive 1:2 target (not the fee-adjusted target from `calculateFeeAdjustedTarget`), so it's a conservative estimate. We cap the search at qty 10,000 and return -1 if no profitable quantity exists, which would indicate the trade is not viable at any reasonable size.

### 7. Auto vs manual SL mode

**Decision:** Two modes for SL: `auto` (swing low) and `manual` (user-dragged slider).

**Why:** The analysis should inform, not dictate. If the user has context the engine doesn't (news, sector rotation, support levels from daily charts), they should be able to override. The mode split lets the engine keep updating the SL as new candles arrive (every 5 min refresh) while in auto mode, but freezes when the user takes manual control.

**Tradeoff:** The SL slider has discrete 0.5% steps (range 0.5%-10%), so the auto-populated value is rounded to the nearest step. This means the actual SL price may differ slightly from the exact swing low. We accepted this because the slider UX is more important than sub-tick precision for a delivery trade.

### 8. RSI: Wilder's smoothing, period 14

**Decision:** Standard RSI-14 with Wilder's smoothing (exponential moving average of gains/losses).

**Why:** RSI-14 is the most widely used momentum oscillator. Wilder's smoothing (as opposed to simple average) gives more weight to recent price action, which matters on 5-minute charts where conditions change fast.

**Scoring:**
- < 30 (oversold): +20 — potential bounce
- 30-50 (weak): -5 — mild bearish bias
- 50-70 (healthy): +10 — bullish momentum
- > 70 (overbought): -20 — potential reversal

**Tradeoff:** RSI can stay overbought/oversold for extended periods in strong trends. The -20 penalty for RSI > 70 could cause the engine to say WAIT/AVOID on a stock that's in a strong breakout. We mitigate this by having EMA trend (+25) and volume (+15) potentially outweigh the RSI penalty.

### 9. EMA 9/21 (not SMA, not 12/26)

**Decision:** EMA-9 and EMA-21 for trend detection, not SMA, and not the classic 12/26 MACD pair.

**Why:** EMAs react faster than SMAs to price changes, which matters on 5-minute charts. The 9/21 pair is tighter than 12/26, giving earlier signals. On intraday timeframes, waiting for 12/26 crossovers often means the move is mostly over.

**Tradeoff:** Faster signals mean more false signals (whipsaws). The crossover bonus (+10) is intentionally small compared to the trend score (+25) so that a single crossover doesn't dominate the verdict.

## Architecture Notes

### Data flow

```
Symbol page loads candles (2 days, 5-min)
  → CandlestickChart renders them
  → TradePanel receives candles + LTP as props
    → useMemo calls analyzeCandles(candles, ltp)
    → Signal card renders analysis result
    → Auto-SL useEffect sets slider from suggestedSL
    → Position sizing and fee calculation use the SL
```

### Re-computation triggers

- **Candles refresh** (every 5 min via `setInterval`): `useMemo` dependency on `candles` re-runs analysis
- **LTP update** (WebSocket, sub-second): `useMemo` dependency on `ltp` re-runs analysis. Only `suggestedEntry` changes; indicators stay the same since candles haven't changed
- **SL slider drag**: Switches to manual mode, no re-analysis

### No external dependencies

The analysis engine uses zero npm packages. All indicator calculations (EMA, RSI, volume SMA, pattern matching) are hand-rolled in ~270 lines. This avoids pulling in heavy TA libraries (like `technicalindicators` at 200KB+) for 6 indicators.

## Future Improvements

- **MACD histogram** for momentum confirmation
- **Bollinger Bands** for volatility-based entry/SL
- **Per-stock calibration** of RSI zones based on historical behavior
- **Multi-timeframe analysis** (15min/1hr candles for trend, 5min for entry)
- **Server-side scanning** to generate alerts across all daily picks, not just the viewed stock
- **Backtesting** the scoring system against historical data to tune weights
