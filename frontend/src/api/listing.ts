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

export interface EditorPolicy {
  id: string; name: string; terms: string[]; summary: string; headline?: string; fetched_at: string | null; provenance: string;
}
export interface ListingEditorContext {
  metadata: {
    browse_starts?: CategoryBranchNode[]; browse_starts_provenance?: string;
    category_id: string; category_stale: boolean; policies_stale: boolean;
    category_snapshot: null | {
      category: { category_id: string; category_name: string; category_tree_id: string; is_leaf: boolean };
      aspects: null | Array<{ name: string; required: boolean; values: string[] }>;
      condition_policy: null | { required: boolean; conditions: Array<{ conditionId: string; conditionDescription: string }> };
      listing_types: null | { formats: Record<string, string[]> };
      fetched_at: string | null; provenance: string;
    };
    category_search: { query?: string; fetched_at?: string; provenance?: string; suggestions?: Array<{ category_id: string; category_name: string; category_tree_id: string; is_leaf: boolean; category_path?: string[]; ancestors?: CategoryBranchNode[] }> };
    policies: Record<"payment" | "fulfillment" | "return", EditorPolicy[]>;
    policies_fetched_at: string | null; policies_provenance: string;
    locations: Array<{ id: string; name: string; address: string; verified: boolean; fetched_at: string | null; provenance: string }>;
  };
  sources: Record<string, string>;
  price_options: Array<{ id: string; value: string; label: string }>;
  price_source: null | { kind?: string; label?: string; value?: string };
  checks: Array<ListingCheck & { field: string }>;
  read_only: boolean; staged_local_changes: boolean;
  effective_duration?: string; duration_source?: string;
}

export function getListingEditor(id: UUID, categoryId?: string) {
  const query = categoryId === undefined ? "" : `?category_id=${encodeURIComponent(categoryId)}`;
  return apiRequest<ListingEditorContext>(`/api/listing-drafts/${id}/editor/${query}`);
}

export function refreshListingMetadata(id: UUID, options: { category_id?: string; query?: string }) {
  return apiRequest<{ draft: ListingDraft; editor: ListingEditorContext }>(`/api/listing-drafts/${id}/refresh-metadata/`, { method: "POST", body: options });
}

export interface CategoryBranchNode { category_id: string; category_name: string; category_tree_id?: string; is_leaf?: boolean | null }
export interface CategoryBranch { category: CategoryBranchNode; children: CategoryBranchNode[]; fetched_at: string; provenance: string; marketplace: string }
export function getListingCategoryChildren(id: UUID, categoryId: string) {
  return apiRequest<CategoryBranch>(`/api/listing-drafts/${id}/category-children/?category_id=${encodeURIComponent(categoryId)}`);
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

export function archiveListingDraft(id: UUID) {
  return apiRequest<ListingDraft>(`/api/listing-drafts/${id}/archive/`, { method: "POST", body: {} });
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
