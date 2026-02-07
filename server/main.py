import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(title="Groww Portfolio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_groww_client():
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    if not api_key or not api_secret:
        raise HTTPException(
            status_code=500,
            detail="API_KEY and API_SECRET must be set in server/.env",
        )
    from growwapi import GrowwAPI

    access_token = GrowwAPI.get_access_token(api_key, secret=api_secret)
    return GrowwAPI(access_token)


@app.get("/api/holdings")
def get_holdings():
    try:
        groww = get_groww_client()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")

    try:
        response = groww.get_holdings_for_user()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch holdings: {e}")

    raw_holdings = response.get("holdings", []) if isinstance(response, dict) else response

    holdings = []
    total_current = 0.0
    total_invested = 0.0

    # Build exchange symbols for batch LTP fetch
    exchange_symbols = []
    for h in raw_holdings:
        ts = h.get("trading_symbol", "UNKNOWN")
        exchanges = h.get("tradable_exchanges", ["NSE"])
        exchange = exchanges[0] if exchanges else "NSE"
        exchange_symbols.append(f"{exchange}_{ts}")

    ltp_map: dict = {}
    if exchange_symbols:
        try:
            ltp_data = groww.get_ltp(
                exchange_trading_symbols=tuple(exchange_symbols),
                segment="CASH",
            )
            # Response is {"NSE_SYMBOL": 123.45, ...}
            if isinstance(ltp_data, dict):
                for key, val in ltp_data.items():
                    if isinstance(val, dict):
                        ltp_map[key] = float(val.get("ltp", 0))
                    else:
                        ltp_map[key] = float(val)
        except Exception:
            pass

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
    total_pnl_percentage = (
        (total_pnl / total_invested * 100) if total_invested != 0 else 0.0
    )

    return {
        "holdings": holdings,
        "summary": {
            "total_current_value": round(total_current, 2),
            "total_invested_value": round(total_invested, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_percentage": round(total_pnl_percentage, 2),
        },
    }
