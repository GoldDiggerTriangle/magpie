import { apiRequest } from "./client";
import type {
  EbayCategoryAspectsResponse,
  EbayCategorySuggestionsResponse,
  EbayConnectionSummary,
  EbayOrderDuplicateCandidate,
  EbayOrderStaging,
  EbayOrderSyncResult,
  EbayStatus,
  MerchantLocationPayload,
  MerchantLocationStatus,
  PaginatedResponse,
  SaleRecord,
  UUID
} from "../types";

export function getEbayStatus() {
  return apiRequest<EbayStatus>("/api/ebay/status/");
}

export function startEbayConnect() {
  return apiRequest<{ consent_url: string }>("/api/ebay/connect/start/", {
    method: "POST",
    body: {}
  });
}

export function completeEbayConnect(payload: { pasted_url: string } | { code: string; state: string }) {
  return apiRequest<EbayConnectionSummary>("/api/ebay/connect/complete/", {
    method: "POST",
    body: payload
  });
}

export function refreshEbayPolicies() {
  return apiRequest<EbayStatus>("/api/ebay/refresh-policies/", {
    method: "POST",
    body: {}
  });
}

export function disconnectEbay() {
  return apiRequest<void>("/api/ebay/disconnect/", { method: "POST", body: {} });
}

export function getEbayCategorySuggestions(q: string) {
  return apiRequest<EbayCategorySuggestionsResponse>(`/api/ebay/category-suggestions/?q=${encodeURIComponent(q)}`);
}

export function getEbayCategoryAspects(categoryId: string) {
  return apiRequest<EbayCategoryAspectsResponse>(`/api/ebay/category-aspects/?category_id=${encodeURIComponent(categoryId)}`);
}

export function getMerchantLocation() {
  return apiRequest<MerchantLocationStatus>("/api/ebay/merchant-location/");
}

export function createMerchantLocation(payload: MerchantLocationPayload) {
  return apiRequest<MerchantLocationStatus>("/api/ebay/merchant-location/", {
    method: "POST",
    body: payload
  });
}

export function syncEbayOrders(payload: { first_sync_days?: number; lookback_days?: number } = {}) {
  return apiRequest<EbayOrderSyncResult>("/api/ebay/orders/sync/", {
    method: "POST",
    body: payload
  });
}

export function listEbayOrderStaging(status = "pending") {
  return apiRequest<PaginatedResponse<EbayOrderStaging>>(`/api/ebay/order-staging/?status=${encodeURIComponent(status)}`);
}

export function resolveEbayOrderStaging(
  id: UUID,
  payload:
    | { action: "link"; item: UUID; cost_basis_override?: string | null; notes?: string }
    | { action: "quick_create"; title?: string; quantity_total?: number; acquisition_cost?: string | null; cost_basis_override?: string | null; notes?: string }
    | { action: "mark_external"; cost_basis_override?: string | null; notes?: string }
) {
  return apiRequest<SaleRecord>(`/api/ebay/order-staging/${id}/resolve/`, {
    method: "POST",
    body: payload
  });
}

export function listEbayOrderDuplicates(status = "pending") {
  return apiRequest<PaginatedResponse<EbayOrderDuplicateCandidate>>(`/api/ebay/order-duplicates/?status=${encodeURIComponent(status)}`);
}

export function resolveEbayOrderDuplicate(id: UUID, payload: { action: "link" | "dismiss" }) {
  return apiRequest<EbayOrderDuplicateCandidate>(`/api/ebay/order-duplicates/${id}/resolve/`, {
    method: "POST",
    body: payload
  });
}
