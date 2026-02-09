/** Indian exchange fee configuration for equity trades. */

export interface FeeConfig {
  /** Flat brokerage per order (buy + sell) */
  brokeragePerOrder: number;
  /** STT rate on sell side for intraday */
  sttIntradaySellRate: number;
  /** STT rate on both sides for delivery */
  sttDeliveryRate: number;
  /** Exchange transaction charge rate */
  exchangeTxnRate: number;
  /** SEBI turnover fee rate */
  sebiRate: number;
  /** Stamp duty rate (buy side only) */
  stampDutyRate: number;
  /** GST rate on (brokerage + exchange txn + SEBI) */
  gstRate: number;
}

export const DEFAULT_FEE_CONFIG: FeeConfig = {
  brokeragePerOrder: 20,
  sttIntradaySellRate: 0.00025, // 0.025%
  sttDeliveryRate: 0.001, // 0.1%
  exchangeTxnRate: 0.0000345, // 0.00345%
  sebiRate: 0.000001, // 0.0001%
  stampDutyRate: 0.00003, // 0.003%
  gstRate: 0.18, // 18%
};
