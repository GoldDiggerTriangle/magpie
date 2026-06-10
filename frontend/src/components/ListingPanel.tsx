import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Copy,
  Download,
  Eye,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Trash2
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  createItemListingDraft,
  deleteListingDraft,
  downloadListingZip,
  generateListingDraft,
  getListingReadiness,
  listItemListingDrafts,
  listListingBoilerplates,
  updateListingDraft
} from "../api/listing";
import { updateItem } from "../api/items";
import type {
  InventoryItemDetail,
  ListingBoilerplate,
  ListingCheck,
  ListingDraft,
  ListingSpecific,
  PhotoAsset,
  UUID
} from "../types";
import { ConfirmDialog } from "./ConfirmDialog";
import { EmptyState } from "./EmptyState";

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

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["listing-drafts", item.id] });
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
    mutationFn: (draft: ListingDraft) => deleteListingDraft(draft.id),
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
          Create draft
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
        title="Delete listing draft?"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            deleteMutation.mutate(deleteTarget);
          }
        }}
      />
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
  const [local, setLocal] = useState(draft);
  const [preview, setPreview] = useState(false);
  const [pendingGenerate, setPendingGenerate] = useState<"title" | "description" | null>(null);
  const [markListedOpen, setMarkListedOpen] = useState(false);

  useEffect(() => setLocal(draft), [draft]);

  const selectedBoilerplate = boilerplates.find((entry) => entry.id === local.boilerplate) ?? null;
  const titleDirty = local.title !== draft.title || draft.title_edited;
  const descriptionDirty = local.description_html !== draft.description_html || draft.description_edited;

  const saveMutation = useMutation({
    mutationFn: () => updateListingDraft(local.id, toPayload(local)),
    onSuccess: (updated) => {
      setLocal(updated);
      onSaved();
    }
  });
  const generateMutation = useMutation({
    mutationFn: ({ field, confirm }: { field: "title" | "description" | "specifics" | "price"; confirm: boolean }) => generateListingDraft(local.id, [field], confirm),
    onSuccess: (updated) => {
      setLocal(updated);
      setPendingGenerate(null);
      onSaved();
    }
  });
  const markListedMutation = useMutation({
    mutationFn: () => updateItem(item.id, { status: "listed" }),
    onSuccess: () => {
      setMarkListedOpen(false);
      queryClient.invalidateQueries({ queryKey: ["item", item.id] });
    }
  });

  function requestGenerate(field: "title" | "description" | "specifics" | "price") {
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
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill status={local.status} />
          {local.readiness_summary.fail_count > 0 ? <span className="rounded border border-rose-400/40 bg-rose-500/10 px-2 py-1 text-xs font-semibold text-rose-100">Unready</span> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary gap-2" disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()} type="button">
            <Save className="h-4 w-4" aria-hidden="true" />
            Save
          </button>
          <button className="btn-secondary gap-2" onClick={onDelete} type="button">
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            Delete
          </button>
        </div>
      </div>

      <div className="grid gap-3">
        <label className="label">
          <span className="flex items-center justify-between gap-3">
            <span>Title</span>
            <span className={local.title.length > titleMax ? "text-rose-300" : "text-slate-500"}>{local.title.length}/{titleMax}</span>
          </span>
          <input className={local.title.length > titleMax ? "field border-rose-400 focus:border-rose-300 focus:ring-rose-300/20" : "field"} value={local.title} onChange={(event) => setLocal({ ...local, title: event.target.value })} />
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
          <button className="btn-secondary gap-2" disabled={generateMutation.isPending} onClick={() => requestGenerate("price")} type="button">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Regenerate price
          </button>
        </div>
      </div>

      <label className="label">
        <span>Subtitle</span>
        <input className="field" value={local.subtitle} onChange={(event) => setLocal({ ...local, subtitle: event.target.value })} />
      </label>

      <div className="grid gap-3 sm:grid-cols-5">
        <label className="label">
          <span>Format</span>
          <select className="field" value={local.listing_format} onChange={(event) => setLocal({ ...local, listing_format: event.target.value as ListingDraft["listing_format"] })}>
            <option value="fixed">Fixed price</option>
            <option value="auction">Auction</option>
          </select>
        </label>
        <label className="label">
          <span>Price</span>
          <input className="field" inputMode="decimal" value={local.price ?? ""} onChange={(event) => setLocal({ ...local, price: event.target.value || null })} />
        </label>
        <label className="label">
          <span>Currency</span>
          <input className="field" maxLength={3} value={local.currency} onChange={(event) => setLocal({ ...local, currency: event.target.value.toUpperCase() })} />
        </label>
        <label className="label">
          <span>Quantity</span>
          <input className="field" inputMode="numeric" value={local.quantity} onChange={(event) => setLocal({ ...local, quantity: Number(event.target.value) || 0 })} />
        </label>
        <label className="flex items-end gap-2 text-sm font-medium text-slate-300">
          <input checked={local.include_sku_footer} type="checkbox" onChange={(event) => setLocal({ ...local, include_sku_footer: event.target.checked })} />
          SKU footer
        </label>
      </div>

      <label className="label">
        <span>Shipping note</span>
        <input className="field" value={local.est_shipping_note} onChange={(event) => setLocal({ ...local, est_shipping_note: event.target.value })} />
      </label>

      <label className="label">
        <span>Boilerplate</span>
        <select className="field" value={local.boilerplate ?? ""} onChange={(event) => setLocal({ ...local, boilerplate: event.target.value || null })}>
          <option value="">None</option>
          {boilerplates.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}
        </select>
      </label>

      <div>
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
          <textarea className="field min-h-48 font-mono" value={local.description_html} onChange={(event) => setLocal({ ...local, description_html: event.target.value })} />
        )}
      </div>

      <SpecificsEditor rows={local.item_specifics} onChange={(item_specifics) => setLocal({ ...local, item_specifics })} />
      <PhotoPicker photos={item.photos} selected={local.photo_ids} onChange={(photo_ids) => setLocal({ ...local, photo_ids })} />
      <ReadinessChecklist draft={local} />
      <ExportButtons boilerplate={selectedBoilerplate} draft={local} onExported={onSaved} />

      <button className="btn-primary w-fit gap-2" disabled={local.status !== "exported"} onClick={() => setMarkListedOpen(true)} type="button">
        <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
        Mark item listed
      </button>

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
      <ConfirmDialog
        open={markListedOpen}
        title="Mark item listed?"
        detail="This updates the item status through the existing item save path."
        confirmLabel="Mark listed"
        danger={false}
        onCancel={() => setMarkListedOpen(false)}
        onConfirm={() => markListedMutation.mutate()}
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
  const orderedPhotos = useMemo(() => [...photos].sort((a, b) => a.order_index - b.order_index), [photos]);

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
            <div className="flex items-center gap-3 rounded border border-slate-800 bg-slate-900 p-2" key={photo.id}>
              <input checked={isSelected} type="checkbox" onChange={(event) => toggle(photo, event.target.checked)} aria-label={`Select photo ${photo.id}`} />
              {photo.thumb_url ? <img alt="" className="h-12 w-12 rounded object-cover" src={photo.thumb_url} /> : <div className="h-12 w-12 rounded bg-slate-800" />}
              <div className="min-w-0 flex-1 text-xs text-slate-400">
                <p className="truncate">{photo.role}</p>
                <p className="truncate">{photo.processed_path || "No processed image"}</p>
              </div>
              {isSelected ? (
                <div className="flex gap-1">
                  <button className="icon-button" onClick={() => move(photo.id, -1)} title="Move up" type="button">
                    <ArrowUp className="h-4 w-4" aria-hidden="true" />
                  </button>
                  <button className="icon-button" onClick={() => move(photo.id, 1)} title="Move down" type="button">
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

function ReadinessChecklist({ draft }: { draft: ListingDraft }) {
  const readiness = useQuery({ queryKey: ["listing-readiness", draft.id], queryFn: () => getListingReadiness(draft.id) });
  const checks = readiness.data ?? [];
  const groups = groupChecks(checks);

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-200">Readiness</h3>
        <button className="btn-secondary gap-2" onClick={() => readiness.refetch()} type="button">
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Refresh
        </button>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <CheckGroup title="Fails" checks={groups.fail} tone="rose" />
        <CheckGroup title="Warnings" checks={groups.warn} tone="amber" />
        <CheckGroup title="Passes" checks={groups.pass} tone="cyan" />
      </div>
    </div>
  );
}

function CheckGroup({ title, checks, tone }: { title: string; checks: ListingCheck[]; tone: "rose" | "amber" | "cyan" }) {
  const toneClass = tone === "rose" ? "text-rose-100 border-rose-400/30 bg-rose-500/10" : tone === "amber" ? "text-amber-100 border-amber-300/30 bg-amber-300/10" : "text-cyan-100 border-cyan-300/30 bg-cyan-300/10";
  return (
    <div className={`rounded border p-3 ${toneClass}`}>
      <p className="text-sm font-semibold">{title} ({checks.length})</p>
      <ul className="mt-2 space-y-1 text-xs">
        {checks.length === 0 ? <li>None</li> : checks.map((check) => <li key={check.key}>{check.message}</li>)}
      </ul>
    </div>
  );
}

function ExportButtons({ boilerplate, draft, onExported }: { boilerplate: ListingBoilerplate | null; draft: ListingDraft; onExported: () => void }) {
  const downloadMutation = useMutation({
    mutationFn: () => downloadListingZip(draft.id),
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
  const classes = status === "ready" ? "border-cyan-300/40 bg-cyan-300/10 text-cyan-100" : status === "exported" ? "border-emerald-300/40 bg-emerald-300/10 text-emerald-100" : "border-slate-600 bg-slate-800 text-slate-200";
  return <span className={`rounded border px-2 py-0.5 text-xs font-semibold ${classes}`}>{status}</span>;
}

function groupChecks(checks: ListingCheck[]) {
  return {
    fail: checks.filter((check) => check.level === "fail"),
    warn: checks.filter((check) => check.level === "warn"),
    pass: checks.filter((check) => check.level === "pass")
  };
}

function toPayload(draft: ListingDraft) {
  return {
    status: draft.status,
    channel: draft.channel,
    channel_data: draft.channel_data,
    title: draft.title,
    subtitle: draft.subtitle,
    description_html: draft.description_html,
    listing_format: draft.listing_format,
    price: draft.price,
    currency: draft.currency,
    quantity: draft.quantity,
    est_shipping_note: draft.est_shipping_note,
    item_specifics: draft.item_specifics,
    photo_ids: draft.photo_ids,
    include_sku_footer: draft.include_sku_footer,
    boilerplate: draft.boilerplate
  };
}
