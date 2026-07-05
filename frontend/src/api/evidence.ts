import { apiRequest } from "./client";
import type { DescriptorCapturePayload, DescriptorCaptureResult, DescriptorEvidenceLookup, UUID } from "../types";

export interface DescriptorLookupQuery {
  category?: UUID | "";
  terms?: string;
  attributes?: Record<string, unknown>;
}

export function getDescriptorEvidence(query: DescriptorLookupQuery) {
  const params = new URLSearchParams();
  if (query.category) {
    params.set("category", query.category);
  }
  if (query.terms) {
    params.set("terms", query.terms);
  }
  for (const [key, value] of Object.entries(query.attributes ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(`attr_${key}`, String(value));
    }
  }
  const text = params.toString();
  return apiRequest<DescriptorEvidenceLookup>(`/api/evidence/lookup/${text ? `?${text}` : ""}`);
}

export function captureDescriptorComparable(payload: DescriptorCapturePayload) {
  return apiRequest<DescriptorCaptureResult>("/api/evidence/capture/", {
    method: "POST",
    body: payload
  });
}
