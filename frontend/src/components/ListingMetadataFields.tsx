import { useMutation } from "@tanstack/react-query";
import { RefreshCw, Search } from "lucide-react";
import { useState } from "react";
import { refreshListingMetadata, type ListingEditorContext } from "../api/listing";
import type { ListingDraft } from "../types";
import { ListingCategoryBrowse } from "./ListingCategoryBrowse";

export const listingFieldId = (id: string, field: string) => `listing-${id}-${field}`;
export const channelValue = (draft: ListingDraft, key: string) => String(draft.channel_data[key] ?? "");

export function FieldSource({ context, field }: { context?: ListingEditorContext; field: string }) {
  return <small className="listing-source">Source: {context?.sources[field] || "Saved draft; source not recorded"}</small>;
}

export function ListingMetadataFields({ draft, context, onChange, flush, onRefreshed }: {
  draft: ListingDraft; context?: ListingEditorContext;
  onChange: (draft: ListingDraft) => void; flush: () => Promise<ListingDraft>;
  onRefreshed: (draft: ListingDraft) => void;
}) {
  const [search, setSearch] = useState("");
  const [requested, setRequested] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const metadata = context?.metadata;
  const category = metadata?.category_snapshot;
  const condition = category?.condition_policy;
  const update = (patch: Record<string, string>) => onChange({ ...draft, channel_data: { ...draft.channel_data, ...patch } });
  const refresh = useMutation({
    mutationFn: async (query?: string) => {
      await flush();
      return refreshListingMetadata(draft.id, { category_id: channelValue(draft, "category_id"), ...(query ? { query } : {}) });
    },
    onSuccess: (result) => { onRefreshed(result.draft); setRequested(true); }
  });
  const suggestions = metadata?.category_search.suggestions ?? [];
  return <div className="listing-metadata space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h3 className="section-title">eBay listing details</h3>
        <p className="listing-source">{metadata?.policies_provenance || "Saved eBay metadata"} · Fetched: {metadata?.policies_fetched_at ? new Date(metadata.policies_fetched_at).toLocaleString() : "not available"}</p>
        {metadata?.policies_stale || metadata?.category_stale ? <p className="listing-source">Missing or older-than-7-day snapshot. Refresh to check current choices.</p> : null}
      </div>
      <button type="button" className="btn-secondary gap-2" disabled={refresh.isPending} onClick={() => refresh.mutate(undefined)}><RefreshCw size={18} />Refresh from eBay</button>
    </div>
    {refresh.error ? <p role="alert" className="text-red-800">{refresh.error instanceof Error ? refresh.error.message : "Refresh failed; saved metadata remains available."}</p> : null}
    {requested && !refresh.isPending ? <p role="status">Metadata refreshed. No listing values were selected or staged.</p> : null}
    <div id={listingFieldId(draft.id, "category_id")} tabIndex={-1} className="listing-field-anchor space-y-2">
      <label className="label"><span>Search eBay category</span><input className="field" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="e.g. gold nugget" /></label>
      <button type="button" className="btn-secondary gap-2" disabled={!search.trim() || refresh.isPending} onClick={() => refresh.mutate(search.trim())}><Search size={18} />Search eBay</button>
      <button type="button" className="btn-secondary ml-2" aria-expanded={browsing} onClick={() => setBrowsing(!browsing)}>Browse categories</button>
      {browsing ? <ListingCategoryBrowse draftId={draft.id} starts={Array.from(new Map(suggestions.flatMap((node) => node.ancestors ?? []).map((node) => [node.category_id, node])).values())} onSelect={(node) => { update({ category_id: node.category_id, category_name: node.category_name, category_tree_id: node.category_tree_id || "", ...(node.category_id !== channelValue(draft, "category_id") ? { condition_id: "" } : {}) }); setBrowsing(false); }} /> : null}
      {suggestions.map((option) => <button type="button" className="btn-secondary listing-category-option" key={option.category_id} disabled={option.is_leaf !== true} onClick={() => update({ category_id: option.category_id, category_name: option.category_name, category_tree_id: option.category_tree_id, ...(option.category_id !== channelValue(draft, "category_id") ? { condition_id: "" } : {}) })}>
        <span>{(option.category_path?.length ? option.category_path : [option.category_name]).join(" > ")} · ID {option.category_id}{option.is_leaf !== true ? " (choose a leaf category)" : ""}</span>
      </button>)}
      {metadata?.category_search.fetched_at ? <p className="listing-source">{metadata.category_search.provenance} · Fetched: {new Date(metadata.category_search.fetched_at).toLocaleString()}</p> : null}
      <label className="label"><span>Chosen eBay category ID</span><input className="field" inputMode="numeric" value={channelValue(draft, "category_id")} onChange={(event) => update({ category_id: event.target.value, category_name: "", condition_id: "", listing_duration: "" })} /></label>
      <p className="font-semibold break-words">{channelValue(draft, "category_name") || "No category confirmed"} {channelValue(draft, "category_id") ? `· ID ${channelValue(draft, "category_id")}` : ""}</p>
      {category && !channelValue(draft, "category_name") ? <button className="btn-secondary" type="button" onClick={() => update({ category_name: category.category.category_name, category_tree_id: category.category.category_tree_id })}>Confirm {category.category.category_name} · ID {category.category.category_id}</button> : null}
      {category ? <p className="listing-source">{category.provenance} · Fetched: {category.fetched_at ? new Date(category.fetched_at).toLocaleString() : "not recorded"}</p> : null}
      <FieldSource context={context} field="category_id" />
    </div>
    <label className="label listing-field-anchor" id={listingFieldId(draft.id, "condition_id")}>
      <span>eBay condition</span>
      {condition && !condition.required && condition.conditions.length === 0 ? <strong className="block">Not used by this category</strong> : <select aria-label="eBay condition" className="field" value={channelValue(draft, "condition_id")} onChange={(event) => update({ condition_id: event.target.value })}>
        <option value="">{condition ? "Choose condition" : "Refresh category metadata first"}</option>
        {(condition?.conditions ?? []).map((row) => <option key={row.conditionId} value={row.conditionId}>{row.conditionDescription} ({row.conditionId})</option>)}
        {channelValue(draft, "condition_id") && !condition?.conditions.some((row) => row.conditionId === channelValue(draft, "condition_id")) ? <option value={channelValue(draft, "condition_id")}>Saved {channelValue(draft, "condition_id")} (not validated)</option> : null}
      </select>}
      <FieldSource context={context} field="condition_id" />
    </label>
    <label className="label listing-field-anchor" id={listingFieldId(draft.id, "listing_duration")}><span>Duration</span>
      <select aria-label="Duration" className="field" value={channelValue(draft, "listing_duration") || (draft.listing_format === "fixed" ? context?.effective_duration : "") || ""} onChange={(event) => update({ listing_duration: event.target.value })}>
        <option value="">Choose duration</option>
        {(category?.listing_types?.formats[draft.listing_format === "fixed" ? "FIXED_PRICE_ITEM" : "AUCTION"] ?? []).map((value) => <option key={value} value={value}>{value === "GTC" ? "Good 'Til Cancelled" : value.replace("DAYS_", "") + " days"}</option>)}
        {channelValue(draft, "listing_duration") && !(category?.listing_types?.formats[draft.listing_format === "fixed" ? "FIXED_PRICE_ITEM" : "AUCTION"] ?? []).includes(channelValue(draft, "listing_duration")) ? <option value={channelValue(draft, "listing_duration")}>Saved {channelValue(draft, "listing_duration")} (refresh to validate)</option> : null}
        {!channelValue(draft, "listing_duration") && draft.listing_format === "fixed" && context?.effective_duration && !(category?.listing_types?.formats.FIXED_PRICE_ITEM ?? []).includes(context.effective_duration) ? <option value={context.effective_duration}>{context.effective_duration} (saved staged duration; refresh to validate)</option> : null}
      </select><small className="listing-source">Source: {channelValue(draft, "listing_duration") ? context?.sources.listing_duration || "Saved draft" : context?.duration_source || "Not set"}</small>
    </label>
    <div className="grid gap-4">
      {(["payment", "fulfillment", "return"] as const).map((kind) => {
        const options = metadata?.policies[kind] ?? [];
        const key = `${kind}_policy_id`;
        const chosen = options.find((row) => row.id === channelValue(draft, key));
        return <div key={kind} id={listingFieldId(draft.id, key)} className="listing-field-anchor">
          <label className="label"><span>{kind === "fulfillment" ? "Postage" : kind === "return" ? "Return" : "Payment"} policy</span>
            <select className="field" value={channelValue(draft, key)} onChange={(event) => update({ [key]: event.target.value })}>
              <option value="">Choose policy</option>
              {options.map((row) => <option key={row.id} value={row.id}>{row.name}{row.headline ? ` - ${row.headline}` : ""}</option>)}
              {channelValue(draft, key) && !chosen ? <option value={channelValue(draft, key)}>Saved {channelValue(draft, key)} (not in snapshot)</option> : null}
            </select>
          </label>
          {chosen ? <ul className="listing-policy-terms" aria-label={`${kind} policy terms`}>{chosen.terms.map((term, index) => <li key={index}>{term}</li>)}</ul> : null}
          <FieldSource context={context} field={key} />
        </div>;
      })}
    </div>
    <label className="label listing-field-anchor" id={listingFieldId(draft.id, "merchant_location_key")}><span>Merchant location</span>
      <select aria-label="Merchant location" className="field" value={channelValue(draft, "merchant_location_key")} onChange={(event) => update({ merchant_location_key: event.target.value })}>
        <option value="">Choose merchant location</option>
        {(metadata?.locations ?? []).map((row) => <option key={row.id} value={row.id} disabled={!row.verified}>{row.name} · {row.id} · {row.address}{row.verified ? "" : " (not verified)"}</option>)}
        {channelValue(draft, "merchant_location_key") && !metadata?.locations.some((row) => row.id === channelValue(draft, "merchant_location_key")) ? <option value={channelValue(draft, "merchant_location_key")}>Saved {channelValue(draft, "merchant_location_key")} (not verified)</option> : null}
      </select><FieldSource context={context} field="merchant_location_key" />
    </label>
  </div>;
}

export function EditorReadiness({ draft, context }: { draft: ListingDraft; context?: ListingEditorContext }) {
  const checks = context?.checks ?? [];
  const jump = (field: string) => {
    const target = document.getElementById(listingFieldId(draft.id, field));
    target?.scrollIntoView?.({ block: "center", behavior: "auto" });
    ((target?.matches("input,select,textarea") ? target : target?.querySelector("input,select,textarea,button")) as HTMLElement | null)?.focus();
  };
  return <section className="listing-readiness" aria-label="Listing readiness"><h3 className="section-title">Listing readiness</h3>
    {!context ? <p>Loading saved metadata and checks…</p> : null}
    <p>{checks.filter((row) => row.level === "fail").length} blockers · {checks.filter((row) => row.level === "warn").length} recommendations</p>
    <ul>{checks.filter((row) => row.level !== "pass").map((row) => <li key={row.key} className="flex flex-wrap items-center justify-between gap-2 border-b py-2">
      <span>{row.level === "fail" ? "Required: " : "Recommended: "}{row.message}</span>
      <button type="button" className="btn-secondary" onClick={() => jump(row.field)}>Go to field</button>
    </li>)}</ul>
    <details className="mt-3"><summary>Passed checks ({checks.filter((row) => row.level === "pass").length})</summary><ul>{checks.filter((row) => row.level === "pass").map((row) => <li key={row.key}>{row.message}</li>)}</ul></details>
  </section>;
}
