"use client";

import { useState, useEffect, useRef, useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Instrument {
  trading_symbol: string;
  groww_symbol: string;
  name: string;
  segment: string;
  exchange: string;
  exchange_token: string;
  expiry_date?: string;
  strike_price?: number;
  instrument_type?: string;
  underlying_symbol?: string;
}

interface SymbolSearchProps {
  value: string;
  onChange: (growwSymbol: string) => void;
  segment: "CASH" | "FNO";
  disabled?: boolean;
}

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

// Local storage hook for recent searches
function useRecentSearches(segment: "CASH" | "FNO"): [string[], (symbol: string) => void] {
  const [recents, setRecents] = useState<string[]>([]);

  useEffect(() => {
    const key = `recent_symbols_${segment}`;
    const stored = localStorage.getItem(key);
    if (stored) {
      try {
        setRecents(JSON.parse(stored));
      } catch {
        setRecents([]);
      }
    }
  }, [segment]);

  const addRecent = useCallback(
    (symbol: string) => {
      const key = `recent_symbols_${segment}`;
      setRecents((prev) => {
        const newRecents = [symbol, ...prev.filter((s) => s !== symbol)].slice(0, 5);
        localStorage.setItem(key, JSON.stringify(newRecents));
        return newRecents;
      });
    },
    [segment],
  );

  return [recents, addRecent];
}

export default function SymbolSearch({
  value,
  onChange,
  segment,
  disabled = false,
}: SymbolSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Instrument[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [recentSearches, addRecentSearch] = useRecentSearches(segment);
  const abortControllerRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const debouncedQuery = useDebounce(query, 300);

  // Fetch search results
  useEffect(() => {
    if (debouncedQuery.length < 2) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    setLoading(true);
    setError(null);

    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    fetch(
      `${API_URL}/api/instruments/search?q=${encodeURIComponent(
        debouncedQuery,
      )}&segment=${segment}&limit=20`,
      {
        signal: abortControllerRef.current.signal,
      },
    )
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setResults(data.instruments || []);
        setIsOpen(true);
        setSelectedIndex(-1);
      })
      .catch((e) => {
        if (e.name !== "AbortError") {
          setError("Search failed");
          console.error("Symbol search error:", e);
        }
      })
      .finally(() => setLoading(false));

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [debouncedQuery, segment]);

  // Handle click outside to close dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Format display text for an instrument
  const formatDisplayText = (inst: Instrument): string => {
    if (segment === "FNO") {
      const parts = [inst.trading_symbol];
      if (inst.instrument_type) parts.push(inst.instrument_type);
      if (inst.expiry_date) {
        const date = new Date(inst.expiry_date);
        parts.push(date.toLocaleDateString("en-IN", { month: "short", day: "numeric" }));
      }
      if (inst.strike_price && inst.strike_price > 0) {
        parts.push(inst.strike_price.toString());
      }
      return parts.join(" ");
    }
    return inst.trading_symbol;
  };

  // Handle selection
  const handleSelect = (inst: Instrument) => {
    onChange(inst.groww_symbol);
    setQuery(inst.trading_symbol);
    setIsOpen(false);
    addRecentSearch(inst.groww_symbol);
  };

  // Handle input change
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    if (e.target.value === "") {
      onChange("");
    }
  };

  // Handle focus - show recent searches
  const handleFocus = () => {
    if (query.length < 2 && recentSearches.length > 0) {
      // Load recent searches as results
      Promise.all(
        recentSearches.map((symbol) =>
          fetch(
            `${API_URL}/api/instruments/search?q=${encodeURIComponent(
              symbol,
            )}&segment=${segment}&limit=1`,
          ).then((r) => r.json()),
        ),
      )
        .then((results) => {
          const instruments = results.map((r) => r.instruments?.[0]).filter(Boolean);
          setResults(instruments);
          setIsOpen(true);
        })
        .catch(() => {
          // Silently fail for recents
        });
    }
  };

  return (
    <div className="relative">
      <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">
        Symbol
      </label>
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query || value}
          onChange={handleInputChange}
          onFocus={handleFocus}
          disabled={disabled}
          placeholder={
            segment === "CASH" ? "Search stocks (e.g., RELIANCE)" : "Search FNO (e.g., NIFTY)"
          }
          className="w-full rounded border border-gray-300 bg-white px-3 py-2 pr-10 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
        />
        {loading && (
          <div className="absolute top-1/2 right-3 -translate-y-1/2">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
          </div>
        )}
      </div>

      {isOpen && (results.length > 0 || error) && (
        <div
          ref={dropdownRef}
          className="absolute z-10 mt-1 max-h-72 w-full overflow-auto rounded-md border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-800"
        >
          {error ? (
            <div className="px-3 py-2 text-sm text-red-600 dark:text-red-400">{error}</div>
          ) : (
            <>
              {query.length < 2 && recentSearches.length > 0 && (
                <div className="px-3 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">
                  Recent
                </div>
              )}
              <ul className="py-1">
                {results.map((inst, index) => (
                  <li
                    key={inst.exchange_token}
                    onClick={() => handleSelect(inst)}
                    className={`cursor-pointer px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 ${
                      index === selectedIndex ? "bg-blue-50 dark:bg-blue-900/20" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-gray-900 dark:text-gray-100">
                        {formatDisplayText(inst)}
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {inst.segment}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{inst.name}</div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
