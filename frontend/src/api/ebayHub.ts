import { apiRequest } from "./client";

export interface HubDraft {
  id: string; item_id: string; sku: string; title: string; status: string;
  updated_at: string; offer_id: string; listing_id: string;
  publish_started_at: string | null; has_publish_error: boolean;
}
export interface EbayHub {
  as_of: string; provenance: string;
  drafts: HubDraft[];
  listings: Array<{ id: string; item_id: string; sku: string; title: string; draft_id: string; listing_id: string; url: string; listed_at: string }>;
  connection: { configured: boolean; connected: boolean; environment: string; requires_reconsent: boolean;
    access_token_expires_at: string | null; has_refresh_error: boolean; policies_fetched_at: string | null };
  orders: { last_synced_at: string | null; pending: number; duplicates: number };
}
export function getEbayHub() { return apiRequest<EbayHub>("/api/ebay/hub/"); }
export const draftDestination = (row: { item_id: string; id: string }) => `/inventory/${encodeURIComponent(row.item_id)}?draft=${encodeURIComponent(row.id)}#listings-channels`;
