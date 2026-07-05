import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { listChannelListings, markChannelListingEnded } from "../api/listing";
import type { InventoryItemDetail } from "../types";

export function TakeDownChecklist({ item }: { item: InventoryItemDetail }) {
  const queryClient = useQueryClient();
  const listings = useQuery({
    queryKey: ["item-channel-listings", item.id],
    queryFn: () => listChannelListings({ item: item.id, active: true })
  });
  const markEnded = useMutation({
    mutationFn: markChannelListingEnded,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["item-channel-listings", item.id] });
      queryClient.invalidateQueries({ queryKey: ["channel-listing-board"] });
    }
  });
  const active = listings.data?.results ?? [];
  if (active.length === 0) {
    return null;
  }
  if (item.quantity_remaining > 0 && item.quantity_sold > 0) {
    return (
      <section className="rounded border border-blue-700 bg-blue-50 p-4 text-blue-950">
        <p className="font-semibold">sold {item.quantity_sold} of {item.quantity_total} - listings still valid.</p>
      </section>
    );
  }
  if (item.quantity_remaining > 0) {
    return null;
  }
  const channels = active.map((listing) => listing.channel_label).join(", ");
  return (
    <section className="take-down-alert" aria-label="Take-down checklist">
      <div>
        <AlertTriangle className="h-5 w-5" aria-hidden="true" />
        <div>
          <h2>Still listed on: {channels} - take them down.</h2>
          <p>The item is sold out. End the real marketplace listings yourself, then tick each row here.</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {active.map((listing) => (
          <button className="btn-danger gap-2" disabled={markEnded.isPending} key={listing.id} onClick={() => markEnded.mutate(listing.id)} type="button">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            Mark {listing.channel_label} ended
          </button>
        ))}
      </div>
    </section>
  );
}
