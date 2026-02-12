"use client";

import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import DailyPicksTable from "@/components/DailyPicksTable";
import LiveIndicator from "@/components/LiveIndicator";
import { useTradeSettings } from "@/hooks/useTradeSettings";
import { analyzeCandles } from "@/lib/candleAnalysis";

interface DailyPick {
  symbol: string;
  name: string;
  ltp: number;
  open: number;
  day_change_pct: number;
  volume: number;
  turnover: number;
  fno_eligible: boolean;
  meets_gainer_criteria: boolean;
  meets_volume_leader_criteria: boolean;
  high_conviction: boolean;
  news_headline: string;
  news_link: string;
}

export interface RankedPick extends DailyPick {
  rank: number;
  tier: "hc" | "gainer" | "volume" | "other";
  analysisVerdict?: "BUY" | "WAIT" | "AVOID";
  analysisScore?: number;
}

interface Meta {
  total_instruments_scanned?: number;
  candidates_after_price_filter?: number;
  candidates_volume_enriched?: number;
  passes_gainer_criteria?: number;
  passes_volume_leader_criteria?: number;
  high_conviction_count?: number;
  fno_eligible_universe?: number;
  scan_time_seconds?: number;
  cache_active?: boolean;
  scan_timestamp?: string;
}

interface ScanProgress {
  current: number;
  total: number;
}

type Phase = "loading" | "snapshot" | "scanning" | "live";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DailyPicksPage() {
  const { smallCapitalMode } = useTradeSettings();
  const [candidates, setCandidates] = useState<DailyPick[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [scanProgress, setScanProgress] = useState<ScanProgress | null>(null);
  const [stage, setStage] = useState<string>("starting");
  const [lastLtpTime, setLastLtpTime] = useState<number | null>(null);
  const [flashSymbols, setFlashSymbols] = useState<Set<string>>(new Set());
  const [snapshotTime, setSnapshotTime] = useState<string | null>(null);
  const [showTradeableOnly, setShowTradeableOnly] = useState(false);
  const [analysisMap, setAnalysisMap] = useState<Record<string, { verdict: string; score: number; trend: string; rsi: number; volumeRatio: number }>>({});
  const [analysisPhase, setAnalysisPhase] = useState<"idle" | "running" | "done">("idle");

  const eventSourceRef = useRef<EventSource | null>(null);
  const liveSseRef = useRef<EventSource | null>(null);
  const flashTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const liveRetriesRef = useRef(0);
  const MAX_LIVE_RETRIES = 3;

  // Staleness timer — force re-render every 5s so LiveIndicator transitions
  const [, setTick] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 5000);
    return () => clearInterval(interval);
  }, []);

  const closeScanStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const closeLiveStream = useCallback(() => {
    if (liveSseRef.current) {
      liveSseRef.current.close();
      liveSseRef.current = null;
    }
  }, []);

  const closeAllStreams = useCallback(() => {
    closeScanStream();
    closeLiveStream();
    if (flashTimeoutRef.current) {
      clearTimeout(flashTimeoutRef.current);
      flashTimeoutRef.current = null;
    }
  }, [closeScanStream, closeLiveStream]);

  // Batch analysis: fetch 5min candles for top candidates and run analyzeCandles()
  // Prioritizes HC > gainer > volume tier stocks so they get analyzed first
  const runBatchAnalysis = useCallback(async (picks: DailyPick[]) => {
    setAnalysisPhase("running");

    // Sort by tier priority so we analyze the best candidates first
    const tierPriority = (c: DailyPick): number => {
      if (c.high_conviction) return 0;
      if (c.meets_gainer_criteria) return 1;
      if (c.meets_volume_leader_criteria) return 2;
      return 3;
    };
    const sorted = [...picks].sort((a, b) => tierPriority(a) - tierPriority(b));

    // Analyze all non-"other" tier stocks, plus top 10 "other" tier (max ~40)
    const nonOther = sorted.filter(c => tierPriority(c) < 3);
    const otherTop = sorted.filter(c => tierPriority(c) === 3).slice(0, 10);
    const top = [...nonOther, ...otherTop];

    const results: Record<string, { verdict: string; score: number; trend: string; rsi: number; volumeRatio: number }> = {};

    for (let i = 0; i < top.length; i += 5) {
      const batch = top.slice(i, i + 5);
      const promises = batch.map(async (c) => {
        try {
          const res = await fetch(`${API_URL}/api/candles/${encodeURIComponent(c.symbol)}?interval=5minute&days=2`);
          if (!res.ok) return;
          const data = await res.json();
          const candles = data.candles || [];
          if (candles.length >= 21) {
            const analysis = analyzeCandles(candles, c.ltp);
            results[c.symbol] = {
              verdict: analysis.verdict,
              score: analysis.score,
              trend: analysis.trend,
              rsi: analysis.rsi,
              volumeRatio: analysis.volumeRatio,
            };
          }
        } catch { /* skip failed */ }
      });
      await Promise.all(promises);
      setAnalysisMap(prev => ({ ...prev, ...results }));
    }
    setAnalysisPhase("done");
  }, []);

  // Phase 3: Start live LTP stream
  const startLiveStream = useCallback(() => {
    closeLiveStream();

    const es = new EventSource(`${API_URL}/api/daily-picks/live-ltp`);
    liveSseRef.current = es;
    setPhase("live");

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event_type !== "ltp_update") return;

        liveRetriesRef.current = 0;

        const updates: Record<string, { ltp: number; day_change_pct: number }> =
          data.updates;
        const timestamp: number = data.timestamp;

        setLastLtpTime(timestamp);

        // Flash symbols that changed
        const changedSymbols = new Set(Object.keys(updates));
        setFlashSymbols(changedSymbols);

        // Clear flash after 500ms
        if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
        flashTimeoutRef.current = setTimeout(() => {
          setFlashSymbols(new Set());
        }, 500);

        // Patch candidates with new LTP values
        setCandidates((prev) =>
          prev.map((c) => {
            const upd = updates[c.symbol];
            if (!upd) return c;
            const newLtp = upd.ltp;
            const newTurnover = c.volume > 0 ? round2(c.volume * newLtp) : c.turnover;
            return {
              ...c,
              ltp: newLtp,
              day_change_pct: upd.day_change_pct,
              turnover: newTurnover,
            };
          })
        );
      } catch {
        // Ignore malformed messages
      }
    };

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) return;
      closeLiveStream();

      liveRetriesRef.current += 1;
      if (liveRetriesRef.current > MAX_LIVE_RETRIES) {
        setPhase("snapshot");
        setError("Live updates unavailable. Click Refresh to retry.");
        return;
      }

      setTimeout(() => {
        startLiveStream();
      }, 5000);
    };
  }, [closeLiveStream]);

  // Phase 2: SSE scan
  const startScan = useCallback(() => {
    closeScanStream();
    closeLiveStream();
    setPhase("scanning");
    setError(null);
    setScanProgress(null);
    setStage("starting");

    const es = new EventSource(`${API_URL}/api/daily-picks/stream`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.event_type === "error") {
          setError(data.message || "Stream error");
          setPhase("snapshot");
          closeScanStream();
          return;
        }

        if (data.candidates) {
          setCandidates(data.candidates);
        }

        if (data.meta) {
          setMeta((prev) => (prev ? { ...prev, ...data.meta } : data.meta));
        }

        if (data.progress) {
          setScanProgress(data.progress);
        }

        if (data.event_type === "batch") {
          setStage("ohlc");
        } else if (data.event_type === "stage_complete" && data.stage === "ohlc") {
          setStage("volume");
          setScanProgress(null);
        } else if (data.event_type === "stage_complete" && data.stage === "volume") {
          setStage("news");
        } else if (data.event_type === "complete") {
          setStage("done");
          closeScanStream();
          // Run candle analysis on top candidates
          if (data.candidates && data.candidates.length > 0) {
            runBatchAnalysis(data.candidates);
          }
          // Transition to phase 3: live LTP
          startLiveStream();
        }
      } catch {
        // Ignore malformed messages
      }
    };

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) return;
      setError("Connection to scanner lost. Try refreshing.");
      setPhase(candidates.length > 0 ? "snapshot" : "loading");
      closeScanStream();
    };
  }, [closeScanStream, closeLiveStream, startLiveStream, runBatchAnalysis, candidates.length]);

  // Refresh button: close live stream -> restart scan -> transitions back to live
  const handleRefresh = useCallback(() => {
    closeAllStreams();
    liveRetriesRef.current = 0;
    setLastLtpTime(null);
    setFlashSymbols(new Set());
    setSnapshotTime(null);
    setAnalysisMap({});
    setAnalysisPhase("idle");
    startScan();
  }, [closeAllStreams, startScan]);

  // Phase 1: Load snapshot on mount, then start scan
  useEffect(() => {
    let cancelled = false;

    async function init() {
      let snapshotSavedAt: number | null = null;
      let snapshotCandidates: DailyPick[] = [];
      try {
        const res = await fetch(`${API_URL}/api/daily-picks/snapshot`);
        if (!res.ok) throw new Error("Snapshot fetch failed");
        const data = await res.json();

        if (!cancelled && data.candidates && data.candidates.length > 0) {
          snapshotCandidates = data.candidates;
          setCandidates(data.candidates);
          if (data.meta) setMeta(data.meta);
          if (data.saved_at) {
            snapshotSavedAt = data.saved_at;
            const d = new Date(data.saved_at * 1000);
            setSnapshotTime(
              d.toLocaleTimeString("en-IN", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })
            );
          }
          setStage("done");
          setPhase("snapshot");
        }
      } catch {
        // Snapshot not available — proceed to scan
      }

      if (!cancelled) {
        const ageSeconds = snapshotSavedAt
          ? (Date.now() / 1000) - snapshotSavedAt
          : Infinity;
        if (ageSeconds > 300) {
          startScan();
        } else {
          // Snapshot is fresh — run analysis on it and start live LTP
          if (snapshotCandidates.length > 0) {
            runBatchAnalysis(snapshotCandidates);
          }
          startLiveStream();
        }
      }
    }

    init();

    return () => {
      cancelled = true;
      closeAllStreams();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Unified ranking: HC > Gainer > Volume Leader > Other, each sub-sorted
  // When analysis results are available, BUY verdicts sort first within each tier
  const rankedCandidates = useMemo((): RankedPick[] => {
    if (candidates.length === 0) return [];

    const hc: DailyPick[] = [];
    const gainers: DailyPick[] = [];
    const volumeLeaders: DailyPick[] = [];
    const other: DailyPick[] = [];

    for (const c of candidates) {
      if (c.high_conviction) {
        hc.push(c);
      } else if (c.meets_gainer_criteria) {
        gainers.push(c);
      } else if (c.meets_volume_leader_criteria) {
        volumeLeaders.push(c);
      } else {
        other.push(c);
      }
    }

    const hasAnalysis = Object.keys(analysisMap).length > 0;

    // Verdict priority: BUY=0, WAIT=1, unanalyzed=2, AVOID=3
    const verdictPriority = (symbol: string): number => {
      const a = analysisMap[symbol];
      if (!a) return 2; // unanalyzed sorts below WAIT
      if (a.verdict === "BUY") return 0;
      if (a.verdict === "WAIT") return 1;
      return 3; // AVOID
    };

    const sortWithAnalysis = (arr: DailyPick[], fallbackSort: (a: DailyPick, b: DailyPick) => number) => {
      if (!hasAnalysis) {
        arr.sort(fallbackSort);
        return;
      }
      arr.sort((a, b) => {
        const vp = verdictPriority(a.symbol) - verdictPriority(b.symbol);
        if (vp !== 0) return vp;
        // Within same verdict: sort by analysis score desc, then fallback
        const aScore = analysisMap[a.symbol]?.score ?? -999;
        const bScore = analysisMap[b.symbol]?.score ?? -999;
        if (aScore !== bScore) return bScore - aScore;
        return fallbackSort(a, b);
      });
    };

    sortWithAnalysis(hc, (a, b) => b.day_change_pct - a.day_change_pct);
    sortWithAnalysis(gainers, (a, b) => b.day_change_pct - a.day_change_pct);
    sortWithAnalysis(volumeLeaders, (a, b) => b.turnover - a.turnover);
    sortWithAnalysis(other, (a, b) => b.day_change_pct - a.day_change_pct);

    const ranked: RankedPick[] = [];
    let rank = 1;

    const annotate = (c: DailyPick, tier: RankedPick["tier"]): RankedPick => {
      const a = analysisMap[c.symbol];
      return {
        ...c,
        rank: rank++,
        tier,
        analysisVerdict: a?.verdict as RankedPick["analysisVerdict"],
        analysisScore: a?.score,
      };
    };

    for (const c of hc) ranked.push(annotate(c, "hc"));
    for (const c of gainers) ranked.push(annotate(c, "gainer"));
    for (const c of volumeLeaders) ranked.push(annotate(c, "volume"));
    for (const c of other) ranked.push(annotate(c, "other"));

    return ranked;
  }, [candidates, analysisMap]);

  const hasCandidates = candidates.length > 0;
  const isScanning = phase === "scanning";

  const progressLabel = useMemo(() => {
    if (stage === "starting") return "Starting scan...";
    if (stage === "ohlc" && scanProgress) {
      const pct = Math.round((scanProgress.current / scanProgress.total) * 100);
      return `Batch ${scanProgress.current}/${scanProgress.total} (${pct}%)`;
    }
    if (stage === "volume") return "Enriching volume...";
    if (stage === "news") return "Fetching news...";
    return "";
  }, [stage, scanProgress]);

  const progressPct = useMemo(() => {
    if (!scanProgress) return 0;
    return Math.round((scanProgress.current / scanProgress.total) * 100);
  }, [scanProgress]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
      <header className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
            Daily Picks
          </h1>
          {phase === "live" && <LiveIndicator lastUpdateTime={lastLtpTime} />}
          {phase === "snapshot" && snapshotTime && (
            <span className="text-xs text-gray-400 dark:text-gray-500">
              Snapshot from {snapshotTime}
            </span>
          )}
          {meta?.high_conviction_count != null && meta.high_conviction_count > 0 && (
            <span className="text-xs text-amber-600 dark:text-amber-400">
              {meta.high_conviction_count} HC
            </span>
          )}
          {smallCapitalMode && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700 dark:bg-amber-900 dark:text-amber-300">
              Small Capital
            </span>
          )}
          {analysisPhase === "running" && (
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-green-300 border-t-green-600" />
              <span className="text-xs text-green-700 dark:text-green-300">
                Analyzing signals...
              </span>
            </div>
          )}
          {analysisPhase === "done" && (
            <span className="text-xs text-green-600 dark:text-green-400">
              {Object.values(analysisMap).filter(a => a.verdict === "BUY").length} BUY signals
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* Tradeable only filter */}
          {smallCapitalMode && (
            <button
              onClick={() => setShowTradeableOnly(!showTradeableOnly)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                showTradeableOnly
                  ? "bg-green-600 text-white"
                  : "border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
              }`}
            >
              Tradeable only
            </button>
          )}
          {/* Inline scan progress */}
          {isScanning && hasCandidates && (
            <div className="flex items-center gap-2">
              <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-blue-300 border-t-blue-600" />
              <span className="text-xs text-blue-700 dark:text-blue-300">
                {progressLabel}
              </span>
              {scanProgress && (
                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-blue-200 dark:bg-blue-800">
                  <div
                    className="h-full rounded-full bg-blue-600 transition-all duration-300"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
              )}
            </div>
          )}
          <button
            onClick={handleRefresh}
            disabled={isScanning}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {isScanning ? "Scanning..." : "Refresh"}
          </button>
        </div>
      </header>

      {phase === "loading" && !hasCandidates && (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600" />
          <span className="ml-3 text-gray-500">Loading...</span>
        </div>
      )}

      {isScanning && !hasCandidates && (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600" />
          <span className="ml-3 text-gray-500">{progressLabel}</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-800 dark:bg-red-950">
          <h2 className="text-lg font-semibold text-red-800 dark:text-red-200">
            Scanner Error
          </h2>
          <p className="mt-2 text-red-600 dark:text-red-400">{error}</p>
          <p className="mt-4 text-sm text-red-500 dark:text-red-400">
            Make sure the backend is running at {API_URL} and your API
            credentials are configured in{" "}
            <code className="rounded bg-red-100 px-1 dark:bg-red-900">
              server/.env
            </code>
            .
          </p>
        </div>
      )}

      {hasCandidates && (
        <DailyPicksTable
          results={rankedCandidates}
          stage={stage}
          flashSymbols={flashSymbols}
          smallCapitalMode={smallCapitalMode}
          showTradeableOnly={showTradeableOnly}
          analysisPhase={analysisPhase}
        />
      )}
    </div>
  );
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}
