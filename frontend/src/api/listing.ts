import { ApiError, apiRequest } from "./client";
import type {
  ListingBoilerplate,
  ChannelListing,
  ChannelListingBoard,
  ChannelListingPayload,
  ChannelListingSeedResult,
  CopyPack,
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

export function getItemCopyPack(
  itemId: UUID,
  options: { channel?: CopyPack["channel"]; evidence_price?: string; evidence_label?: string } = {}
) {
  const params = new URLSearchParams();
  if (options.channel) params.set("channel", options.channel);
  if (options.evidence_price) params.set("evidence_price", options.evidence_price);
  if (options.evidence_label) params.set("evidence_label", options.evidence_label);
  const query = params.toString();
  return apiRequest<CopyPack>(`/api/items/${itemId}/copy-pack/${query ? `?${query}` : ""}`);
}

export function listChannelListings(params: { item?: UUID; active?: boolean } = {}) {
  const query = new URLSearchParams();
  if (params.item) query.set("item", params.item);
  if (typeof params.active === "boolean") query.set("active", params.active ? "true" : "false");
  const suffix = query.toString();
  return apiRequest<PaginatedResponse<ChannelListing>>(`/api/channel-listings/${suffix ? `?${suffix}` : ""}`);
}

export function createChannelListing(payload: ChannelListingPayload) {
  return apiRequest<ChannelListing>("/api/channel-listings/", {
    method: "POST",
    body: payload
  });
}

export function markChannelListingEnded(id: UUID) {
  return apiRequest<ChannelListing>(`/api/channel-listings/${id}/mark-ended/`, {
    method: "POST",
    body: {}
  });
}

export function getChannelListingBoard() {
  return apiRequest<ChannelListingBoard>("/api/channel-listings/board/");
}

export function seedEbayChannelListings() {
  return apiRequest<ChannelListingSeedResult>("/api/channel-listings/seed-ebay/", {
    method: "POST",
    body: {}
  });
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
