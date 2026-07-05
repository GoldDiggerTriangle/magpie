import type { BuyCalculationPayload, BuyCalculationResult, ProfitSettings, RoiBasis, SellerMode } from "../../types";

const BPF_CAP = 210.7;

function decimal(value: string | undefined | null, fallback = 0) {
  if (value === undefined || value === null || value === "") return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`Invalid decimal value: ${value}`);
  }
  return parsed;
}

function money(value: number) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function percent(value: number) {
  return money(value);
}

function asMoneyString(value: number) {
  return money(value).toFixed(2);
}

export function buyerProtectionFee(sellerPrice: number) {
  const first = Math.min(sellerPrice, 20);
  const second = Math.min(Math.max(sellerPrice - 20, 0), 480);
  const third = Math.min(Math.max(sellerPrice - 500, 0), 4500);
  return money(Math.min(0.3 + first * 0.08 + second * 0.06 + third * 0.04, BPF_CAP));
}

export function sellerPriceFromBuyerVisible(buyerTotal: number) {
  if (buyerTotal <= 0.3) return 0;
  if (buyerTotal <= 21.9) return money((buyerTotal - 0.3) / 1.08);
  if (buyerTotal <= 530.7) return money((buyerTotal - 0.7) / 1.06);
  if (buyerTotal <= 5210.7) return money((buyerTotal - 10.7) / 1.04);
  return money(buyerTotal - BPF_CAP);
}

export function buyerVisibleTotal(sellerPrice: number) {
  return money(sellerPrice + buyerProtectionFee(sellerPrice));
}

function sellerReceives(price: string, basis: BuyCalculationPayload["price_basis"]) {
  if (basis === "unknown") {
    throw new Error("Expected sell price needs a known basis for calculator math.");
  }
  const amount = decimal(price);
  return basis === "buyer_visible" ? sellerPriceFromBuyerVisible(amount) : money(amount);
}

function sellerFees(price: number, sellerMode: SellerMode, settings?: ProfitSettings) {
  if (sellerMode === "pro_starter") return money(price * 0.134);
  if (sellerMode === "pro_other") return money(price * decimal(settings?.pro_other_final_value_pct, 13.4) / 100);
  if (sellerMode === "legacy_manual") {
    return money(price * decimal(settings?.manual_final_value_pct, 0) / 100 + decimal(settings?.manual_fixed_fee, 0));
  }
  buyerProtectionFee(price);
  return 0;
}

function maxBuyForRoi(netBeforeBuy: number, nonBuyCosts: number, roiPct: number, basis: RoiBasis) {
  const roi = roiPct / 100;
  if (basis === "buy_price") return money(netBeforeBuy / (1 + roi));
  return money((netBeforeBuy + nonBuyCosts) / (1 + roi) - nonBuyCosts);
}

export function calculateLocalBuy(
  payload: BuyCalculationPayload,
  settings?: ProfitSettings
): BuyCalculationResult {
  const receives = sellerReceives(payload.expected_sell_price, payload.price_basis);
  const fees = sellerFees(receives, payload.seller_mode ?? settings?.seller_mode ?? "free_selling", settings);
  const nonBuyCosts = money(decimal(payload.postage) + decimal(payload.packaging) + decimal(payload.refurb));
  const netBeforeBuy = money(receives - fees - nonBuyCosts);
  const maxBuy = payload.target_type === "flat"
    ? money(receives - fees - nonBuyCosts - decimal(payload.flat_profit_target))
    : maxBuyForRoi(netBeforeBuy, nonBuyCosts, decimal(payload.roi_pct), payload.roi_basis);

  let expectedProfit: number | null = null;
  let roiAtAsking: number | null = null;
  let verdict: BuyCalculationResult["verdict"] = "NO ASKING PRICE";
  const asking = payload.asking_price ? decimal(payload.asking_price) : null;
  if (asking !== null) {
    expectedProfit = money(netBeforeBuy - asking);
    const allInCash = asking + nonBuyCosts;
    roiAtAsking = allInCash > 0 ? percent((expectedProfit / allInCash) * 100) : null;
    const maybeBand = decimal(settings?.maybe_band_pct, 10) / 100;
    if (asking <= maxBuy) {
      verdict = "BUY";
    } else if (asking <= money(maxBuy * (1 + maybeBand))) {
      verdict = "MAYBE";
    } else {
      verdict = "PASS";
    }
  }

  return {
    max_buy: asMoneyString(maxBuy),
    headline: payload.lot_mode ? "Max Lot Buy" : (payload.auction_mode ? "Max Bid" : "Max Buy Price"),
    verdict,
    expected_profit_at_asking: expectedProfit === null ? null : asMoneyString(expectedProfit),
    roi_at_asking: roiAtAsking === null ? null : roiAtAsking.toFixed(2),
    net_proceeds_before_buy: asMoneyString(netBeforeBuy),
    seller_fees: asMoneyString(fees),
    non_buy_costs: asMoneyString(nonBuyCosts),
    evidence_source: payload.evidence_source,
    confidence_label: payload.confidence_label,
    roi_basis: payload.roi_basis
  };
}
