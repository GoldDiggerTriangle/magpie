import { useEffect, useState } from "react";
import { CheckCircle2, ExternalLink, Eye, RefreshCw, Send, ShieldCheck, Trash2, UploadCloud, X } from "lucide-react";
import { publishListingDraft, stageListingDraft, withdrawListingDraft } from "../api/listing";
import { getWorkflowDraft, reconcileListing, reviewListing, type ListingReview } from "../api/listingWorkflow";
import type { InventoryItemDetail, ListingDraft } from "../types";
import { groupedBlockers, ListingDescription, ListingFees, reviewedTime } from "./ListingPreviewContent";

export function ListingWorkflow({ draft, item, mode, onUpdated, beforeReview }: {
  draft: ListingDraft; item: InventoryItemDetail; mode: "full" | "quick";
  onUpdated: (draft: ListingDraft) => void; beforeReview?: () => Promise<ListingDraft>;
}) {
  const [review, setReview] = useState<ListingReview | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sku, setSku] = useState("");
  const [remove, setRemove] = useState(false);
  const inflight = ["publishing", "publish_unknown"].includes(draft.status);
  const terminal = ["published", "archived"].includes(draft.status) || Boolean(draft.channel_data.listing_id);
  useEffect(() => { setReview((old) => old && sameTime(old.draft_revision, draft.updated_at) ? old : null); setSku(""); }, [draft.id, draft.updated_at]);
  const expired = review ? new Date(review.expires_at).getTime() <= Date.now() : true;
  const sameRevision = review && sameTime(review.draft_revision, draft.updated_at)
    && review.listing.title === draft.title && review.listing.description_html === draft.description_html
    && review.price === draft.price && review.listing.quantity === draft.quantity && review.listing.currency === draft.currency
    && review.listing.listing_format === draft.listing_format
    && JSON.stringify(review.specifics) === JSON.stringify(draft.item_specifics)
    && JSON.stringify(review.photos.map((p) => p.id)) === JSON.stringify(draft.photo_ids)
    && Object.entries(review.mapping).every(([key, value]) => String(draft.channel_data[key] ?? "") === value);
  async function run(action: () => Promise<void>) {
    setBusy(true); setError("");
    try { await action(); } catch (e) {
      setReview(null);
      setError(e instanceof Error ? e.message : "Operation not confirmed. Reload and reconcile before retrying.");
      try { const current = await getWorkflowDraft(draft.id); if (current?.id) onUpdated(current); } catch { /* Preserve the error; no retry of a marketplace write. */ }
    } finally { setBusy(false); }
  }
  async function preview() {
    await run(async () => {
      const saved = beforeReview ? await beforeReview() : draft;
      setReview(await reviewListing(saved.id, mode)); setSku(""); setOpen(true);
    });
  }
  async function stage() {
    if (!review) return;
    await run(async () => {
      const updated = await stageListingDraft(draft.id, { review_id: review.id });
      onUpdated(updated); setSku("");
      setReview(await reviewListing(updated.id, mode)); setOpen(true);
    });
  }
  function fix(field: string) {
    if (field !== "staging" || mode === "quick") setOpen(false);
    window.location.hash = "listings-channels";
    window.dispatchEvent(new Event(`magpie:open-draft:${item.id}`));
    window.setTimeout(() => {
      const node = document.getElementById(`listing-${draft.id}-${field}`);
      node?.scrollIntoView?.({ block: "center" });
      const control = node?.matches("input,select,textarea,button") ? node : node?.querySelector("input,select,textarea,button");
      ((control ?? node) as HTMLElement | null)?.focus();
    }, 100);
  }
  if (terminal) return <div className="rounded border border-slate-400 p-4"><strong>{draft.status === "archived" ? "Archived history" : "Published listing"}</strong>{draft.channel_data.listing_id ? <a className="row-link mt-3" href={`https://www.ebay.com.au/itm/${encodeURIComponent(String(draft.channel_data.listing_id))}`} target="_blank" rel="noreferrer"><ExternalLink aria-hidden="true" size={18} />Open live listing</a> : null}</div>;
  return <section className="min-w-0 space-y-3" aria-label={mode === "quick" ? "Quick eBay review" : "eBay review and publish"}>
    <div className="flex flex-wrap gap-3">
      <button id={mode === "full" && !open ? `listing-${draft.id}-staging` : undefined} className="btn-primary gap-2" disabled={busy || inflight} onClick={() => void preview()} type="button"><Eye aria-hidden="true" size={18} />{mode === "quick" ? "Preview eBay listing" : "Review listing"}</button>
      {draft.channel_data.offer_id && !inflight && mode === "full" ? <button className="btn-secondary gap-2" disabled={busy} onClick={() => setRemove(true)} type="button"><Trash2 aria-hidden="true" size={18} />Remove unpublished offer</button> : null}
    </div>
    {inflight ? <div role="alert" className="rounded border-2 border-amber-700 bg-amber-50 p-4"><strong>Publish outcome needs reconciliation</strong><p>Do not retry or edit this draft. A timeout does not cancel a request.</p><button className="btn-secondary mt-3 gap-2" disabled={busy} onClick={() => void run(async () => { onUpdated(await reconcileListing(draft.id)); })} type="button"><RefreshCw aria-hidden="true" size={18} />Reconcile offer</button></div> : null}
    {error ? <p role="alert" className="break-words font-semibold text-red-800">{error}</p> : null}
    {draft.publish_error?.message ? <p role="status">{draft.publish_error.message}{draft.publish_error.http_status ? ` HTTP ${draft.publish_error.http_status}.` : ""}{draft.publish_error.error_ids?.length ? ` eBay codes: ${draft.publish_error.error_ids.join(", ")}.` : ""}</p> : null}
    {remove ? <div role="alertdialog" aria-label="Confirm unpublished offer removal" className="rounded border-2 border-red-800 p-4"><p>Remove this unpublished offer from eBay? Archive is available only after removal is confirmed. If eBay reports this offer live or ambiguous, removal stops. Ending a live listing is a separate decision.</p><div className="mt-3 flex flex-wrap gap-3"><button className="btn-secondary" disabled={busy} onClick={() => setRemove(false)} type="button">Cancel</button><button className="btn-primary gap-2" disabled={busy} onClick={() => void run(async () => { onUpdated(await withdrawListingDraft(draft.id)); setRemove(false); setReview(null); })} type="button"><Trash2 size={18} aria-hidden="true" />Confirm removal</button></div></div> : null}
    {open && review ? <div className="listing-review min-w-0 space-y-4 rounded border-2 border-slate-500 bg-white p-4" aria-label="Reviewed listing">
      <div className="flex items-start justify-between gap-3"><h3 className="text-xl font-semibold">{review.offer_id ? "Staged listing review" : "Listing preview"}</h3><button className="btn-icon" aria-label="Close listing preview" onClick={() => setOpen(false)} type="button"><X size={20} /></button></div>
      <h4 className="break-words text-lg font-semibold">{review.listing.title}</h4>
      <dl className="grid min-w-0 gap-3 sm:grid-cols-2">
        <Row label="Price" value={`${review.listing.currency} ${review.price ?? "[price not set]"}`} source={review.sources.price} />
        <Row label="eBay category" value={`${review.mapping.category_name || "[category mapping not set]"} ${review.mapping.category_id}`} source={review.sources.category_id} />
        <Row label="Condition" value={review.metadata?.category_snapshot?.condition_policy.required === false && !review.metadata.category_snapshot.condition_policy.conditions.length ? "Not used by this category" : review.metadata?.category_snapshot?.condition_policy.conditions.find((r) => r.conditionId === review.mapping.condition_id)?.conditionDescription || "[condition not set]"} source={review.sources.condition_id} />
        <Row label="Format / duration" value={`${review.listing.listing_format} / ${review.mapping.listing_duration || "[duration not set]"}`} />
        <Row label="Quantity" value={String(review.listing.quantity)} source={review.sources.quantity} />
        <Row label="Merchant location" value={review.mapping.merchant_location_key || "[location not set]"} source={review.sources.merchant_location_key} />
      </dl>
      {(["payment", "fulfillment", "return"] as const).map((kind) => {
        const chosen = review.metadata?.policies[kind]?.find((p) => p.id === review.mapping[`${kind}_policy_id`]);
        return <div key={kind}><h4 className="font-semibold">{kind === "fulfillment" ? "Postage" : kind === "return" ? "Returns" : "Payment"}</h4><p>{chosen?.name || "[policy not set]"}</p>{chosen?.terms.map((term, i) => <p className="break-words" key={i}>{term}</p>)}<small>{review.sources[`${kind}_policy_id`]}</small></div>;
      })}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{review.photos.map((p) => {
        const photo = item.photos.find((own) => own.id === p.id);
        return photo ? <img className="aspect-square w-full rounded border border-slate-400 object-contain" key={p.id} src={p.url || (p.derivative ? photo.derivatives.find((d) => d.id === p.derivative)?.fixed_url : photo.processed_url) || photo.thumb_url || ""} alt={photo.role || "Selected own photo"} /> : null;
      })}</div>
      <dl aria-label="Item specifics">{review.specifics?.map((r, i) => <div className="min-w-0 break-words border-b border-slate-300 py-2" key={i}><dt className="inline font-semibold">{r.name}:</dt>{" "}<dd className="inline">{r.value}</dd></div>)}</dl>
      <div><h4 className="font-semibold">Description</h4><ListingDescription html={review.listing.description_html} /><small>{review.sources.description_html}</small></div>
      {review.fees.length ? <ListingFees fees={review.fees} /> : null}
      {[...review.checks, ...review.publish_checks].length ? <div role="status" className="space-y-2 border-l-4 border-amber-700 pl-3"><strong>Before publishing</strong>{groupedBlockers([...review.checks, ...review.publish_checks]).map((b, i) => <div key={`${b.key}-${i}`}><p>{b.message}</p><button className="text-left font-semibold text-blue-800 underline" onClick={() => fix(b.field)} type="button">Go to {b.field === "staging" ? review.offer_id ? "Update staged offer" : "Stage reviewed listing" : b.field.replace(/_/g, " ")}</button></div>)}</div> : null}
      {mode === "full" ? <div id={`listing-${draft.id}-staging`} tabIndex={-1} className="listing-field-anchor">{review.can_stage ? <button className="btn-secondary gap-2" disabled={busy || !sameRevision || expired} onClick={() => void stage()} type="button"><UploadCloud aria-hidden="true" size={18} />{review.offer_id ? "Update staged offer" : "Stage reviewed listing"}</button> : <p>Resolve the listing blockers above before {review.offer_id ? "Update staged offer" : "Stage reviewed listing"}.</p>}</div> : null}
      {mode === "quick" && !review.can_publish ? <button className="btn-secondary" onClick={() => fix("title")} type="button">Open full editor to update and review</button> : null}
      {mode === "full" && review.can_publish ? <label className="label">Type {review.sku} to confirm<input autoComplete="off" className="field" value={sku} onChange={(e) => setSku(e.target.value)} /></label> : null}
      <button className="btn-primary gap-2" disabled={busy || !review.can_publish || !sameRevision || expired || (mode === "full" && sku !== review.sku)} onClick={() => void run(async () => { const updated = await publishListingDraft(draft.id, mode === "full" ? sku : "", { review_id: review.id, mode }); onUpdated(updated); setReview(null); setOpen(false); })} type="button"><Send aria-hidden="true" size={18} />{mode === "quick" ? "Post live to eBay" : "Confirm publish to eBay"}</button>
      {expired || !sameRevision ? <p role="alert">Review expired or draft changed. Review again before continuing.</p> : null}
      <p className="flex items-start gap-2 text-sm"><ShieldCheck size={18} aria-hidden="true" />{busy ? "Waiting for a confirmed response. Do not send again." : <time dateTime={review.draft_revision}>{reviewedTime(review.draft_revision)}</time>}</p>
    </div> : null}
    {draft.status === "ready" && !open ? <span className="sr-only"><CheckCircle2 />Ready for review</span> : null}
  </section>;
}

function Row({ label, value, source }: { label: string; value: string; source?: string }) {
  return <div className="min-w-0 border-b border-slate-300 py-2"><dt className="font-semibold">{label}</dt><dd className="break-words">{value}</dd>{source ? <dd className="text-sm">Source: {source}</dd> : null}</div>;
}

function sameTime(a: string, b: string) {
  return Number.isFinite(Date.parse(a)) && Date.parse(a) === Date.parse(b);
}
