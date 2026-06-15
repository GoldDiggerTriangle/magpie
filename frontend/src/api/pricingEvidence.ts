import { apiRequest } from "./client";
import type { PricingEvidence, UUID } from "../types";

export function getPricingEvidence(itemId: UUID) {
  return apiRequest<PricingEvidence>(`/api/items/${itemId}/pricing-evidence/`);
}
