import { plainDate } from "./itemDisplay";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, RotateCcw, Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import { browseListingDefaultsCategory, defaultValues, defaultsForm, getListingDefaults, listListingDefaults, previewListingDefaults, refreshListingDefaultsMetadata, saveListingDefaults, type ListingDefaultValues, type ListingDefaults, type DefaultsPreview } from "../api/listingDefaults";
import type { ListingDraft } from "../types";
import { ListingMetadataFields } from "./ListingMetadataFields";

export function SaveListingDefaults({ categoryId, categoryName, values, onSaved, label, reset = false }: {
  categoryId: string; categoryName: string; values: ListingDefaultValues; onSaved?: (result: ListingDefaults) => void; label?: string; reset?: boolean;
}) {
  const client = useQueryClient();
  const [preview, setPreview] = useState<DefaultsPreview | null>(null);
  const [saved, setSaved] = useState(false);
  const inspect = useMutation({ mutationFn: () => previewListingDefaults(categoryId, values), onSuccess: (result) => { setPreview(result); setSaved(false); } });
  const save = useMutation({ mutationFn: () => { if (!preview) throw new Error("Review the defaults first."); return saveListingDefaults(categoryId, preview); },
    onSuccess: (result) => { setPreview(null); setSaved(true); onSaved?.(result); void client.invalidateQueries({ queryKey: ["listing-defaults"] }); } });
  return <div className="listing-default-save space-y-3">
    <button type="button" className="btn-secondary gap-2" disabled={inspect.isPending || save.isPending} onClick={() => inspect.mutate()}>{reset ? <RotateCcw size={18} /> : <Save size={18} />}{label ?? `Save these as ${categoryName} defaults`}</button>
    {saved ? <p role="status">{categoryName} defaults saved. Existing drafts are unchanged.</p> : null}
    {inspect.error || save.error ? <p role="alert">{String((inspect.error ?? save.error) instanceof Error ? (inspect.error ?? save.error)?.message : "Defaults could not save; preview again and retry.")}</p> : null}
    {preview ? <section aria-label={`${categoryName} defaults change preview`} className="listing-readiness space-y-3">
      <h3 className="section-title">Review {categoryName} defaults changes</h3>
      {preview.changes.length ? <ul className="divide-y">{preview.changes.map((row) => <li key={row.field} className="py-3 break-words"><strong>{row.label}</strong><p>{row.before || "[not set]"} → {row.after || "[empty]"}</p>{row.clears ? <strong className="text-red-800">Clears existing default</strong> : null}</li>)}</ul> : <p>No changes.</p>}
      <p>New drafts only. No price, quantity or item specifics are saved as defaults.</p>
      <div className="flex flex-wrap gap-2"><button type="button" className="btn-primary gap-2" disabled={save.isPending || !preview.changes.length} onClick={() => save.mutate()}><Check size={18} />Confirm defaults changes</button><button type="button" className="btn-secondary gap-2" disabled={save.isPending} onClick={() => setPreview(null)}><X size={18} />Cancel</button></div>
    </section> : null}
  </div>;
}

export function ListingDefaultsPanel() {
  const rows = useQuery({ queryKey: ["listing-defaults"], queryFn: listListingDefaults });
  const [selected, setSelected] = useState("");
  return <section className="listing-defaults-panel rounded border p-4 space-y-4" aria-label="Listing defaults">
    <h2 className="section-title">Listing defaults</h2>
    <p>Human-chosen settings for new eBay drafts, by Magpie category. Existing drafts never change.</p>
    {rows.isLoading ? <p>Loading category defaults...</p> : null}
    {rows.error ? <p role="alert">Listing defaults could not load. Check your session and retry.</p> : null}
    {(rows.data?.categories ?? []).map((row) => <div key={row.id} className="border-t pt-3 min-w-0">
      <button className="btn-secondary w-full justify-between" type="button" aria-expanded={selected === row.id} onClick={() => setSelected(selected === row.id ? "" : row.id)}><span>{row.name} · {row.configured ? "Set" : "Not set"}</span><ChevronDown size={18} /></button>
      {selected === row.id ? <DefaultsEditor categoryId={row.id} categoryName={row.name} /> : null}
    </div>)}
  </section>;
}

function DefaultsEditor({ categoryId, categoryName }: { categoryId: string; categoryName: string }) {
  const [form, setForm] = useState<ListingDraft | null>(null);
  const [snapshot, setSnapshot] = useState<ListingDefaults | null>(null);
  const query = useQuery({ queryKey: ["listing-defaults", categoryId, String(form?.channel_data.category_id ?? "")], queryFn: () => getListingDefaults(categoryId, form ? String(form.channel_data.category_id ?? "") : undefined) });
  useEffect(() => { if (query.data) { setSnapshot(query.data); setForm((previous) => previous ?? defaultsForm(categoryId, query.data.values)); } }, [query.data, categoryId]);
  if (!form || !snapshot) return <p>{query.error ? "Defaults could not load. Retry after signing in." : "Loading saved defaults..."}</p>;
  const accepted = (result: ListingDefaults) => { setForm(defaultsForm(categoryId, result.values)); setSnapshot(result); };
  return <div className="py-4 space-y-5 min-w-0">
    <label className="label"><span>Format</span><select className="field" aria-label="Default format" value={form.listing_format} onChange={(event) => setForm({ ...form, listing_format: event.target.value as ListingDraft["listing_format"], channel_data: { ...form.channel_data, listing_duration: "" } })}><option value="">No format default</option><option value="fixed">Fixed price</option><option value="auction">Auction</option></select></label>
    <ListingMetadataFields draft={form} context={snapshot.editor} onChange={setForm} flush={async () => form} onRefreshed={() => undefined} metadataPort={{
      refresh: async (options) => { const result = await refreshListingDefaultsMetadata(categoryId, options); setSnapshot(result); return result.editor; },
      browse: (id) => browseListingDefaultsCategory(categoryId, id)
    }} />
    {snapshot.validation.map((row) => <p key={row.field} className="listing-source">{row.message} Saved choices updated: {row.fetched_at ? plainDate(row.fetched_at, true) : "unavailable"}.</p>)}
    <SaveListingDefaults categoryId={categoryId} categoryName={categoryName} values={defaultValues(form)} onSaved={accepted} label="Review and save defaults" />
    <SaveListingDefaults categoryId={categoryId} categoryName={categoryName} values={{}} onSaved={accepted} label={`Clear ${categoryName} defaults`} reset />
  </div>;
}
