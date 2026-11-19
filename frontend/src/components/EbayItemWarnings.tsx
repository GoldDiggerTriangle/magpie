import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { getEbayQuantity } from "../api/ebayQuantity";
import { listChannelListings } from "../api/listing";
import type { InventoryItemDetail } from "../types";
import { focusItemField } from "./itemNavigation";

export function EbayItemWarnings({ item }: { item: InventoryItemDetail }) {
  const quantity = useQuery({ queryKey: ["ebay-quantity", item.id], queryFn: () => getEbayQuantity(item.id), retry: false, refetchOnWindowFocus: false });
  const listings = useQuery({ queryKey: ["item-channel-listings", item.id], queryFn: () => listChannelListings({ item: item.id, active: true }) });
  const takeDown = item.quantity_remaining === 0 && Boolean(listings.data?.results.length);
  const urgent = quantity.data?.urgent || quantity.data?.attempt_id;
  if (!takeDown && !urgent) return null;
  return <div className="item-urgent" role="alert"><AlertTriangle size={20} aria-hidden="true" />
    <div>{takeDown ? <p>Sold out but still listed. End the marketplace listing, then complete the take-down checklist.</p> : <p>{quantity.data?.label || "Check the eBay quantity result before making another change."}</p>}
      <button className="row-link" type="button" onClick={() => focusItemField(takeDown ? `take-down-${item.id}` : `ebay-quantity-${item.id}`)}>{takeDown ? "Open take-down checklist" : "Review eBay quantity"}</button>
    </div>
  </div>;
}
