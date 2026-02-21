"""
Holdings Service - Portfolio holdings management.

Provides portfolio enrichment with real-time LTP and P&L calculations.
"""

from typing import Any, Dict, List, Optional

from core.logging_config import get_logger
from infrastructure.groww_client import GrowwClientBase

logger = get_logger("services.holdings")


class HoldingsService:
    """Service for managing and enriching portfolio holdings."""

    def __init__(self, groww_client: GrowwClientBase):
        self._groww = groww_client

    def get_holdings(self) -> Dict[str, Any]:
        """Fetch and enrich user holdings with LTP data."""
        try:
            response = self._groww.get_holdings_for_user()
        except Exception as e:
            logger.error("Failed to fetch holdings: %s", e)
            raise HoldingsError(f"Failed to fetch holdings: {e}")

        raw_holdings = response.get("holdings", []) if isinstance(response, dict) else response
        return self._enrich_holdings(raw_holdings)

    def _enrich_holdings(self, raw_holdings: List[Dict]) -> Dict[str, Any]:
        """Enrich raw holdings with LTP and calculate P&L."""
        holdings = []
        total_current = 0.0
        total_invested = 0.0

        exchange_symbols = []
        for h in raw_holdings:
            ts = h.get("trading_symbol", "UNKNOWN")
            exchanges = h.get("tradable_exchanges", ["NSE"])
            exchange = exchanges[0] if exchanges else "NSE"
            exchange_symbols.append(f"{exchange}_{ts}")

        ltp_map = self._fetch_ltp_batch(exchange_symbols)

        for i, h in enumerate(raw_holdings):
            symbol = h.get("trading_symbol", "UNKNOWN")
            quantity = float(h.get("quantity", 0))
            average_price = float(h.get("average_price", 0))

            es = exchange_symbols[i] if i < len(exchange_symbols) else ""
            ltp = ltp_map.get(es, average_price)

            current_value = quantity * ltp
            invested_value = quantity * average_price
            pnl = current_value - invested_value
            pnl_percentage = (pnl / invested_value * 100) if invested_value != 0 else 0.0

            total_current += current_value
            total_invested += invested_value

            holdings.append(
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "average_price": round(average_price, 2),
                    "ltp": round(ltp, 2),
                    "current_value": round(current_value, 2),
                    "invested_value": round(invested_value, 2),
                    "pnl": round(pnl, 2),
                    "pnl_percentage": round(pnl_percentage, 2),
                }
            )

        total_pnl = total_current - total_invested
        total_pnl_percentage = (total_pnl / total_invested * 100) if total_invested != 0 else 0.0

        return {
            "holdings": holdings,
            "summary": {
                "total_current_value": round(total_current, 2),
                "total_invested_value": round(total_invested, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_percentage": round(total_pnl_percentage, 2),
            },
        }

    def _fetch_ltp_batch(self, exchange_symbols: List[str]) -> Dict[str, float]:
        """Fetch LTP for symbols in batches."""
        ltp_map = {}
        if not exchange_symbols:
            return ltp_map

        try:
            for i in range(0, len(exchange_symbols), 50):
                batch = exchange_symbols[i : i + 50]
                try:
                    ltp_data = self._groww.get_ltp(
                        exchange_trading_symbols=tuple(batch),
                        segment="CASH",
                    )
                    if isinstance(ltp_data, dict):
                        for key, val in ltp_data.items():
                            if isinstance(val, dict):
                                ltp_map[key] = float(val.get("ltp", 0))
                            else:
                                ltp_map[key] = float(val)
                except Exception as e:
                    logger.warning("LTP batch fetch failed: %s", e)
        except Exception as e:
            logger.error("Failed to fetch LTP: %s", e)

        return ltp_map


class HoldingsError(Exception):
    """Exception raised for holdings-related errors."""

    pass
