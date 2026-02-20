"""
Stock screener pipeline — scans NSE equities for day-trading candidates.

Includes the original screener (aggressive filters) and a new Daily Picks
multi-strategy scanner that reliably returns tradeable stocks every day.
Uses only stdlib for news/RSS (no new pip dependencies).
"""

import logging
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stage 1 — Batch OHLC: price range + day-change filter
# ---------------------------------------------------------------------------

def _batch_ohlc(groww, instruments_df, batch_size=50, sleep_between=0.1, cache=None,
                min_day_change=10.0, price_range=(100, 2000)):
    """Fetch OHLC + LTP in batches and return survivors with price/change data."""
    symbols = instruments_df["trading_symbol"].tolist()
    survivors = []
    total = len(symbols)
    min_price, max_price = price_range

    for i in range(0, total, batch_size):
        raw_batch = symbols[i : i + batch_size]
        # API requires NSE_SYMBOL format for exchange_trading_symbols
        batch = tuple(f"NSE_{s}" for s in raw_batch)

        # Fetch OHLC (open/high/low/close)
        if cache:
            try:
                ohlc = cache.get_ohlc_batch(groww, batch)
            except Exception as e:
                logger.warning("OHLC batch %d failed: %s", i, e)
                ohlc = {}
        else:
            retries = 0
            while retries < 3:
                try:
                    ohlc = groww.get_ohlc(
                        exchange_trading_symbols=batch, segment="CASH"
                    )
                    break
                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str or "rate" in err_str.lower():
                        retries += 1
                        time.sleep(0.5 * (2 ** retries))
                        continue
                    logger.warning("OHLC batch %d failed: %s", i, e)
                    ohlc = {}
                    break
            else:
                logger.warning("OHLC batch %d exhausted retries", i)
                ohlc = {}

        if not isinstance(ohlc, dict):
            continue

        # Fetch LTP for the same batch (separate API — OHLC has no ltp)
        ltp_map = {}
        try:
            ltp_data = groww.get_ltp(
                exchange_trading_symbols=batch, segment="CASH"
            )
            if isinstance(ltp_data, dict):
                for key, val in ltp_data.items():
                    if isinstance(val, dict):
                        ltp_map[key] = float(val.get("ltp", 0))
                    else:
                        ltp_map[key] = float(val)
        except Exception as e:
            logger.warning("LTP batch %d failed: %s", i, e)

        for sym in raw_batch:
            es = f"NSE_{sym}"
            data = ohlc.get(es)
            if not data or not isinstance(data, dict):
                continue
            try:
                open_price = float(data.get("open", 0))
            except (TypeError, ValueError):
                continue

            ltp = ltp_map.get(es, 0)

            if open_price <= 0 or ltp <= 0:
                continue
            if not (min_price <= ltp <= max_price):
                continue

            day_change_pct = ((ltp - open_price) / open_price) * 100
            if day_change_pct < min_day_change:
                continue

            # Look up name from instruments dataframe
            name_rows = instruments_df.loc[
                instruments_df["trading_symbol"] == sym, "name"
            ]
            name = name_rows.iloc[0] if len(name_rows) > 0 else sym
            if not isinstance(name, str) or not name.strip():
                name = sym

            survivors.append(
                {
                    "symbol": sym,
                    "name": name,
                    "ltp": round(ltp, 2),
                    "open": round(open_price, 2),
                    "day_change_pct": round(day_change_pct, 2),
                }
            )

        time.sleep(sleep_between)

    return survivors


# ---------------------------------------------------------------------------
# Stage 2 — Volume filter (5x relative volume)
# ---------------------------------------------------------------------------

def _fetch_volume(groww, symbol, cache=None):
    """Return (today_volume, avg_volume) for a symbol, or None on failure."""
    try:
        quote = groww.get_quote(symbol, "NSE", "CASH")
        today_volume = float(quote.get("volume", 0) if isinstance(quote, dict) else 0)
    except Exception:
        return None

    avg_volume = 0
    try:
        # Groww symbol may differ from trading symbol; try same value
        end = datetime.now()
        start = end - timedelta(days=30)
        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")
        if cache:
            candles = cache.get_historical_candles(groww, symbol, start_str, end_str)
        else:
            candles = groww.get_historical_candles(
                "NSE", "CASH", symbol, start_str, end_str, "1day"
            )
        volumes = []
        if isinstance(candles, list):
            for c in candles:
                v = c.get("volume", 0) if isinstance(c, dict) else 0
                if v:
                    volumes.append(float(v))
        elif isinstance(candles, dict):
            for c in candles.get("candles", candles.get("data", [])):
                v = c.get("volume", 0) if isinstance(c, dict) else 0
                if v:
                    volumes.append(float(v))

        # Take up to last 20 sessions (exclude today if present)
        if len(volumes) > 1:
            volumes = volumes[-21:-1]  # last 20 before today
        avg_volume = sum(volumes) / len(volumes) if volumes else 0
    except Exception:
        pass  # keep avg_volume=0; still return today_volume

    return today_volume, avg_volume


def _volume_filter(groww, candidates, min_relative_volume=5.0, cache=None):
    """Keep candidates with today_volume / avg_volume >= threshold."""
    survivors = []

    with ThreadPoolExecutor(max_workers=5) as pool:
        future_to_cand = {
            pool.submit(_fetch_volume, groww, c["symbol"], cache): c for c in candidates
        }
        for future in as_completed(future_to_cand):
            cand = future_to_cand[future]
            try:
                result = future.result()
            except Exception:
                continue
            if result is None:
                continue
            today_vol, avg_vol = result
            if avg_vol <= 0:
                continue
            rel_vol = today_vol / avg_vol
            if rel_vol >= min_relative_volume:
                cand["volume"] = int(today_vol)
                cand["avg_volume"] = int(avg_vol)
                cand["relative_volume"] = round(rel_vol, 2)
                survivors.append(cand)

    return survivors


# ---------------------------------------------------------------------------
# Stage 3 — News filter (recent catalyst via Google News RSS)
# ---------------------------------------------------------------------------

def _fetch_news(name):
    """Return (headline, link) if a news article within 48h exists, else None."""
    try:
        query = urllib.request.quote(f"{name} stock india")
        url = (
            f"https://news.google.com/rss/search?q={query}"
            "&hl=en-IN&gl=IN&ceid=IN:en"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        cutoff = datetime.now() - timedelta(hours=48)

        for item in root.iter("item"):
            pub_date_el = item.find("pubDate")
            title_el = item.find("title")
            link_el = item.find("link")
            if pub_date_el is None or pub_date_el.text is None:
                continue
            try:
                pub_dt = parsedate_to_datetime(pub_date_el.text).replace(tzinfo=None)
            except Exception:
                continue
            if pub_dt >= cutoff:
                headline = title_el.text if title_el is not None and title_el.text else ""
                link = link_el.text if link_el is not None and link_el.text else ""
                return headline, link

    except Exception:
        pass
    return None


def _news_filter(candidates, cache=None):
    """Keep candidates with at least one recent news article."""
    survivors = []

    def _get_news(name):
        if cache:
            return cache.get_news(name, _fetch_news)
        return _fetch_news(name)

    with ThreadPoolExecutor(max_workers=10) as pool:
        future_to_cand = {
            pool.submit(_get_news, c["name"]): c for c in candidates
        }
        for future in as_completed(future_to_cand):
            cand = future_to_cand[future]
            try:
                result = future.result()
            except Exception:
                continue
            if result is None:
                continue
            headline, link = result
            cand["news_headline"] = headline
            cand["news_link"] = link
            survivors.append(cand)

    return survivors


# ---------------------------------------------------------------------------
# Stage 4 — Float filter (skip if data unavailable)
# ---------------------------------------------------------------------------

def _float_filter(instruments_df, candidates):
    """Filter by low float if the column exists. Returns (survivors, available)."""
    float_col = None
    for col_name in ("float", "free_float", "shares_outstanding"):
        if col_name in instruments_df.columns:
            float_col = col_name
            break

    if float_col is None:
        for c in candidates:
            c["float_shares"] = None
        return candidates, False

    symbol_float = dict(
        zip(instruments_df["trading_symbol"], instruments_df[float_col])
    )
    survivors = []
    for c in candidates:
        val = symbol_float.get(c["symbol"])
        if val is not None:
            try:
                val = float(val)
            except (TypeError, ValueError):
                c["float_shares"] = None
                survivors.append(c)
                continue
            c["float_shares"] = int(val)
            if val < 10_000_000:
                survivors.append(c)
        else:
            c["float_shares"] = None
            survivors.append(c)

    return survivors, True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_instruments(groww, cache=None):
    """Load and filter instruments to NSE CASH equities only."""
    if cache:
        df = cache.get_instruments(groww)
    else:
        df = groww.get_all_instruments()

    # Filter to NSE CASH
    if "exchange" in df.columns and "segment" in df.columns:
        mask = (df["exchange"] == "NSE") & (df["segment"] == "CASH")
        df = df[mask]
    elif "exchange" in df.columns:
        df = df[df["exchange"] == "NSE"]

    # Keep only EQ series (drop NCDs, bonds, etc.)
    if "series" in df.columns:
        df = df[df["series"].isin(["EQ", "BE", "SM", "ST"])]

    return df


def _get_fno_symbols(instruments_full_df):
    """Extract FnO-eligible equity symbols from the full instruments DataFrame."""
    if "segment" not in instruments_full_df.columns:
        return set()
    fno_rows = instruments_full_df[instruments_full_df["segment"] == "FNO"]
    if "underlying_symbol" in fno_rows.columns:
        return set(fno_rows["underlying_symbol"].dropna().unique())
    if "trading_symbol" in fno_rows.columns:
        return set(fno_rows["trading_symbol"].dropna().unique())
    return set()


def _fetch_quote_volume(groww, symbol):
    """Return today's volume from the quote API with retry on rate limit."""
    for attempt in range(4):
        try:
            quote = groww.get_quote(symbol, "NSE", "CASH")
            return int(float(quote.get("volume", 0) if isinstance(quote, dict) else 0))
        except Exception as e:
            err_str = str(e).lower()
            if "rate" in err_str or "429" in err_str:
                time.sleep(0.5 * (2 ** attempt))
                continue
            return 0
    return 0


def _volume_enrich(groww, candidates, cache=None, max_workers=3):
    """Enrich all candidates with volume + turnover from the quote API."""
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_cand = {
            pool.submit(_fetch_quote_volume, groww, c["symbol"]): c
            for c in candidates
        }
        for future in as_completed(future_to_cand):
            cand = future_to_cand[future]
            try:
                vol = future.result()
            except Exception:
                vol = 0
            cand["volume"] = vol
            cand["turnover"] = round(vol * cand["ltp"], 2)
    return candidates


def _news_enrich(candidates, cache=None, max_workers=10):
    """Enrich candidates with news data (does NOT filter — sets empty if none)."""
    def _get_news(name):
        if cache:
            return cache.get_news(name, _fetch_news)
        return _fetch_news(name)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_cand = {
            pool.submit(_get_news, c["name"]): c for c in candidates
        }
        for future in as_completed(future_to_cand):
            cand = future_to_cand[future]
            try:
                result = future.result()
            except Exception:
                result = None
            if result is None:
                cand["news_headline"] = ""
                cand["news_link"] = ""
            else:
                headline, link = result
                cand["news_headline"] = headline
                cand["news_link"] = link
    return candidates


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_screener(groww, cache=None) -> dict:
    """Run the full screening pipeline and return results + metadata."""
    start_time = time.time()

    instruments_df = _load_instruments(groww, cache)

    total_instruments = len(instruments_df)

    # Stage 1: Price + day-change
    after_price = _batch_ohlc(groww, instruments_df, cache=cache)
    after_price_count = len(after_price)

    # Stage 2: Volume
    after_volume = _volume_filter(groww, after_price, cache=cache)
    after_volume_count = len(after_volume)

    # Stage 3: News
    after_news = _news_filter(after_volume, cache=cache)
    after_news_count = len(after_news)

    # Stage 4: Float
    final, float_available = _float_filter(instruments_df, after_news)

    scan_time = round(time.time() - start_time, 2)

    return {
        "results": final,
        "meta": {
            "total_instruments_scanned": total_instruments,
            "after_price_filter": after_price_count,
            "after_volume_filter": after_volume_count,
            "after_news_filter": after_news_count,
            "scan_time_seconds": scan_time,
            "float_filter_available": float_available,
            "cache_active": cache is not None,
        },
    }


def run_daily_picks(groww, cache=None, limit=10) -> dict:
    """Multi-strategy daily scanner — reliably returns tradeable stocks."""
    start_time = time.time()

    # Load full instruments for FnO cross-reference
    if cache:
        instruments_full_df = cache.get_instruments(groww)
    else:
        instruments_full_df = groww.get_all_instruments()
    fno_symbols = _get_fno_symbols(instruments_full_df)

    # Load filtered NSE CASH equities
    instruments_df = _load_instruments(groww, cache)
    total_instruments = len(instruments_df)

    # Stage 1: Batch OHLC — any positive change, price ≥ ₹50
    all_positive = _batch_ohlc(
        groww, instruments_df, cache=cache,
        min_day_change=0.0, price_range=(50, 50000),
    )
    candidates_after_price = len(all_positive)

    # Stage 2: Top 100 by day change + top 30 FnO stocks
    # FnO stocks rarely top day-change rankings but are needed for HC picks
    fno_candidates = [c for c in all_positive if c["symbol"] in fno_symbols]
    fno_candidates.sort(key=lambda x: x["day_change_pct"], reverse=True)
    top_fno = fno_candidates[:30]

    non_fno = [c for c in all_positive if c["symbol"] not in fno_symbols]
    non_fno.sort(key=lambda x: x["day_change_pct"], reverse=True)
    top_non_fno = non_fno[:100]

    # Merge: top movers + top FnO (deduplicated)
    seen = set()
    candidates = []
    for c in top_non_fno + top_fno:
        if c["symbol"] not in seen:
            seen.add(c["symbol"])
            candidates.append(c)

    # Stage 3: Volume enrich (parallel, 10 workers)
    candidates = _volume_enrich(groww, candidates, cache=cache)
    candidates_volume_enriched = len(candidates)

    # Stage 4: Tag every candidate with criteria flags (no filtering)
    # Turnover (volume × ltp) is the primary quality/liquidity proxy
    passes_gainer = 0
    passes_volume_leader = 0
    passes_hc = 0
    for c in candidates:
        c["fno_eligible"] = c["symbol"] in fno_symbols
        meets_turnover = c["turnover"] >= 5_000_000  # ₹50L
        c["meets_gainer_criteria"] = meets_turnover and c["volume"] >= 100_000
        c["meets_volume_leader_criteria"] = meets_turnover and c["volume"] >= 500_000
        c["high_conviction"] = (
            meets_turnover and c["volume"] >= 100_000 and c["fno_eligible"]
        )
        if c["meets_gainer_criteria"]:
            passes_gainer += 1
        if c["meets_volume_leader_criteria"]:
            passes_volume_leader += 1
        if c["high_conviction"]:
            passes_hc += 1

    # Stage 5: News enrich all candidates (does not filter)
    _news_enrich(candidates, cache=cache, max_workers=10)

    scan_time = round(time.time() - start_time, 2)

    return {
        "candidates": candidates,
        "meta": {
            "total_instruments_scanned": total_instruments,
            "candidates_after_price_filter": candidates_after_price,
            "candidates_volume_enriched": candidates_volume_enriched,
            "passes_gainer_criteria": passes_gainer,
            "passes_volume_leader_criteria": passes_volume_leader,
            "high_conviction_count": passes_hc,
            "fno_eligible_universe": len(fno_symbols),
            "scan_time_seconds": scan_time,
            "cache_active": cache is not None,
            "scan_timestamp": datetime.now().isoformat(),
        },
    }


def _batch_ohlc_streaming(groww, instruments_df, batch_size=50, sleep_between=0.1,
                          cache=None, min_day_change=0.0, price_range=(50, 50000),
                          yield_every=5):
    """Generator version of _batch_ohlc that yields intermediate results."""
    symbols = instruments_df["trading_symbol"].tolist()
    survivors = []
    total = len(symbols)
    total_batches = (total + batch_size - 1) // batch_size
    min_price, max_price = price_range
    batch_num = 0

    for i in range(0, total, batch_size):
        raw_batch = symbols[i : i + batch_size]
        batch = tuple(f"NSE_{s}" for s in raw_batch)

        if cache:
            try:
                ohlc = cache.get_ohlc_batch(groww, batch)
            except Exception as e:
                logger.warning("OHLC batch %d failed: %s", i, e)
                ohlc = {}
        else:
            retries = 0
            while retries < 3:
                try:
                    ohlc = groww.get_ohlc(
                        exchange_trading_symbols=batch, segment="CASH"
                    )
                    break
                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str or "rate" in err_str.lower():
                        retries += 1
                        time.sleep(0.5 * (2 ** retries))
                        continue
                    logger.warning("OHLC batch %d failed: %s", i, e)
                    ohlc = {}
                    break
            else:
                logger.warning("OHLC batch %d exhausted retries", i)
                ohlc = {}

        if not isinstance(ohlc, dict):
            batch_num += 1
            continue

        ltp_map = {}
        try:
            ltp_data = groww.get_ltp(
                exchange_trading_symbols=batch, segment="CASH"
            )
            if isinstance(ltp_data, dict):
                for key, val in ltp_data.items():
                    if isinstance(val, dict):
                        ltp_map[key] = float(val.get("ltp", 0))
                    else:
                        ltp_map[key] = float(val)
        except Exception as e:
            logger.warning("LTP batch %d failed: %s", i, e)

        for sym in raw_batch:
            es = f"NSE_{sym}"
            data = ohlc.get(es)
            if not data or not isinstance(data, dict):
                continue
            try:
                open_price = float(data.get("open", 0))
            except (TypeError, ValueError):
                continue

            ltp = ltp_map.get(es, 0)

            if open_price <= 0 or ltp <= 0:
                continue
            if not (min_price <= ltp <= max_price):
                continue

            day_change_pct = ((ltp - open_price) / open_price) * 100
            if day_change_pct < min_day_change:
                continue

            name_rows = instruments_df.loc[
                instruments_df["trading_symbol"] == sym, "name"
            ]
            name = name_rows.iloc[0] if len(name_rows) > 0 else sym
            if not isinstance(name, str) or not name.strip():
                name = sym

            survivors.append(
                {
                    "symbol": sym,
                    "name": name,
                    "ltp": round(ltp, 2),
                    "open": round(open_price, 2),
                    "day_change_pct": round(day_change_pct, 2),
                }
            )

        batch_num += 1
        time.sleep(sleep_between)

        if batch_num % yield_every == 0 or batch_num == total_batches:
            yield {
                "survivors": list(survivors),
                "batch_num": batch_num,
                "total_batches": total_batches,
            }


def run_daily_picks_streaming(groww, cache=None):
    """Generator that yields SSE event dicts at each stage of the pipeline."""
    start_time = time.time()

    # Load full instruments for FnO cross-reference
    if cache:
        instruments_full_df = cache.get_instruments(groww)
    else:
        instruments_full_df = groww.get_all_instruments()
    fno_symbols = _get_fno_symbols(instruments_full_df)

    # Load filtered NSE CASH equities
    instruments_df = _load_instruments(groww, cache)
    total_instruments = len(instruments_df)

    # Stage 1: Streaming batch OHLC
    all_positive = []
    for update in _batch_ohlc_streaming(groww, instruments_df, cache=cache):
        all_positive = update["survivors"]

        # Build interim top movers for preview
        fno_cands = [c for c in all_positive if c["symbol"] in fno_symbols]
        fno_cands.sort(key=lambda x: x["day_change_pct"], reverse=True)
        non_fno = [c for c in all_positive if c["symbol"] not in fno_symbols]
        non_fno.sort(key=lambda x: x["day_change_pct"], reverse=True)

        seen = set()
        preview = []
        for c in non_fno[:100] + fno_cands[:30]:
            if c["symbol"] not in seen:
                seen.add(c["symbol"])
                # Add placeholder fields for unenriched data
                preview.append(dict(
                    c,
                    volume=0,
                    turnover=0,
                    fno_eligible=c["symbol"] in fno_symbols,
                    meets_gainer_criteria=False,
                    meets_volume_leader_criteria=False,
                    high_conviction=False,
                    news_headline="",
                    news_link="",
                ))

        yield {
            "event_type": "batch",
            "stage": "ohlc",
            "candidates": preview,
            "progress": {
                "current": update["batch_num"],
                "total": update["total_batches"],
            },
            "meta": {
                "total_instruments_scanned": total_instruments,
                "fno_eligible_universe": len(fno_symbols),
                "cache_active": cache is not None,
            },
        }

    # Stage 2: Top movers selection (same logic as run_daily_picks)
    candidates_after_price = len(all_positive)
    fno_candidates = [c for c in all_positive if c["symbol"] in fno_symbols]
    fno_candidates.sort(key=lambda x: x["day_change_pct"], reverse=True)
    top_fno = fno_candidates[:30]

    non_fno = [c for c in all_positive if c["symbol"] not in fno_symbols]
    non_fno.sort(key=lambda x: x["day_change_pct"], reverse=True)
    top_non_fno = non_fno[:100]

    seen = set()
    candidates = []
    for c in top_non_fno + top_fno:
        if c["symbol"] not in seen:
            seen.add(c["symbol"])
            candidates.append(c)

    # Yield OHLC complete
    ohlc_candidates = []
    for c in candidates:
        ohlc_candidates.append(dict(
            c,
            volume=0,
            turnover=0,
            fno_eligible=c["symbol"] in fno_symbols,
            meets_gainer_criteria=False,
            meets_volume_leader_criteria=False,
            high_conviction=False,
            news_headline="",
            news_link="",
        ))

    yield {
        "event_type": "stage_complete",
        "stage": "ohlc",
        "candidates": ohlc_candidates,
        "meta": {
            "total_instruments_scanned": total_instruments,
            "candidates_after_price_filter": candidates_after_price,
            "fno_eligible_universe": len(fno_symbols),
            "cache_active": cache is not None,
        },
    }

    # Stage 3: Volume enrich
    candidates = _volume_enrich(groww, candidates, cache=cache)

    # Tag criteria flags
    for c in candidates:
        c["fno_eligible"] = c["symbol"] in fno_symbols
        meets_turnover = c["turnover"] >= 5_000_000
        c["meets_gainer_criteria"] = meets_turnover and c["volume"] >= 100_000
        c["meets_volume_leader_criteria"] = meets_turnover and c["volume"] >= 500_000
        c["high_conviction"] = (
            meets_turnover and c["volume"] >= 100_000 and c["fno_eligible"]
        )
        c.setdefault("news_headline", "")
        c.setdefault("news_link", "")

    passes_gainer = sum(1 for c in candidates if c["meets_gainer_criteria"])
    passes_volume_leader = sum(1 for c in candidates if c["meets_volume_leader_criteria"])
    passes_hc = sum(1 for c in candidates if c["high_conviction"])

    yield {
        "event_type": "stage_complete",
        "stage": "volume",
        "candidates": list(candidates),
        "meta": {
            "total_instruments_scanned": total_instruments,
            "candidates_after_price_filter": candidates_after_price,
            "candidates_volume_enriched": len(candidates),
            "passes_gainer_criteria": passes_gainer,
            "passes_volume_leader_criteria": passes_volume_leader,
            "high_conviction_count": passes_hc,
            "fno_eligible_universe": len(fno_symbols),
            "cache_active": cache is not None,
        },
    }

    # Stage 4: News enrich
    _news_enrich(candidates, cache=cache, max_workers=10)

    scan_time = round(time.time() - start_time, 2)

    yield {
        "event_type": "complete",
        "stage": "done",
        "candidates": list(candidates),
        "meta": {
            "total_instruments_scanned": total_instruments,
            "candidates_after_price_filter": candidates_after_price,
            "candidates_volume_enriched": len(candidates),
            "passes_gainer_criteria": passes_gainer,
            "passes_volume_leader_criteria": passes_volume_leader,
            "high_conviction_count": passes_hc,
            "fno_eligible_universe": len(fno_symbols),
            "scan_time_seconds": scan_time,
            "cache_active": cache is not None,
            "scan_timestamp": datetime.now().isoformat(),
        },
    }


def run_top_movers(groww, cache=None, limit=50) -> dict:
    """Return top stocks by day change %, no volume/news/float filters."""
    start_time = time.time()

    instruments_df = _load_instruments(groww, cache)
    total_instruments = len(instruments_df)

    # Collect all stocks with any positive change, no minimum cutoff
    all_movers = _batch_ohlc(
        groww, instruments_df, cache=cache,
        min_day_change=-999, price_range=(0, 999999),
    )

    # Sort descending by day_change_pct
    all_movers.sort(key=lambda x: x["day_change_pct"], reverse=True)

    # Trim to limit
    top = all_movers[:limit]

    scan_time = round(time.time() - start_time, 2)

    return {
        "results": top,
        "meta": {
            "total_instruments_scanned": total_instruments,
            "total_with_ohlc": len(all_movers),
            "showing": len(top),
            "scan_time_seconds": scan_time,
            "cache_active": cache is not None,
        },
    }
