import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  Copy,
  Download,
  Eye,
  Pencil,
  Plus,
  RefreshCw,
  Archive,
  Trash2
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  createItemListingDraft,
  archiveListingDraft,
  downloadListingZip,
  generateListingDraft,
  getListingDraft,
  getListingEditor,
  listItemListingDrafts,
  listListingBoilerplates,
} from "../api/listing";
import type {
  InventoryItemDetail,
  ListingBoilerplate,
  ListingDraft,
  ListingSpecific,
  PhotoAsset,
  UUID
} from "../types";
import { ConfirmDialog } from "./ConfirmDialog";
import { EmptyState } from "./EmptyState";
import { PublishPanel } from "./PublishPanel";
import { EditorReadiness, FieldSource, ListingMetadataFields, listingFieldId } from "./ListingMetadataFields";
import { useDraftAutosave } from "./useDraftAutosave";
import { ListingSpecifics } from "./ListingSpecifics";
import { ListingSaveBar } from "./ListingSaveBar";

const titleMax = 80;

export function ListingPanel({ item }: { item: InventoryItemDetail }) {
  const queryClient = useQueryClient();
  const drafts = useQuery({ queryKey: ["listing-drafts", item.id], queryFn: () => listItemListingDrafts(item.id) });
  const boilerplates = useQuery({ queryKey: ["listing-boilerplates"], queryFn: listListingBoilerplates });
  const [selectedId, setSelectedId] = useState<UUID | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ListingDraft | null>(null);

  const draftList = drafts.data?.results ?? [];
  const selectedDraft = draftList.find((draft) => draft.id === selectedId) ?? draftList[0] ?? null;

  useEffect(() => {
    if (!selectedId && draftList.length > 0) {
      setSelectedId(draftList[0].id);
    }
  }, [draftList, selectedId]);

  useEffect(() => {
    const open = () => {
      setSelectedId(draftList[0]?.id ?? null);
      document.getElementById(`listing-editor-${item.id}`)?.scrollIntoView?.({ block: "start" });
    };
    window.addEventListener(`magpie:open-draft:${item.id}`, open);
    return () => window.removeEventListener(`magpie:open-draft:${item.id}`, open);
  }, [draftList, item.id]);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["listing-drafts", item.id] });
    queryClient.invalidateQueries({ queryKey: ["item-listing-drafts", item.id] });
    queryClient.invalidateQueries({ queryKey: ["item", item.id] });
    if (selectedDraft) {
      queryClient.invalidateQueries({ queryKey: ["listing-readiness", selectedDraft.id] });
    }
  };

  const createMutation = useMutation({
    mutationFn: () => createItemListingDraft(item.id),
    onSuccess: (draft) => {
      setSelectedId(draft.id);
      refresh();
    }
  });
  const deleteMutation = useMutation({
    mutationFn: (draft: ListingDraft) => archiveListingDraft(draft.id),
    onSuccess: () => {
      setSelectedId(null);
      setDeleteTarget(null);
      refresh();
    }
  });

  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="section-title">Listing</h2>
          <p className="mt-1 text-xs text-slate-500">{draftList.length} draft{draftList.length === 1 ? "" : "s"}</p>
        </div>
        <button className="btn-primary gap-2" disabled={createMutation.isPending} onClick={() => createMutation.mutate()} type="button">
          <Plus className="h-4 w-4" aria-hidden="true" />
          {draftList.some((row) => !["published", "archived"].includes(row.status)) ? "Open listing draft" : "Create draft"}
        </button>
      </div>

      {drafts.isLoading ? <EmptyState title="Loading listing drafts" /> : null}
      {!drafts.isLoading && draftList.length === 0 ? <EmptyState title="No listing drafts" /> : null}

      {draftList.length > 0 ? (
        <div className="mt-4 grid gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
          <div className="space-y-2">
            {draftList.map((draft) => (
              <button
                className={`w-full rounded border px-3 py-2 text-left text-sm transition ${selectedDraft?.id === draft.id ? "border-cyan-400/60 bg-cyan-400/10 text-cyan-100" : "border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-600"}`}
                key={draft.id}
                onClick={() => setSelectedId(draft.id)}
                type="button"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate font-semibold">{draft.title || "Untitled draft"}</span>
                  <StatusPill status={draft.status} />
                </span>
                <span className="mt-1 block text-xs text-slate-500">{draft.currency} {draft.price ?? "-"}</span>
              </button>
            ))}
          </div>

          {selectedDraft ? (
            <DraftEditor
              key={selectedDraft.id}
              boilerplates={boilerplates.data?.results ?? []}
              draft={selectedDraft}
              item={item}
              onDelete={() => setDeleteTarget(selectedDraft)}
              onSaved={refresh}
            />
          ) : null}
        </div>
      ) : null}

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Archive listing draft?"
        detail="The draft and its history are retained read-only. A staged offer must be withdrawn first."
        confirmLabel="Archive"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            deleteMutation.mutate(deleteTarget);
          }
        }}
      />
      {deleteMutation.error ? <p role="alert">{deleteMutation.error instanceof Error ? deleteMutation.error.message : "Archive failed. Reload and retry."}</p> : null}
    </section>
  );
}

interface DraftEditorProps {
  boilerplates: ListingBoilerplate[];
  draft: ListingDraft;
  item: InventoryItemDetail;
  onDelete: () => void;
  onSaved: () => void;
}

function DraftEditor({ boilerplates, draft, item, onDelete, onSaved }: DraftEditorProps) {
  const queryClient = useQueryClient();
  const readOnly = ["published", "archived", "publishing", "publish_unknown"].includes(draft.status) || Boolean(draft.channel_data.listing_id);
  const autosave = useDraftAutosave(draft, onSaved, readOnly);
  const { local, setLocal } = autosave;
  const [preview, setPreview] = useState(false);
  const [pendingGenerate, setPendingGenerate] = useState<"title" | "description" | null>(null);

  const editor = useQuery({
    queryKey: ["listing-editor", draft.id, String(local.channel_data.category_id ?? ""), local.updated_at],
    queryFn: () => getListingEditor(draft.id, String(local.channel_data.category_id ?? "")),
    // Refresh provenance after saves without unmounting the field being edited.
    placeholderData: (previous, query) => query?.queryKey[2] === String(local.channel_data.category_id ?? "") ? previous : undefined
  });

  const selectedBoilerplate = boilerplates.find((entry) => entry.id === local.boilerplate) ?? null;
  const titleDirty = local.title !== draft.title || draft.title_edited;
  const descriptionDirty = local.description_html !== draft.description_html || draft.description_edited;

  const saveMutation = useMutation({
    mutationFn: persistLocal,
    onSuccess: (updated) => {
      autosave.acceptExternal(updated);
      onSaved();
    }
  });
  const generateMutation = useMutation({
    mutationFn: async ({ field, confirm }: { field: "title" | "description" | "specifics"; confirm: boolean }) => {
      await autosave.flush();
      return generateListingDraft(local.id, [field], confirm);
    },
    onSuccess: (updated) => {
      autosave.acceptExternal(updated);
      setPendingGenerate(null);
      onSaved();
    }
  });

  function persistLocal() {
    return autosave.flush();
  }

  function requestGenerate(field: "title" | "description" | "specifics") {
    if (field === "title" && titleDirty) {
      setPendingGenerate("title");
      return;
    }
    if (field === "description" && descriptionDirty) {
      setPendingGenerate("description");
      return;
    }
    generateMutation.mutate({ field, confirm: false });
  }

  return (
    <div className="listing-editor min-w-0 space-y-5" id={`listing-editor-${item.id}`}>
      {readOnly ? <p className="font-semibold">Read-only history</p> : null}
      {editor.error ? <p role="alert">Saved metadata could not load. Check your session and retry. Your draft is not staged or published by saving.</p> : null}
      {local.channel_data.offer_id ? <div className="listing-staged-notice" role="status"><strong>Unpublished staged offer {String(local.channel_data.offer_id)}</strong><p>{editor.data?.staged_local_changes || autosave.state !== "Saved locally" ? "Local changes are not yet on eBay. Nothing is re-staged by this editor." : "Saved staging snapshot. Editing here stays local; nothing is re-staged automatically."}</p></div> : null}
      <fieldset disabled={readOnly} className="min-w-0 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill status={local.status} />
          {local.readiness_summary.fail_count > 0 ? <span className="rounded border border-rose-400/40 bg-rose-500/10 px-2 py-1 text-xs font-semibold text-rose-100">Unready</span> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary gap-2" disabled={Boolean(local.channel_data.offer_id)} title={local.channel_data.offer_id ? "Withdraw the staged offer before archiving (Phase 5)" : "Archive draft"} onClick={() => { void persistLocal().then(onDelete).catch(() => undefined); }} type="button">
            <Archive className="h-4 w-4" aria-hidden="true" />
            Archive
          </button>
        </div>
      </div>

      <div className="grid gap-3">
        <label className="label">
          <span className="flex items-center justify-between gap-3">
            <span>Title</span>
            <span className={Array.from(local.title).length > titleMax ? "text-rose-300" : "text-slate-500"}>{Array.from(local.title).length}/{titleMax}</span>
          </span>
          <input aria-label="Title" id={listingFieldId(local.id, "title")} className={Array.from(local.title).length > titleMax ? "field border-rose-400 focus:border-rose-300 focus:ring-rose-300/20" : "field"} value={local.title} onChange={(event) => setLocal({ ...local, title: event.target.value })} />
          <FieldSource context={editor.data} field="title" />
        </label>
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary gap-2" disabled={generateMutation.isPending} onClick={() => requestGenerate("title")} type="button">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Regenerate title
          </button>
          <button className="btn-secondary gap-2" disabled={generateMutation.isPending} onClick={() => requestGenerate("description")} type="button">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Regenerate description
          </button>
          <button className="btn-secondary gap-2" disabled={generateMutation.isPending} onClick={() => requestGenerate("specifics")} type="button">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Regenerate specifics
          </button>
        </div>
      </div>

      <label className="label">
        <span>Subtitle</span>
        <input aria-label="Subtitle" className="field" value={local.subtitle} onChange={(event) => setLocal({ ...local, subtitle: event.target.value })} />
        <FieldSource context={editor.data} field="subtitle" />
      </label>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="label">
          <span>Format</span>
          <select aria-label="Format" className="field" value={local.listing_format} onChange={(event) => setLocal({ ...local, listing_format: event.target.value as ListingDraft["listing_format"], channel_data: { ...local.channel_data, listing_duration: "" } })}>
            <option value="fixed">Fixed price</option>
            <option value="auction">Auction</option>
          </select>
          <FieldSource context={editor.data} field="listing_format" />
        </label>
        <label className="label">
          <span>Price</span>
          <input aria-label="Price" id={listingFieldId(local.id, "price")} className="field" inputMode="decimal" value={local.price ?? ""} onChange={(event) => setLocal({ ...local, price: event.target.value || null }, { kind: "human_asking" })} />
          <small className="listing-source">Source: {autosave.pendingPriceChoice ? `${autosave.pendingPriceChoice.kind === "human_asking" ? "Human asking price" : "Human-picked owned evidence"} (pending save)` : ["human_asking", "owned_evidence"].includes(editor.data?.price_source?.kind || "") ? editor.data?.price_source?.label : "Unconfirmed saved price; confirm it or pick evidence"}</small>
        </label>
        <label className="label">
          <span>Currency</span>
          <input aria-label="Currency" className="field" maxLength={3} value={local.currency} onChange={(event) => setLocal({ ...local, currency: event.target.value.toUpperCase() })} />
          <FieldSource context={editor.data} field="currency" />
        </label>
        <label className="label">
          <span>Quantity</span>
          <input aria-label="Quantity" id={listingFieldId(local.id, "quantity")} className="field" inputMode="numeric" value={local.quantity} onChange={(event) => setLocal({ ...local, quantity: Number(event.target.value) || 0 })} />
          <FieldSource context={editor.data} field="quantity" />
        </label>
        <label className="flex items-end gap-2 text-sm font-medium text-slate-300">
          <input aria-label="SKU footer" checked={local.include_sku_footer} type="checkbox" onChange={(event) => setLocal({ ...local, include_sku_footer: event.target.checked })} />
          SKU footer
          <FieldSource context={editor.data} field="include_sku_footer" />
        </label>
      </div>
      <button className="btn-secondary" type="button" disabled={!local.price} onClick={() => setLocal({ ...local }, { kind: "human_asking" })}>Confirm saved price as my asking price</button>
      <label className="label"><span>Pick an evidence price (seller receives)</span><select className="field" value="" onChange={(event) => {
        const row = editor.data?.price_options.find((option) => option.id === event.target.value);
        if (row) setLocal({ ...local, price: row.value }, { kind: "owned_evidence", id: row.id });
      }}><option value="">Choose owned evidence or item asking price</option>{editor.data?.price_options.map((row) => <option value={row.id} key={row.id}>{local.currency} {row.value} | {row.label}</option>)}</select></label>

      <ListingMetadataFields draft={local} context={editor.data} onChange={setLocal} flush={persistLocal} onRefreshed={(updated) => { autosave.acceptExternal(updated); onSaved(); void editor.refetch(); }} />

      <label className="label">
        <span>Shipping note</span>
        <input aria-label="Shipping note" className="field" value={local.est_shipping_note} onChange={(event) => setLocal({ ...local, est_shipping_note: event.target.value })} />
        <FieldSource context={editor.data} field="est_shipping_note" />
      </label>

      <label className="label">
        <span>Boilerplate</span>
        <select aria-label="Boilerplate" className="field" value={local.boilerplate ?? ""} onChange={(event) => setLocal({ ...local, boilerplate: event.target.value || null })}>
          <option value="">None</option>
          {boilerplates.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}
        </select>
        <FieldSource context={editor.data} field="boilerplate" />
      </label>

      <div id={listingFieldId(local.id, "description_html")} className="listing-field-anchor">
        <div className="mb-2 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-slate-200">Description</h3>
          <button className="btn-secondary gap-2" onClick={() => setPreview(!preview)} type="button">
            {preview ? <Pencil className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
            {preview ? "Edit" : "Preview"}
          </button>
        </div>
        {preview ? (
          <div className="prose prose-invert max-w-none rounded border border-slate-800 bg-slate-900 p-3 text-sm" dangerouslySetInnerHTML={{ __html: local.description_html }} />
        ) : (
          <textarea aria-label="Description" className="field min-h-48 font-mono" value={local.description_html} onChange={(event) => setLocal({ ...local, description_html: event.target.value })} />
        )}
        <FieldSource context={editor.data} field="description_html" />
      </div>

      <div id={listingFieldId(local.id, "item_specifics")} className="listing-field-anchor">
        <ListingSpecifics aspects={editor.data?.metadata.category_snapshot?.aspects ?? []} rows={local.item_specifics} onChange={(item_specifics) => setLocal({ ...local, item_specifics })} customRows={<SpecificsEditor rows={local.item_specifics.filter((row) => !editor.data?.metadata.category_snapshot?.aspects?.some((aspect) => aspect.name.toLowerCase() === row.name.toLowerCase()))} onChange={(custom) => setLocal({ ...local, item_specifics: [...local.item_specifics.filter((row) => editor.data?.metadata.category_snapshot?.aspects?.some((aspect) => aspect.name.toLowerCase() === row.name.toLowerCase())), ...custom] })} />} />
        <FieldSource context={editor.data} field="item_specifics" />
      </div>
      <div id={listingFieldId(local.id, "photos")} className="listing-field-anchor"><PhotoPicker photos={item.photos} selected={local.photo_ids} onChange={(photo_ids) => setLocal({ ...local, photo_ids })} /><FieldSource context={editor.data} field="photo_ids" /></div>
      </fieldset>
      <EditorReadiness draft={local} context={editor.data} />
      <ExportButtons boilerplate={selectedBoilerplate} draft={local} beforeExport={persistLocal} onExported={() => {
        void getListingDraft(local.id).then((updated) => { autosave.acceptExternal(updated); onSaved(); });
      }} />
      <PublishPanel
        localEditor
        draft={local}
        item={item}
        onDraftChange={setLocal}
        onDraftUpdated={(updated) => {
          autosave.acceptExternal(updated);
          onSaved();
          queryClient.invalidateQueries({ queryKey: ["item", item.id] });
        }}
        persistDraft={persistLocal}
      />
      <ListingSaveBar state={readOnly ? "Read-only history" : autosave.state} disabled={saveMutation.isPending || readOnly} onSave={() => {
        if (!local.channel_data.listing_duration && editor.data?.effective_duration && local.listing_format === "fixed") {
          setLocal({ ...local, channel_data: { ...local.channel_data, listing_duration: editor.data.effective_duration } });
        }
        saveMutation.mutate();
      }} />

      <ConfirmDialog
        open={pendingGenerate !== null}
        title={`Overwrite edited ${pendingGenerate}?`}
        detail="Regenerate will replace the current edited text."
        confirmLabel="Overwrite"
        danger={false}
        onCancel={() => setPendingGenerate(null)}
        onConfirm={() => {
          if (pendingGenerate) {
            generateMutation.mutate({ field: pendingGenerate, confirm: true });
          }
        }}
      />
    </div>
  );
}

function SpecificsEditor({ rows, onChange }: { rows: ListingSpecific[]; onChange: (rows: ListingSpecific[]) => void }) {
  function update(index: number, patch: Partial<ListingSpecific>) {
    onChange(rows.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row));
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-200">Item specifics</h3>
        <button className="btn-secondary gap-2" onClick={() => onChange([...rows, { name: "", value: "" }])} type="button">
          <Plus className="h-4 w-4" aria-hidden="true" />
          Add row
        </button>
      </div>
      <div className="space-y-2">
        {rows.map((row, index) => (
          <div className="grid gap-2 sm:grid-cols-[minmax(0,0.5fr)_minmax(0,1fr)_auto]" key={index}>
            <input aria-label={`Specific name ${index + 1}`} className="field" value={row.name} onChange={(event) => update(index, { name: event.target.value })} />
            <input aria-label={`Specific value ${index + 1}`} className="field" value={row.value} onChange={(event) => update(index, { value: event.target.value })} />
            <button className="icon-button-danger" onClick={() => onChange(rows.filter((_, rowIndex) => rowIndex !== index))} title="Remove row" type="button">
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function PhotoPicker({ photos, selected, onChange }: { photos: PhotoAsset[]; selected: UUID[]; onChange: (ids: UUID[]) => void }) {
  const orderedPhotos = useMemo(() => [...photos].sort((a, b) => {
    const ai = selected.indexOf(a.id), bi = selected.indexOf(b.id);
    return (ai < 0 ? selected.length + a.order_index : ai) - (bi < 0 ? selected.length + b.order_index : bi);
  }), [photos, selected]);

  function toggle(photo: PhotoAsset, checked: boolean) {
    if (checked) {
      onChange([...selected, photo.id]);
      return;
    }
    onChange(selected.filter((id) => id !== photo.id));
  }

  function move(id: UUID, direction: -1 | 1) {
    const index = selected.indexOf(id);
    const nextIndex = index + direction;
    if (index < 0 || nextIndex < 0 || nextIndex >= selected.length) {
      return;
    }
    const next = [...selected];
    const [removed] = next.splice(index, 1);
    next.splice(nextIndex, 0, removed);
    onChange(next);
  }

  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-slate-200">Photos</h3>
      <div className="grid gap-2 sm:grid-cols-2">
        {orderedPhotos.map((photo) => {
          const isSelected = selected.includes(photo.id);
          return (
            <div className="listing-photo-row" key={photo.id}>
              <label className="flex h-11 w-11 shrink-0 items-center justify-center"><input checked={isSelected} type="checkbox" onChange={(event) => toggle(photo, event.target.checked)} aria-label={`Select photo ${photo.id}`} /></label>
              {photo.thumb_url ? <img alt={`${photo.role || "Item"} photo`} className="listing-photo-thumb" src={photo.thumb_url} /> : <div className="listing-photo-thumb bg-slate-100" />}
              <div className="min-w-0 flex-1 text-xs text-slate-400">
                <p className="font-semibold">{isSelected ? `Photo ${selected.indexOf(photo.id) + 1}` : "Not selected"}</p><p>{photo.role}</p>
              </div>
              {isSelected ? (
                <div className="flex gap-1">
                  <button className="icon-button" disabled={selected.indexOf(photo.id) === 0} onClick={() => move(photo.id, -1)} title="Move up" type="button">
                    <ArrowUp className="h-4 w-4" aria-hidden="true" />
                  </button>
                  <button className="icon-button" disabled={selected.indexOf(photo.id) === selected.length - 1} onClick={() => move(photo.id, 1)} title="Move down" type="button">
                    <ArrowDown className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ExportButtons({ boilerplate, draft, onExported, beforeExport }: { boilerplate: ListingBoilerplate | null; draft: ListingDraft; onExported: () => void; beforeExport: () => Promise<ListingDraft> }) {
  const downloadMutation = useMutation({
    mutationFn: async () => { await beforeExport(); return downloadListingZip(draft.id); },
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `listing-${draft.id}.zip`;
      link.click();
      URL.revokeObjectURL(url);
      onExported();
    }
  });
  const unready = draft.readiness_summary.fail_count > 0;

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-200">Export</h3>
        {unready ? <span className="rounded border border-rose-400/40 bg-rose-500/10 px-2 py-1 text-xs font-semibold text-rose-100">Unready export</span> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        <CopyButton label="Copy title" text={draft.title} />
        <CopyButton label="Copy description" text={draft.description_html} />
        <CopyButton label="Copy specifics" text={draft.item_specifics.map((row) => `${row.name}\t${row.value}`).join("\n")} />
        <CopyButton label="Copy boilerplate" text={boilerplate?.body_html ?? ""} />
        <button className="btn-primary gap-2" disabled={downloadMutation.isPending} onClick={() => downloadMutation.mutate()} type="button">
          <Download className="h-4 w-4" aria-hidden="true" />
          Download zip
        </button>
      </div>
    </div>
  );
}

function CopyButton({ label, text }: { label: string; text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="btn-secondary gap-2"
      onClick={async () => {
        await navigator.clipboard?.writeText(text);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1000);
      }}
      type="button"
    >
      <Copy className="h-4 w-4" aria-hidden="true" />
      {copied ? "Copied" : label}
    </button>
  );
}

function StatusPill({ status }: { status: ListingDraft["status"] }) {
  const classes = status === "ready" || status === "staged"
    ? "border-cyan-300/40 bg-cyan-300/10 text-cyan-100"
    : status === "exported" || status === "published"
      ? "border-emerald-300/40 bg-emerald-300/10 text-emerald-100"
      : status === "publish_failed"
        ? "border-rose-400/40 bg-rose-500/10 text-rose-100"
        : "border-slate-600 bg-slate-800 text-slate-200";
  return <span className={`rounded border px-2 py-0.5 text-xs font-semibold ${classes}`}>{status}</span>;
}
