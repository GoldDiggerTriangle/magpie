import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { listCategories } from "../../api/categories";
import { deleteItem, getItem, reorderPhotos, updateItem, uploadItemPhoto } from "../../api/items";
import { listLocations } from "../../api/locations";
import { deletePhoto, updatePhoto } from "../../api/photos";
import { CategorySelect } from "../../components/CategorySelect";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import { LocationSelect } from "../../components/LocationSelect";
import { ListingPanel } from "../../components/ListingPanel";
import { PhotoGallery } from "../../components/PhotoGallery";
import { PhotoUploader } from "../../components/PhotoUploader";
import { ComparableList } from "../../components/ComparableList";
import { PricingEvidencePanel } from "../../components/PricingEvidencePanel";
import { ProfitBreakdown } from "../../components/ProfitBreakdown";
import { ResearchLinks } from "../../components/ResearchLinks";
import { ResearchLog } from "../../components/ResearchLog";
import { SalesPanel } from "../../components/SalesPanel";
import { sanitizeSchemaAttributes, SchemaFieldsForm } from "../../components/SchemaFieldsForm";
import { SoldSearchPanel } from "../../components/SoldSearchPanel";
import { StatusBadge } from "../../components/StatusBadge";
import { SuggestionReviewPanel } from "../../components/SuggestionReviewPanel";
import { ValuationPanel } from "../../components/ValuationPanel";
import type { ItemFormPayload, PhotoAsset, UUID } from "../../types";

const statusOptions = [
  ["captured", "Captured"],
  ["needs_identification", "Needs ID"],
  ["needs_cleaning", "Needs cleaning"],
  ["needs_research", "Needs research"],
  ["ready_to_list", "Ready"],
  ["listed", "Listed"],
  ["partially_sold", "Partially sold"],
  ["sold", "Sold"],
  ["stored", "Stored"],
  ["archived", "Archived"],
  ["in_bulk_lot", "Bulk lot"]
];

const conditionOptions = [
  ["ungraded", "Ungraded"],
  ["new", "New"],
  ["like_new", "Like new"],
  ["very_good", "Very good"],
  ["good", "Good"],
  ["acceptable", "Acceptable"],
  ["for_parts", "For parts"]
];

export function ItemDetail() {
  const { id } = useParams();
  const itemId = id as UUID;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const item = useQuery({ queryKey: ["item", itemId], queryFn: () => getItem(itemId), enabled: Boolean(itemId) });
  const categories = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const locations = useQuery({ queryKey: ["locations"], queryFn: listLocations });
  const [files, setFiles] = useState<File[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<PhotoAsset | "item" | null>(null);

  const [form, setForm] = useState<ItemFormPayload & { status: string }>({
    title: "",
    category: null,
    status: "captured",
    condition: "ungraded",
    quantity_total: 1,
    location: null,
    acquisition_cost: null,
    refurb_cost: null,
    inbound_shipping_cost: null,
    est_outbound_shipping: null,
    est_packaging_cost: null,
    estimated_value: null,
    notes: "",
    attributes: {}
  });

  useEffect(() => {
    if (!item.data) {
      return;
    }
    setForm({
      title: item.data.title,
      category: item.data.category,
      status: item.data.status,
      condition: item.data.condition,
      quantity_total: item.data.quantity_total,
      location: item.data.location,
      acquisition_cost: item.data.acquisition_cost,
      refurb_cost: item.data.refurb_cost,
      inbound_shipping_cost: item.data.inbound_shipping_cost,
      est_outbound_shipping: item.data.est_outbound_shipping,
      est_packaging_cost: item.data.est_packaging_cost,
      estimated_value: item.data.estimated_value,
      notes: item.data.notes,
      attributes: item.data.attributes
    });
  }, [item.data]);

  const orderedPhotos = useMemo(
    () => [...(item.data?.photos ?? [])].sort((a, b) => a.order_index - b.order_index),
    [item.data?.photos]
  );

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["item", itemId] });

  const saveMutation = useMutation({
    mutationFn: () => updateItem(itemId, { ...form, attributes: sanitizeSchemaAttributes(form.attributes ?? {}) }),
    onSuccess: refresh
  });
  const uploadMutation = useMutation({
    mutationFn: async () => {
      for (const file of files) {
        await uploadItemPhoto(itemId, file, "other");
      }
    },
    onSuccess: () => {
      setFiles([]);
      refresh();
    }
  });
  const deleteItemMutation = useMutation({
    mutationFn: () => deleteItem(itemId),
    onSuccess: () => navigate("/inventory")
  });
  const deletePhotoMutation = useMutation({
    mutationFn: (photo: PhotoAsset) => deletePhoto(photo.id),
    onSuccess: refresh
  });
  const setMainMutation = useMutation({
    mutationFn: (photo: PhotoAsset) => updatePhoto(photo.id, { is_main: true }),
    onSuccess: refresh
  });
  const reorderMutation = useMutation({
    mutationFn: (order: UUID[]) => reorderPhotos(itemId, order),
    onSuccess: refresh
  });

  function movePhoto(photo: PhotoAsset, direction: -1 | 1) {
    const index = orderedPhotos.findIndex((candidate) => candidate.id === photo.id);
    const nextIndex = index + direction;
    if (index < 0 || nextIndex < 0 || nextIndex >= orderedPhotos.length) {
      return;
    }
    const next = [...orderedPhotos];
    const [removed] = next.splice(index, 1);
    next.splice(nextIndex, 0, removed);
    reorderMutation.mutate(next.map((candidate) => candidate.id));
  }

  if (item.isLoading) {
    return <PageFrame><EmptyState title="Loading item" /></PageFrame>;
  }

  if (item.error || !item.data) {
    return <PageFrame><EmptyState title="Unable to load item" detail="Check your Django admin session." /></PageFrame>;
  }

  return (
    <PageFrame>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="page-title">{item.data.title || "Untitled item"}</h1>
            <StatusBadge status={item.data.status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">{item.data.sku}</p>
        </div>
        <button className="btn-danger inline-flex items-center gap-2" onClick={() => setDeleteTarget("item")} type="button">
          <Trash2 className="h-4 w-4" aria-hidden="true" />
          Delete
        </button>
      </div>

      <div className="mt-6 grid gap-8 xl:grid-cols-[minmax(0,1.4fr)_minmax(360px,0.8fr)]">
        <div>
          <PhotoGallery
            photos={orderedPhotos}
            onSetMain={(photo) => setMainMutation.mutate(photo)}
            onMove={movePhoto}
            onDelete={(photo) => setDeleteTarget(photo)}
          />
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <PhotoUploader files={files} onFiles={setFiles} compact />
            <button className="btn-primary" disabled={files.length === 0 || uploadMutation.isPending} onClick={() => uploadMutation.mutate()} type="button">
              Upload selected
            </button>
          </div>
        </div>

        <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); saveMutation.mutate(); }}>
          <label className="label">
            <span>Title</span>
            <input className="field" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
          </label>
          <label className="label">
            <span>Status</span>
            <select className="field" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
              {statusOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="label">
            <span>Condition</span>
            <select className="field" value={form.condition} onChange={(event) => setForm({ ...form, condition: event.target.value })}>
              {conditionOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="label">
            <span>Total quantity</span>
            <input
              className="field"
              min={Math.max(1, item.data.quantity_sold)}
              type="number"
              value={form.quantity_total ?? 1}
              onChange={(event) => setForm({ ...form, quantity_total: Math.max(1, Number(event.target.value) || 1) })}
            />
            <span className="text-xs font-normal text-slate-500">
              {item.data.quantity_sold} sold / {item.data.quantity_remaining} remaining
            </span>
          </label>
          <label className="label">
            <span>Category</span>
            <CategorySelect
              categories={categories.data?.results ?? []}
              value={form.category}
              onChange={(value) => setForm({
                ...form,
                category: value,
                attributes: value === form.category ? form.attributes : {}
              })}
            />
          </label>
          <SchemaFieldsForm
            categoryId={form.category}
            attributes={form.attributes ?? {}}
            onChange={(attributes) => setForm((current) => ({ ...current, attributes }))}
          />
          <label className="label">
            <span>Location</span>
            <LocationSelect locations={locations.data?.results ?? []} value={form.location} onChange={(value) => setForm({ ...form, location: value })} />
          </label>
          <label className="label">
            <span>Acquisition cost</span>
            <input className="field" inputMode="decimal" value={form.acquisition_cost ?? ""} onChange={(event) => setForm({ ...form, acquisition_cost: event.target.value || null })} />
          </label>
          <label className="label">
            <span>Refurb cost</span>
            <input className="field" inputMode="decimal" value={form.refurb_cost ?? ""} onChange={(event) => setForm({ ...form, refurb_cost: event.target.value || null })} />
          </label>
          <label className="label">
            <span>Inbound shipping</span>
            <input className="field" inputMode="decimal" value={form.inbound_shipping_cost ?? ""} onChange={(event) => setForm({ ...form, inbound_shipping_cost: event.target.value || null })} />
          </label>
          <label className="label">
            <span>Outbound shipping est.</span>
            <input className="field" inputMode="decimal" value={form.est_outbound_shipping ?? ""} onChange={(event) => setForm({ ...form, est_outbound_shipping: event.target.value || null })} />
          </label>
          <label className="label">
            <span>Packaging est.</span>
            <input className="field" inputMode="decimal" value={form.est_packaging_cost ?? ""} onChange={(event) => setForm({ ...form, est_packaging_cost: event.target.value || null })} />
          </label>
          <label className="label">
            <span>Estimated value</span>
            <input className="field" inputMode="decimal" value={form.estimated_value ?? ""} onChange={(event) => setForm({ ...form, estimated_value: event.target.value || null })} />
          </label>
          <label className="label">
            <span>Notes</span>
            <textarea className="field min-h-28" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
          </label>
          <button className="btn-primary inline-flex items-center gap-2" disabled={saveMutation.isPending} type="submit">
            <Save className="h-4 w-4" aria-hidden="true" />
            Save
          </button>
        </form>
      </div>

      <div className="mt-8 grid gap-6">
        <PricingEvidencePanel itemId={itemId} />
        <SoldSearchPanel itemId={itemId} />
        <SuggestionReviewPanel itemId={itemId} />
        <ResearchLinks itemId={itemId} />
        <div className="grid gap-6 xl:grid-cols-2">
          <ComparableList itemId={itemId} />
          <ResearchLog itemId={itemId} />
        </div>
        <ValuationPanel item={item.data} />
        <ProfitBreakdown item={item.data} reportId={item.data.current_valuation?.id ?? null} />
        <ListingPanel item={item.data} />
        <SalesPanel item={item.data} />
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        title={deleteTarget === "item" ? "Delete item?" : "Delete photo?"}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget === "item") {
            deleteItemMutation.mutate();
          } else if (deleteTarget) {
            deletePhotoMutation.mutate(deleteTarget);
          }
          setDeleteTarget(null);
        }}
      />
    </PageFrame>
  );
}

function PageFrame({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">{children}</div>;
}
