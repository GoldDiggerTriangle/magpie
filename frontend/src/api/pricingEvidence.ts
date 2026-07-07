import { apiRequest } from "./client";
import type { PricingEvidence, PricingEvidenceCaptureDraftResult, UUID } from "../types";

export function getPricingEvidence(itemId: UUID) {
  return apiRequest<PricingEvidence>(`/api/items/${itemId}/pricing-evidence/`);
}

export function parsePricingEvidenceCaptureDraft(
  itemId: UUID,
  payload: { url?: string; screenshot?: File | null }
) {
  const body = new FormData();
  if (payload.url?.trim()) {
    body.set("url", payload.url.trim());
  }
  if (payload.screenshot) {
    body.set("screenshot", payload.screenshot);
  }
  return apiRequest<PricingEvidenceCaptureDraftResult>(`/api/items/${itemId}/pricing-evidence/capture-draft/`, {
    method: "POST",
    multipart: body
  });
}
