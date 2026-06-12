import { apiRequest } from "./client";
import type {
  EbayCategoryAspectsResponse,
  EbayCategorySuggestionsResponse,
  EbayConnectionSummary,
  EbayStatus,
  MerchantLocationPayload,
  MerchantLocationStatus
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
