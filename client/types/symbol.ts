export type Timeframe = "1m" | "3m" | "5m" | "15m" | "1H" | "1D";

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Quote {
  symbol: string;
  ltp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  prev_close: number;
  volume: number;
  change: number;
  change_pct: number;
}

export interface OrderPayload {
  trading_symbol: string;
  transaction_type: "BUY" | "SELL";
  order_type: "MARKET" | "LIMIT" | "SL" | "SL-M";
  product: "CNC" | "MIS" | "NRML";
  quantity: number;
  price: number;
  trigger_price?: number;
  validity: string;
}

export interface OrderResult {
  order_id?: string;
  status?: string;
  message?: string;
  [key: string]: unknown;
}
