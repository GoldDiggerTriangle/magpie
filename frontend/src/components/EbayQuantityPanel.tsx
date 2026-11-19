import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useRefreshableForm } from "./useRefreshableForm";
import { Link } from "react-router-dom";
import { AlertTriangle, RefreshCw, Upload } from "lucide-react";
import { checkEbayQuantity, getEbayQuantity, updateEbayQuantity, type EbayQuantityState } from "../api/ebayQuantity";

export function EbayQuantityPanel({ itemId, initial, showAllocationUnknown = true }: { itemId: string; initial?: EbayQuantityState; showAllocationUnknown?: boolean }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["ebay-quantity", itemId], queryFn: () => getEbayQuantity(itemId), initialData: initial, retry: false, refetchOnWindowFocus: false });
  const data = query.data;
  const source = useMemo(() => data ? { wanted: data.target ?? 0 } : null, [data]);
  const [form, setForm] = useRefreshableForm(itemId, source, { wanted: 0 });
  const wanted = form.wanted;
  const setWanted = (wanted: number) => setForm({ wanted });
  const [reviewed, setReviewed] = useState(false);
  useEffect(() => { setReviewed(false); }, [data]);
  const changed = (value: EbayQuantityState) => {
    client.setQueryData(["ebay-quantity", itemId], value);
    void client.invalidateQueries({ queryKey: ["ebay-hub"] });
    setReviewed(false);
  };
  const check = useMutation({ mutationFn: () => checkEbayQuantity(data!.allocation_id!), onSuccess: changed });
  const update = useMutation({ mutationFn: () => updateEbayQuantity(data!, wanted), onSuccess: changed });
  if (!data || data.state === "not_listed") return null;
  if (data.state === "allocation_not_recorded") return showAllocationUnknown ? <p className="min-w-0 py-2 font-semibold [overflow-wrap:anywhere]">eBay listing quantity was not recorded</p> : null;
  const busy = check.isPending || update.isPending;
  const error = check.error || update.error;
  const valid = wanted > 0 && wanted <= (data.remaining ?? 0) && !(wanted > (data.target ?? 0) && ((data.pending_units ?? 0) || (data.unlinked_orders ?? 0)));
  return <section id={`ebay-quantity-${itemId}`} tabIndex={-1} aria-label={`eBay quantity ${data.sku}`} className={`min-w-0 space-y-3 border-l-4 p-4 [overflow-wrap:anywhere] ${data.urgent ? "border-red-700 bg-red-50" : "border-slate-600 bg-white"}`}>
    <h2 className="flex min-w-0 flex-wrap items-center gap-2 text-lg font-bold">{data.urgent ? <AlertTriangle size={20} aria-hidden="true" /> : null}{data.label}</h2>
    <p>{data.remaining} known remaining · {data.pending_units ?? 0} pending eBay units · {data.unlinked_orders ?? 0} unlinked orders</p>
    {data.unlinked_orders ? <Link className="row-link min-h-11" to="/ebay/orders">Resolve unlinked orders before increasing quantity</Link> : null}
    <p>Inventory available: {data.inventory_available ?? "not checked"} · Offer available: {data.offer_available ?? "not checked"}</p>
    <p>{data.verified_at ? `Last verified ${new Date(data.verified_at).toLocaleString("en-AU")}` : "Quantity pair not yet verified."}</p>
    {data.remaining === 0 ? <Link className="btn-secondary" to="/listings">Open take-down checklist</Link> : null}
    {data.state !== "take_down" ? <>
      <button className="btn-secondary min-h-11 gap-2" type="button" disabled={busy} onClick={() => check.mutate()}><RefreshCw size={18} aria-hidden="true" />{data.attempt_id ? "Reconcile quantity result" : "Check eBay quantity"}</button>
      {data.can_write ? <div className="min-w-0 space-y-3">
        <label className="block space-y-2"><span>Intended eBay quantity</span><input className="field w-full min-w-0 text-base" type="number" min="1" max={data.remaining} value={wanted} onChange={(e) => { setWanted(Number(e.target.value)); setReviewed(false); }} /></label>
        {wanted > (data.target ?? 0) ? <p>Restock increase - only after confirming physical stock and pending orders.</p> : null}
        <p className="font-bold">Update eBay: {Math.min(data.inventory_available ?? 0, data.offer_available ?? 0)} → {wanted}</p>
        <label className="flex min-h-11 items-start gap-3"><input type="checkbox" className="mt-1 h-5 w-5 shrink-0" checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} /><span>Confirm this exact quantity change</span></label>
        <button className="btn-primary min-h-11 gap-2" type="button" disabled={busy || !valid || !reviewed} onClick={() => update.mutate()}><Upload size={18} aria-hidden="true" />Update quantity on eBay</button>
      </div> : null}
    </> : null}
    {data.attempt_id ? <p role="alert">Outcome unresolved. No new quantity write until reconciliation.</p> : null}
    {error ? <p role="alert">{error instanceof Error ? error.message : "Not confirmed. Check the result before continuing."}</p> : null}
  </section>;
}
