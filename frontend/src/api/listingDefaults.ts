import { apiRequest } from "./client";
import type { CategoryBranch, ListingEditorContext } from "./listing";
import type { ListingDraft } from "../types";

export const defaultFields = ["category_id", "category_name", "category_tree_id", "condition_id", "payment_policy_id", "fulfillment_policy_id", "return_policy_id", "merchant_location_key", "listing_format", "listing_duration"] as const;
export type ListingDefaultValues = Partial<Record<typeof defaultFields[number], string>>;
export interface ListingDefaults {
  category: string; category_name: string; values: ListingDefaultValues; revision: string; updated_at: string | null;
  editor: ListingEditorContext;
  validation: Array<{ field: string; state: string; message: string; fetched_at: string | null }>;
}
export interface DefaultsPreview { values: ListingDefaultValues; expected_revision: string; category_name: string; changes: Array<{ field: string; label: string; before: string; after: string; clears: boolean }> }
export const listListingDefaults = () => apiRequest<{ categories: Array<{ id: string; name: string; configured: boolean }> }>("/api/listing-defaults/");
export const getListingDefaults = (id: string, categoryId?: string) => apiRequest<ListingDefaults>(`/api/listing-defaults/${id}/${categoryId === undefined ? "" : `?category_id=${encodeURIComponent(categoryId)}`}`);
export const previewListingDefaults = (id: string, values: ListingDefaultValues) => apiRequest<DefaultsPreview>(`/api/listing-defaults/${id}/preview/`, { method: "POST", body: { values } });
export const saveListingDefaults = (id: string, preview: DefaultsPreview) => apiRequest<ListingDefaults>(`/api/listing-defaults/${id}/`, { method: "PUT", body: { values: preview.values, expected_revision: preview.expected_revision } });
export const refreshListingDefaultsMetadata = (id: string, options: { category_id: string; query?: string }) => apiRequest<ListingDefaults>(`/api/listing-defaults/${id}/refresh-metadata/`, { method: "POST", body: options });
export const browseListingDefaultsCategory = (id: string, categoryId: string) => apiRequest<CategoryBranch>(`/api/listing-defaults/${id}/category-children/?category_id=${encodeURIComponent(categoryId)}`);

export function defaultValues(draft: ListingDraft): ListingDefaultValues {
  return Object.fromEntries(defaultFields.map((key) => [key, key === "listing_format" ? draft.listing_format : String(draft.channel_data[key] ?? "")]));
}

// A local form model only. It is never sent to a draft endpoint or persisted.
export function defaultsForm(id: string, values: ListingDefaultValues): ListingDraft {
  return { id, item: "", status: "draft", channel: "ebay_au", channel_data: { ...values }, listing_format: values.listing_format === "fixed" || values.listing_format === "auction" ? values.listing_format : "",
    title: "", subtitle: "", description_html: "", price: null, currency: "AUD", quantity: 0, est_shipping_note: "", item_specifics: [], photo_ids: [], include_sku_footer: false, boilerplate: null, title_edited: false, description_edited: false, generated_meta: {}, exported_at: null, readiness_summary: { pass_count: 0, warn_count: 0, fail_count: 0 }, created_at: "", updated_at: "" };
}
