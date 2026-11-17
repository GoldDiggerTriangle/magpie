import { apiRequest } from "./client";
import type { ListingDraft, ListingSpecific, UUID } from "../types";
import type { EbayDiagnostic } from "./ebayHealth";

export function getWorkflowDraft(id: UUID) {
  return apiRequest<ListingDraft>(`/api/listing-drafts/${id}/`);
}

export interface ReviewBlocker { key: string; message: string; field: string; diagnostic?: EbayDiagnostic }
export interface ListingReview {
  id: UUID; draft_revision: string; expires_at: string; mode: "full" | "quick"; offer_id: string;
  sku: string; price: string | null; sources: Record<string, string>;
  listing: { title: string; description_html: string; listing_format: string; quantity: number; currency: string };
  specifics: ListingSpecific[]; mapping: Record<string, string>;
  photos: Array<{ id: string; sha256: string; derivative: string; url?: string }>;
  metadata: null | { category_snapshot: null | { condition_policy: { required: boolean; conditions: Array<{ conditionId: string; conditionDescription: string }> } }; policies: Record<string, Array<{ id: string; name: string; terms: string[] }>> };
  checks: ReviewBlocker[]; publish_checks: ReviewBlocker[];
  fees: Array<{ type: string; value: string; currency: string }>;
  can_stage: boolean; can_publish: boolean;
}

export function reviewListing(id: UUID, mode: "full" | "quick") {
  return apiRequest<ListingReview>(`/api/listing-drafts/${id}/preview/`, { method: "POST", body: { mode } });
}
export function reconcileListing(id: UUID) {
  return apiRequest<ListingDraft>(`/api/listing-drafts/${id}/reconcile/`, { method: "POST", body: {} });
}
export interface PublishHealth { id: UUID; sku: string; status: string; started_at: string | null; attempt: string | null; message: string }
export function getPublishHealth() {
  return apiRequest<{ drafts: PublishHealth[] }>("/api/listing-drafts/publish-health/");
}
