import { apiRequest } from "./client";
import type { EbayConnectionSummary, EbayStatus } from "../types";

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
