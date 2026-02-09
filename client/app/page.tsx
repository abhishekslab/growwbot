"use client";

import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import DailyPicksMeta from "@/components/DailyPicksMeta";
import DailyPicksTable from "@/components/DailyPicksTable";
import CacheStatus from "@/components/CacheStatus";
import LiveIndicator from "@/components/LiveIndicator";

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
type Tab = "high_conviction" | "gainers" | "volume_leaders";

const tabs: { key: Tab; label: string }[] = [
  { key: "high_conviction", label: "High Conviction" },
  { key: "gainers", label: "Top Gainers" },
  { key: "volume_leaders", label: "Volume Leaders" },
];

function criteriaKeyForTab(tab: Tab): keyof DailyPick {
  if (tab === "gainers") return "meets_gainer_criteria";
  if (tab === "volume_leaders") return "meets_volume_leader_criteria";
  return "high_conviction";
}

function sortKeyForTab(tab: Tab): keyof DailyPick {
  if (tab === "volume_leaders") return "turnover";
  return "day_change_pct";
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DailyPicksPage() {
  const [candidates, setCandidates] = useState<DailyPick[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [scanProgress, setScanProgress] = useState<ScanProgress | null>(null);
  const [stage, setStage] = useState<string>("starting");
  const [activeTab, setActiveTab] = useState<Tab>("gainers");
  const [lastLtpTime, setLastLtpTime] = useState<number | null>(null);
  const [flashSymbols, setFlashSymbols] = useState<Set<string>>(new Set());
  const [snapshotTime, setSnapshotTime] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const liveSseRef = useRef<EventSource | null>(null);
  const flashTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
      // Auto-reconnect after 5s
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
  }, [closeScanStream, closeLiveStream, startLiveStream, candidates.length]);

  // Refresh button: close live stream -> restart scan -> transitions back to live
  const handleRefresh = useCallback(() => {
    closeAllStreams();
    setLastLtpTime(null);
    setFlashSymbols(new Set());
    setSnapshotTime(null);
    startScan();
  }, [closeAllStreams, startScan]);

  // Phase 1: Load snapshot on mount, then start scan
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const res = await fetch(`${API_URL}/api/daily-picks/snapshot`);
        if (!res.ok) throw new Error("Snapshot fetch failed");
        const data = await res.json();

        if (!cancelled && data.candidates && data.candidates.length > 0) {
          setCandidates(data.candidates);
          if (data.meta) setMeta(data.meta);
          if (data.saved_at) {
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
        startScan();
      }
    }

    init();

    return () => {
      cancelled = true;
      closeAllStreams();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sortedCandidates = useMemo(() => {
    if (candidates.length === 0) return [];
    const sk = sortKeyForTab(activeTab);
    return [...candidates].sort(
      (a, b) => (b[sk] as number) - (a[sk] as number)
    );
  }, [candidates, activeTab]);

  const getTabPassCount = (tab: Tab): number => {
    const ck = criteriaKeyForTab(tab);
    return candidates.filter((c) => c[ck]).length;
  };

  const hasCandidates = candidates.length > 0;
  const isScanning = phase === "scanning";

  const progressLabel = useMemo(() => {
    if (stage === "starting") return "Starting scan...";
    if (stage === "ohlc" && scanProgress) {
      const pct = Math.round((scanProgress.current / scanProgress.total) * 100);
      return `Scanning batch ${scanProgress.current} of ${scanProgress.total} (${pct}%)`;
    }
    if (stage === "volume") return "Enriching volume data...";
    if (stage === "news") return "Fetching news...";
    return "";
  }, [stage, scanProgress]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            Daily Picks
          </h1>
          <p className="mt-1 flex items-center gap-3 text-gray-500 dark:text-gray-400">
            <span>
              Multi-strategy scanner: quality gainers, volume leaders, and
              high-conviction F&amp;O picks
            </span>
            {phase === "live" && <LiveIndicator lastUpdateTime={lastLtpTime} />}
            {phase === "snapshot" && snapshotTime && (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                Snapshot from {snapshotTime}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isScanning}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {isScanning ? "Scanning..." : "Refresh"}
        </button>
      </header>

      <div className="mb-6">
        <CacheStatus />
      </div>

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

      {isScanning && hasCandidates && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 dark:border-blue-800 dark:bg-blue-950">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-300 border-t-blue-600" />
          <span className="text-sm text-blue-700 dark:text-blue-300">
            {progressLabel}
          </span>
          {scanProgress && (
            <div className="ml-auto h-2 w-32 overflow-hidden rounded-full bg-blue-200 dark:bg-blue-800">
              <div
                className="h-full rounded-full bg-blue-600 transition-all duration-300"
                style={{
                  width: `${Math.round(
                    (scanProgress.current / scanProgress.total) * 100
                  )}%`,
                }}
              />
            </div>
          )}
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
        <div className="space-y-8">
          {meta && <DailyPicksMeta meta={meta} stage={stage} />}

          <div className="border-b border-gray-200 dark:border-gray-800">
            <nav className="-mb-px flex gap-4">
              {tabs.map((tab) => {
                const active = activeTab === tab.key;
                const passCount = getTabPassCount(tab.key);
                const totalCount = candidates.length;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`whitespace-nowrap border-b-2 px-1 py-3 text-sm font-medium ${
                      active
                        ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                        : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                    }`}
                  >
                    {tab.label}
                    <span
                      className={`ml-2 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        active
                          ? "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300"
                          : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                      }`}
                    >
                      {passCount}/{totalCount}
                    </span>
                  </button>
                );
              })}
            </nav>
          </div>

          <DailyPicksTable
            results={sortedCandidates}
            criteriaKey={criteriaKeyForTab(activeTab)}
            stage={stage}
            flashSymbols={flashSymbols}
          />
        </div>
      )}
    </div>
  );
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}
