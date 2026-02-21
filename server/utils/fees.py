"""
Python port of the fee calculator from client/lib/tradeCalculator.ts.

Fee calculations for Indian exchanges (NSE/BSE) with intraday and delivery support.
"""

from typing import Dict, Optional

# Default fee configuration for Indian exchanges
DEFAULT_FEE_CONFIG = {
    "brokerage_per_order": 20,
    "stt_intraday_sell_rate": 0.00025,
    "stt_delivery_rate": 0.001,
    "exchange_txn_rate": 0.0000345,
    "sebi_rate": 0.000001,
    "stamp_duty_rate": 0.00003,
    "gst_rate": 0.18,
}


def calculate_fees(
    price,  # type: float
    qty,  # type: int
    side,  # type: str  # "BUY" or "SELL"
    trade_type,  # type: str  # "INTRADAY" or "DELIVERY"
    config=None,  # type: Optional[dict]
):
    # type: (...) -> Dict[str, float]
    """
    Calculate total trading fees for a single order.

    Args:
        price: Order price per share
        qty: Quantity of shares
        side: "BUY" or "SELL"
        trade_type: "INTRADAY" or "DELIVERY"
        config: Fee configuration override (optional)

    Returns:
        Dict with "total" key containing the total fee amount
    """
    if config is None:
        config = DEFAULT_FEE_CONFIG

    turnover = price * qty
    brokerage = min(config["brokerage_per_order"], turnover * 0.0003)

    if trade_type == "INTRADAY":
        stt = turnover * config["stt_intraday_sell_rate"] if side == "SELL" else 0
    else:
        stt = turnover * config["stt_delivery_rate"]

    exchange_txn = turnover * config["exchange_txn_rate"]
    sebi = turnover * config["sebi_rate"]
    stamp_duty = turnover * config["stamp_duty_rate"] if side == "BUY" else 0
    gst = (brokerage + exchange_txn + sebi) * config["gst_rate"]

    total = brokerage + stt + exchange_txn + sebi + stamp_duty + gst
    return {"total": round(total, 2)}


def compute_exit_pnl(entry_price, exit_price, quantity, trade_type="DELIVERY"):
    # type: (float, float, int, str) -> tuple
    """
    Calculate net P&L and total fees for a trade exit.

    Args:
        entry_price: Average entry price
        exit_price: Average exit price
        quantity: Number of shares
        trade_type: "INTRADAY" or "DELIVERY"

    Returns:
        Tuple of (net_pnl, total_fees)
    """
    gross = (exit_price - entry_price) * quantity
    fees_entry = calculate_fees(entry_price, quantity, "BUY", trade_type)
    fees_exit = calculate_fees(exit_price, quantity, "SELL", trade_type)
    total_fees = fees_entry["total"] + fees_exit["total"]
    net = gross - total_fees
    return round(net, 2), round(total_fees, 2)


def calculate_position_value(entry_price, quantity):
    # type: (float, int) -> float
    """Calculate gross position value (price × quantity)."""
    return round(entry_price * quantity, 2)


def calculate_risk_per_share(entry_price, stop_loss, is_long=True):
    # type: (float, float, bool) -> float
    """Calculate risk amount per share based on stop loss."""
    risk = abs(entry_price - stop_loss)
    return round(risk, 2)


def calculate_position_size(capital, risk_percent, risk_per_share, fees=None):
    # type: (float, float, float, Optional[float]) -> int
    """
    Calculate position size based on risk management rules.

    Args:
        capital: Available capital
        risk_percent: Percentage of capital to risk (0-100)
        risk_per_share: Risk amount per share
        fees: Estimated fees to account for (optional)

    Returns:
        Number of shares to buy/sell
    """
    risk_amount = capital * (risk_percent / 100)

    if fees:
        risk_amount = max(0, risk_amount - fees)

    if risk_per_share <= 0:
        return 0

    position_size = int(risk_amount / risk_per_share)
    return position_size


def get_fee_config():
    # type: () -> dict
    """Get the default fee configuration."""
    return DEFAULT_FEE_CONFIG.copy()


def update_fee_config(**kwargs):
    # type: (**float) -> dict
    """Create a custom fee configuration with updated values."""
    config = DEFAULT_FEE_CONFIG.copy()
    config.update(kwargs)
    return config
