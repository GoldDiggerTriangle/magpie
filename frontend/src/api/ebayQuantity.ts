import { apiRequest } from "./client";

export interface EbayQuantityState {
  item_id: string; sku: string; state: string; label: string; urgent: boolean; can_write: boolean;
  allocation_id?: string; allocated?: number; target?: number; remaining?: number;
  inventory_available?: number | null; offer_available?: number | null; verified_at?: string | null;
  pending_units?: number; unlinked_orders?: number; attempt_id?: string | null;
  stock_revision?: number; stock_fingerprint?: string; allocation_revision?: number;
}
export function getEbayQuantity(itemId: string) {
  return apiRequest<EbayQuantityState>(`/api/items/${itemId}/ebay-quantity/`);
}
export function checkEbayQuantity(allocationId: string) {
  return apiRequest<EbayQuantityState>(`/api/ebay/allocations/${allocationId}/check/`, { method: "POST", body: {} });
}
export function updateEbayQuantity(state: EbayQuantityState, quantity: number) {
  return apiRequest<EbayQuantityState>(`/api/ebay/allocations/${state.allocation_id}/update/`, { method: "POST",
    body: { quantity, stock_revision: state.stock_revision, stock_fingerprint: state.stock_fingerprint, allocation_revision: state.allocation_revision } });
}
