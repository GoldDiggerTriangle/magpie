import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useState } from "react";
import { createItemListingDraft, listItemListingDrafts } from "../api/listing";
import type { InventoryItemDetail } from "../types";
import { ListingWorkflow } from "./ListingWorkflow";

export function QuickPublishPanel({ item }: { item: InventoryItemDetail }) {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const drafts = useQuery({ queryKey: ["item-listing-drafts", item.id], queryFn: () => listItemListingDrafts(item.id) });
  const draft = drafts.data?.results.find((d) => !["published", "archived"].includes(d.status) && !d.channel_data.listing_id);
  async function openEditor() {
    setBusy(true); setError("");
    try {
      await createItemListingDraft(item.id); // Server reuses the canonical active draft.
      await client.invalidateQueries({ queryKey: ["item-listing-drafts", item.id] });
      await client.invalidateQueries({ queryKey: ["listing-drafts", item.id] });
      window.location.hash = "listings-channels";
      window.setTimeout(() => window.dispatchEvent(new Event(`magpie:open-draft:${item.id}`)), 0);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not open the canonical draft."); }
    finally { setBusy(false); }
  }
  return <section className="min-w-0 space-y-3" aria-label="eBay listing actions">
    <button className="btn-secondary gap-2" disabled={busy || drafts.isLoading} onClick={() => void openEditor()} type="button"><Pencil size={18} aria-hidden="true" />{draft ? "Open eBay draft" : "Create eBay draft"}</button>
    {draft ? <ListingWorkflow draft={draft} item={item} mode="quick" onUpdated={() => {
      void client.invalidateQueries({ queryKey: ["item-listing-drafts", item.id] });
      void client.invalidateQueries({ queryKey: ["listing-drafts", item.id] });
      void client.invalidateQueries({ queryKey: ["item", item.id] });
    }} /> : null}
    {error || drafts.error ? <p role="alert">{error || "Could not load drafts. Check your session and reload."}</p> : null}
  </section>;
}
