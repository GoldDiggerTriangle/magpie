import { ApiError, apiRequest } from "./client";
import type {
  ListingBoilerplate,
  EbayAspectCheck,
  ListingCheck,
  ListingDraft,
  ListingDraftPayload,
  PaginatedResponse,
  StagedOfferReview,
  UUID
} from "../types";

export function listItemListingDrafts(itemId: UUID) {
  return apiRequest<PaginatedResponse<ListingDraft>>(`/api/items/${itemId}/listing-drafts/`);
}

export function createItemListingDraft(itemId: UUID) {
  return apiRequest<ListingDraft>(`/api/items/${itemId}/listing-drafts/`, {
    method: "POST",
    body: {}
  });
}

export function getListingDraft(id: UUID) {
  return apiRequest<ListingDraft>(`/api/listing-drafts/${id}/`);
}

export function updateListingDraft(id: UUID, payload: ListingDraftPayload) {
  return apiRequest<ListingDraft>(`/api/listing-drafts/${id}/`, {
    method: "PATCH",
    body: payload
  });
}

export function deleteListingDraft(id: UUID) {
  return apiRequest<void>(`/api/listing-drafts/${id}/`, { method: "DELETE" });
}

export function generateListingDraft(
  id: UUID,
  fields: Array<"title" | "description" | "specifics" | "price">,
  confirmOverwrite = false
) {
  return apiRequest<ListingDraft>(`/api/listing-drafts/${id}/generate/`, {
    method: "POST",
    body: { fields, confirm_overwrite: confirmOverwrite }
  });
}

export function getListingReadiness(id: UUID) {
  return apiRequest<ListingCheck[]>(`/api/listing-drafts/${id}/readiness/`);
}

export function getListingAspectCheck(id: UUID) {
  return apiRequest<EbayAspectCheck>(`/api/listing-drafts/${id}/aspects-check/`);
}

export function stageListingDraft(id: UUID, payload: { override_missing_aspects?: boolean; override_reason?: string } = {}) {
  return apiRequest<ListingDraft>(`/api/listing-drafts/${id}/stage/`, {
    method: "POST",
    body: payload
  });
}

export function withdrawListingDraft(id: UUID) {
  return apiRequest<ListingDraft>(`/api/listing-drafts/${id}/withdraw/`, {
    method: "POST",
    body: {}
  });
}

export function getStagedOfferReview(id: UUID) {
  return apiRequest<StagedOfferReview>(`/api/listing-drafts/${id}/staged-review/`);
}

export function publishListingDraft(id: UUID, confirmSku: string) {
  return apiRequest<ListingDraft>(`/api/listing-drafts/${id}/publish/`, {
    method: "POST",
    body: { confirm_sku: confirmSku }
  });
}

export function listListingBoilerplates() {
  return apiRequest<PaginatedResponse<ListingBoilerplate>>("/api/listing-boilerplates/");
}

export async function downloadListingZip(id: UUID) {
  const response = await fetch(`/api/listing-drafts/${id}/export/`, {
    credentials: "include"
  });
  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }
  return response.blob();
}
