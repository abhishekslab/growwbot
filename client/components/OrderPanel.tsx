"use client";

import { useState, useEffect } from "react";
import { OrderPayload } from "@/types/symbol";

type TransactionType = "BUY" | "SELL";
type Product = "CNC" | "MIS" | "NRML";
type OrderType = "MARKET" | "LIMIT" | "SL" | "SL-M";

interface Props {
  symbol: string;
  ltp: number;
  onSubmit: (order: OrderPayload) => void;
}

export default function OrderPanel({ symbol, ltp, onSubmit }: Props) {
  const [txnType, setTxnType] = useState<TransactionType>("BUY");
  const [product, setProduct] = useState<Product>("CNC");
  const [orderType, setOrderType] = useState<OrderType>("MARKET");
  const [quantity, setQuantity] = useState(1);
  const [price, setPrice] = useState(ltp);
  const [triggerPrice, setTriggerPrice] = useState(0);

  useEffect(() => {
    if (orderType === "MARKET") setPrice(ltp);
  }, [ltp, orderType]);

  const showPrice = orderType === "LIMIT" || orderType === "SL";
  const showTrigger = orderType === "SL" || orderType === "SL-M";
  const estimatedValue = quantity * (orderType === "MARKET" ? ltp : price);

  const valid = quantity >= 1 && (!showPrice || price > 0) && (!showTrigger || triggerPrice > 0);

  const handleSubmit = () => {
    if (!valid) return;
    onSubmit({
      trading_symbol: symbol,
      transaction_type: txnType,
      order_type: orderType,
      product,
      quantity,
      price: orderType === "MARKET" ? 0 : price,
      trigger_price: showTrigger ? triggerPrice : undefined,
      validity: "DAY",
    });
  };

  const products: Product[] = ["CNC", "MIS", "NRML"];
  const orderTypes: OrderType[] = ["MARKET", "LIMIT", "SL", "SL-M"];

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-gray-100">Place Order</h2>

      {/* Buy / Sell toggle */}
      <div className="mb-4 flex gap-2">
        {(["BUY", "SELL"] as TransactionType[]).map((t) => (
          <button
            key={t}
            onClick={() => setTxnType(t)}
            className={`flex-1 rounded-lg py-2 text-sm font-semibold transition ${
              txnType === t
                ? t === "BUY"
                  ? "bg-green-600 text-white"
                  : "bg-red-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Product type */}
      <div className="mb-4">
        <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
          Product
        </label>
        <div className="flex gap-2">
          {products.map((p) => (
            <button
              key={p}
              onClick={() => setProduct(p)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                product === p
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Order type */}
      <div className="mb-4">
        <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
          Order Type
        </label>
        <div className="flex gap-2">
          {orderTypes.map((ot) => (
            <button
              key={ot}
              onClick={() => setOrderType(ot)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                orderType === ot
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              }`}
            >
              {ot}
            </button>
          ))}
        </div>
      </div>

      {/* Quantity */}
      <div className="mb-4">
        <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
          Quantity
        </label>
        <input
          type="number"
          min={1}
          value={quantity}
          onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100"
        />
      </div>

      {/* Price (LIMIT / SL) */}
      {showPrice && (
        <div className="mb-4">
          <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
            Price
          </label>
          <input
            type="number"
            step="0.05"
            min={0}
            value={price}
            onChange={(e) => setPrice(parseFloat(e.target.value) || 0)}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100"
          />
        </div>
      )}

      {/* Trigger Price (SL / SL-M) */}
      {showTrigger && (
        <div className="mb-4">
          <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
            Trigger Price
          </label>
          <input
            type="number"
            step="0.05"
            min={0}
            value={triggerPrice}
            onChange={(e) => setTriggerPrice(parseFloat(e.target.value) || 0)}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100"
          />
        </div>
      )}

      {/* Estimated value */}
      <div className="mb-4 rounded-lg bg-gray-50 px-3 py-2 text-sm dark:bg-gray-800">
        <span className="text-gray-500 dark:text-gray-400">Est. Value: </span>
        <span className="font-medium text-gray-900 dark:text-gray-100">
          {"\u20B9"}
          {estimatedValue.toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </span>
      </div>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={!valid}
        className={`w-full rounded-lg py-2.5 text-sm font-semibold text-white transition disabled:opacity-50 ${
          txnType === "BUY" ? "bg-green-600 hover:bg-green-700" : "bg-red-600 hover:bg-red-700"
        }`}
      >
        Review {txnType} Order
      </button>
    </div>
  );
}
