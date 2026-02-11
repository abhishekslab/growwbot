import { FeeConfig, DEFAULT_FEE_CONFIG } from "./feeDefaults";

export interface FeeBreakdown {
  brokerage: number;
  stt: number;
  exchangeTxn: number;
  sebi: number;
  stampDuty: number;
  gst: number;
  total: number;
}

export interface PositionResult {
  quantity: number;
  target: number;
  capitalUsed: number;
  riskAmount: number;
  feesEntry: FeeBreakdown;
  feesExitTarget: FeeBreakdown;
  feesExitSL: FeeBreakdown;
  netProfitIfTarget: number;
  netLossIfSL: number;
}

export interface ExitResult {
  grossPnl: number;
  feesEntry: FeeBreakdown;
  feesExit: FeeBreakdown;
  totalFees: number;
  netPnl: number;
}

/** Calculate fees for one side (buy or sell) of a trade. */
export function calculateFees(
  price: number,
  qty: number,
  side: "BUY" | "SELL",
  tradeType: "INTRADAY" | "DELIVERY",
  config: FeeConfig = DEFAULT_FEE_CONFIG
): FeeBreakdown {
  const turnover = price * qty;

  const brokerage = Math.min(config.brokeragePerOrder, turnover * 0.0003); // cap at 0.03% or flat

  let stt = 0;
  if (tradeType === "INTRADAY") {
    stt = side === "SELL" ? turnover * config.sttIntradaySellRate : 0;
  } else {
    stt = turnover * config.sttDeliveryRate;
  }

  const exchangeTxn = turnover * config.exchangeTxnRate;
  const sebi = turnover * config.sebiRate;
  const stampDuty = side === "BUY" ? turnover * config.stampDutyRate : 0;
  const gst = (brokerage + exchangeTxn + sebi) * config.gstRate;

  const total = brokerage + stt + exchangeTxn + sebi + stampDuty + gst;

  return {
    brokerage: round2(brokerage),
    stt: round2(stt),
    exchangeTxn: round2(exchangeTxn),
    sebi: round2(sebi),
    stampDuty: round2(stampDuty),
    gst: round2(gst),
    total: round2(total),
  };
}

/** Calculate position size based on risk management rules. */
export function calculatePositionSize(
  capital: number,
  riskPercent: number,
  entryPrice: number,
  stopLoss: number,
  tradeType: "INTRADAY" | "DELIVERY",
  config: FeeConfig = DEFAULT_FEE_CONFIG,
  rrRatio: number = 2
): PositionResult {
  const riskPerShare = Math.abs(entryPrice - stopLoss);
  if (riskPerShare === 0) {
    return emptyResult(entryPrice);
  }

  const maxRisk = capital * (riskPercent / 100);
  let quantity = Math.floor(maxRisk / riskPerShare);

  // Ensure we don't exceed capital
  while (quantity > 0 && quantity * entryPrice > capital) {
    quantity--;
  }

  if (quantity <= 0) {
    return emptyResult(entryPrice);
  }

  // Risk-reward target
  const isLong = entryPrice > stopLoss;
  const target = isLong
    ? entryPrice + riskPerShare * rrRatio
    : entryPrice - riskPerShare * rrRatio;

  const capitalUsed = quantity * entryPrice;
  const riskAmount = quantity * riskPerShare;

  const feesEntry = calculateFees(entryPrice, quantity, "BUY", tradeType, config);
  const feesExitTarget = calculateFees(target, quantity, "SELL", tradeType, config);
  const feesExitSL = calculateFees(stopLoss, quantity, "SELL", tradeType, config);

  const grossProfitTarget = quantity * Math.abs(target - entryPrice);
  const grossLossSL = quantity * riskPerShare;

  const netProfitIfTarget = grossProfitTarget - feesEntry.total - feesExitTarget.total;
  const netLossIfSL = -(grossLossSL + feesEntry.total + feesExitSL.total);

  return {
    quantity,
    target: round2(target),
    capitalUsed: round2(capitalUsed),
    riskAmount: round2(riskAmount),
    feesEntry,
    feesExitTarget,
    feesExitSL,
    netProfitIfTarget: round2(netProfitIfTarget),
    netLossIfSL: round2(netLossIfSL),
  };
}

/** Calculate realized P&L when closing a trade. */
export function calculateTradeExit(
  entryPrice: number,
  exitPrice: number,
  quantity: number,
  tradeType: "INTRADAY" | "DELIVERY",
  config: FeeConfig = DEFAULT_FEE_CONFIG
): ExitResult {
  const grossPnl = (exitPrice - entryPrice) * quantity;
  const feesEntry = calculateFees(entryPrice, quantity, "BUY", tradeType, config);
  const feesExit = calculateFees(exitPrice, quantity, "SELL", tradeType, config);
  const totalFees = feesEntry.total + feesExit.total;
  const netPnl = grossPnl - totalFees;

  return {
    grossPnl: round2(grossPnl),
    feesEntry,
    feesExit,
    totalFees: round2(totalFees),
    netPnl: round2(netPnl),
  };
}

export interface FeeAdjustedTargetResult {
  target: number;
  netProfit: number;
  netLoss: number;
}

/** Calculate a fee-adjusted target so that net profit = rrRatio× net loss (after fees). */
export function calculateFeeAdjustedTarget(
  entryPrice: number,
  stopLoss: number,
  quantity: number,
  tradeType: "INTRADAY" | "DELIVERY",
  config: FeeConfig = DEFAULT_FEE_CONFIG,
  rrRatio: number = 2
): FeeAdjustedTargetResult {
  if (quantity <= 0 || entryPrice <= 0 || stopLoss <= 0) {
    return { target: entryPrice, netProfit: 0, netLoss: 0 };
  }

  const riskPerShare = Math.abs(entryPrice - stopLoss);
  if (riskPerShare === 0) {
    return { target: entryPrice, netProfit: 0, netLoss: 0 };
  }

  const feesEntry = calculateFees(entryPrice, quantity, "BUY", tradeType, config);
  const feesExitSL = calculateFees(stopLoss, quantity, "SELL", tradeType, config);
  const netLoss = quantity * riskPerShare + feesEntry.total + feesExitSL.total;
  const desiredNetProfit = rrRatio * netLoss;

  // Iterative: converge on target where net profit after fees = desiredNetProfit
  let target = entryPrice + riskPerShare * rrRatio; // naive starting point
  for (let i = 0; i < 5; i++) {
    const feesExitTarget = calculateFees(target, quantity, "SELL", tradeType, config);
    const neededGross = desiredNetProfit + feesEntry.total + feesExitTarget.total;
    const newTarget = entryPrice + neededGross / quantity;
    if (Math.abs(newTarget - target) < 0.05) {
      target = newTarget;
      break;
    }
    target = newTarget;
  }

  // Round to nearest tick (0.05)
  target = Math.round(target / 0.05) * 0.05;

  const feesExitTarget = calculateFees(target, quantity, "SELL", tradeType, config);
  const grossProfit = (target - entryPrice) * quantity;
  const netProfit = grossProfit - feesEntry.total - feesExitTarget.total;

  return {
    target: round2(target),
    netProfit: round2(netProfit),
    netLoss: round2(-netLoss),
  };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

function emptyResult(entryPrice: number): PositionResult {
  const zeroFees: FeeBreakdown = {
    brokerage: 0, stt: 0, exchangeTxn: 0, sebi: 0, stampDuty: 0, gst: 0, total: 0,
  };
  return {
    quantity: 0,
    target: entryPrice,
    capitalUsed: 0,
    riskAmount: 0,
    feesEntry: zeroFees,
    feesExitTarget: zeroFees,
    feesExitSL: zeroFees,
    netProfitIfTarget: 0,
    netLossIfSL: 0,
  };
}
