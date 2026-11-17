import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Send } from "lucide-react";
import { createItemListingDraft, listItemListingDrafts } from "../api/listing";
import type { InventoryItemDetail, ListingDraft, UUID } from "../types";

export const itemDraftKey = (id: UUID) => ["listing-drafts", id];
export const activeEbayDraft = (draft: ListingDraft) => draft.channel === "ebay_au"
  && !["published", "archived"].includes(draft.status) && !draft.channel_data.listing_id;

export function canonicalEbayDraft(rows: ListingDraft[]) {
  // The server orders active keepers first. History must never conceal a newer active draft.
  return rows.find(activeEbayDraft) ?? rows.find((row) => row.channel === "ebay_au" && row.status === "published")
    ?? rows.find((row) => row.channel === "ebay_au") ?? null;
}

export function ebayDraftStatus(draft: ListingDraft | null) {
  if (!draft) return "none";
  if (draft.status === "publish_unknown") return "check result";
  if (draft.status === "publishing") return "publishing";
  if (draft.status === "publish_failed" || draft.publish_error?.message) return "failed";
  if (draft.status === "published" || draft.channel_data.listing_id) return "live";
  if (draft.status === "archived") return "archived history";
  if (draft.status === "staged" || draft.channel_data.offer_id) return "staged";
  return "draft";
}

export function useItemDrafts(id: UUID) {
  return useQuery({ queryKey: itemDraftKey(id), queryFn: () => listItemListingDrafts(id) });
}

export function openItemDraft(itemId: UUID, draftId: UUID) {
  window.dispatchEvent(new CustomEvent(`magpie:open-draft:${itemId}`, { detail: { draftId } }));
}

export function EbayListingEntry({ item }: { item: InventoryItemDetail }) {
  const client = useQueryClient();
  const drafts = useItemDrafts(item.id);
  const rows = drafts.data?.results ?? [];
  const canonical = canonicalEbayDraft(rows);
  const live = rows.find((row) => row.channel === "ebay_au" && row.channel_data.listing_id);
  const create = useMutation({
    mutationFn: () => createItemListingDraft(item.id),
    onSuccess: (draft) => {
      client.setQueryData(itemDraftKey(item.id), { ...drafts.data, results: [draft, ...rows.filter((row) => row.id !== draft.id)] });
      openItemDraft(item.id, draft.id);
      void client.invalidateQueries({ queryKey: itemDraftKey(item.id) });
    }
  });
  return <div className="ebay-listing-entry min-w-0 space-y-2" aria-label="eBay listing entry">
    <div className="flex min-w-0 flex-wrap items-center gap-3">
      <button className="btn-primary gap-2" disabled={drafts.isPending || drafts.isError || create.isPending} type="button"
        onClick={() => canonical ? openItemDraft(item.id, canonical.id) : create.mutate()}><Send size={18} aria-hidden="true" />List on eBay</button>
      <span role="status">{drafts.isPending ? "Loading draft status" : drafts.isError ? "Draft status unavailable" : ebayDraftStatus(canonical)}</span>
      {live ? <a className="row-link gap-2" href={`https://www.ebay.com.au/itm/${encodeURIComponent(String(live.channel_data.listing_id))}`} target="_blank" rel="noreferrer"><ExternalLink size={18} aria-hidden="true" />View on eBay</a> : null}
    </div>
    {drafts.isError ? <p role="alert">Drafts could not load. Check your session and <button className="underline" onClick={() => void drafts.refetch()} type="button">retry</button>.</p> : null}
    {create.error ? <p role="alert">{create.error instanceof Error ? create.error.message : "Draft could not open."}</p> : null}
  </div>;
}
