import { apiRequest } from "./client";
import type { BoughtItPayload, BuyCalculationPayload, BuyCalculationResult, BuyCalculatorEvidence, InventoryItemDetail, ProfitSettings, UUID } from "../types";

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
