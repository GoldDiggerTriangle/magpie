import { apiRequest } from "./client";
import type { MetalSpotQuote, PaginatedResponse, ProfitBreakdown, UUID, ValuationReport, ValuationReportPayload } from "../types";

export function listItemValuationReports(itemId: UUID) {
  return apiRequest<PaginatedResponse<ValuationReport>>(`/api/items/${itemId}/valuation-reports/`);
}

export function createValuationReport(itemId: UUID, payload: ValuationReportPayload) {
  return apiRequest<ValuationReport>(`/api/items/${itemId}/valuation-reports/`, {
    method: "POST",
    body: payload
  });
}

export function getValuationReport(id: UUID) {
  return apiRequest<ValuationReport>(`/api/valuation-reports/${id}/`);
}

export function updateValuationReport(id: UUID, payload: Partial<ValuationReportPayload>) {
  return apiRequest<ValuationReport>(`/api/valuation-reports/${id}/`, {
    method: "PATCH",
    body: payload
  });
}

export function deleteValuationReport(id: UUID) {
  return apiRequest<void>(`/api/valuation-reports/${id}/`, { method: "DELETE" });
}

export function setCurrentValuationReport(id: UUID) {
  return apiRequest<ValuationReport>(`/api/valuation-reports/${id}/set-current/`, { method: "POST" });
}

export function getReportProfit(id: UUID, price: string) {
  return apiRequest<ProfitBreakdown>(`/api/valuation-reports/${id}/profit/?price=${encodeURIComponent(price)}`);
}

export function getMetalSpot(metal: string, currency = "AUD", refresh = false) {
  const params = new URLSearchParams({ metal, currency });
  if (refresh) {
    params.set("refresh", "true");
  }
  return apiRequest<MetalSpotQuote>(`/api/metals/spot/?${params.toString()}`);
}
