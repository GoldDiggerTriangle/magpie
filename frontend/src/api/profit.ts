import { apiRequest } from "./client";
import type { BoughtItPayload, BuyCalculationPayload, BuyCalculationResult, BuyCalculatorEvidence, InventoryItemDetail, ProfitLedger, ProfitSettings, UUID } from "../types";

export function getProfitSettings() {
  return apiRequest<ProfitSettings>("/api/profit/settings/");
}

export function updateProfitSettings(payload: ProfitSettings) {
  return apiRequest<ProfitSettings>("/api/profit/settings/", {
    method: "PUT",
    body: payload
  });
}

export function getBuyCalculatorEvidence(itemId?: UUID) {
  const query = itemId ? `?item=${encodeURIComponent(itemId)}` : "";
  return apiRequest<BuyCalculatorEvidence>(`/api/buy-calculator/evidence/${query}`);
}

export function calculateBuy(payload: BuyCalculationPayload) {
  return apiRequest<BuyCalculationResult>("/api/buy-calculator/calculate/", {
    method: "POST",
    body: payload
  });
}

export function createBoughtItItem(payload: BoughtItPayload) {
  return apiRequest<InventoryItemDetail>("/api/buy-calculator/bought-it/", {
    method: "POST",
    body: payload
  });
}

export interface ProfitLedgerQuery {
  stale_days?: number;
  fy?: string;
}

function profitQueryString(query: ProfitLedgerQuery = {}) {
  const params = new URLSearchParams();
  if (query.stale_days) params.set("stale_days", String(query.stale_days));
  if (query.fy) params.set("fy", query.fy);
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function getProfitLedger(query: ProfitLedgerQuery = {}) {
  return apiRequest<ProfitLedger>(`/api/profit/ledger/${profitQueryString(query)}`);
}

export function profitLedgerCsvUrl(query: ProfitLedgerQuery = {}) {
  return `/api/profit/ledger.csv${profitQueryString(query)}`;
}
