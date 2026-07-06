import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Save, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { listCategories } from "../../api/categories";
import { deleteItem, getItem, reorderPhotos, updateItem, uploadItemPhoto } from "../../api/items";
import { listLocations } from "../../api/locations";
import { listLots, listSources } from "../../api/lots";
import { deletePhoto, updatePhoto } from "../../api/photos";
import { AuthRequiredState } from "../../components/AuthRequiredState";
import { CategorySelect } from "../../components/CategorySelect";
import { AIResearchPanel } from "../../components/AIResearchPanel";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DescriptorEvidencePanel } from "../../components/DescriptorEvidencePanel";
import { EmptyState } from "../../components/EmptyState";
import { LocationSelect } from "../../components/LocationSelect";
import { ListingPanel } from "../../components/ListingPanel";
import { PhotoFixupPanel } from "../../components/PhotoFixupPanel";
import { PhotoGallery } from "../../components/PhotoGallery";
import { PhotoUploader } from "../../components/PhotoUploader";
import { ComparableList } from "../../components/ComparableList";
import { CopyPackPanel } from "../../components/CopyPackPanel";
import { PricingEvidencePanel } from "../../components/PricingEvidencePanel";
import { ProfitBreakdown } from "../../components/ProfitBreakdown";
import { ResearchLinks } from "../../components/ResearchLinks";
import { ResearchLog } from "../../components/ResearchLog";
import { SalesPanel } from "../../components/SalesPanel";
import { sanitizeSchemaAttributes, SchemaFieldsForm } from "../../components/SchemaFieldsForm";
import { SoldSearchPanel } from "../../components/SoldSearchPanel";
import { StatusBadge } from "../../components/StatusBadge";
import { SuggestionReviewPanel } from "../../components/SuggestionReviewPanel";
import { TakeDownChecklist } from "../../components/TakeDownChecklist";
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

const itemSections = [
  { id: "photos", label: "Photos" },
  { id: "core-details", label: "Core details" },
  { id: "category-specifics", label: "Category specifics" },
  { id: "ai-research", label: "AI research" },
  { id: "pricing-evidence", label: "Pricing evidence & comps" },
  { id: "listings-channels", label: "Listings / channels" },
  { id: "sales-valuations", label: "Sales & valuations" }
] as const;

type ItemSectionId = typeof itemSections[number]["id"];
type OpenSections = Record<ItemSectionId, boolean>;

const defaultOpenSections: OpenSections = {
  photos: true,
  "core-details": true,
  "category-specifics": false,
  "ai-research": false,
  "pricing-evidence": false,
  "listings-channels": false,
  "sales-valuations": false
};

const hashSectionMap: Record<string, ItemSectionId> = {
  "#photos": "photos",
  "#core-details": "core-details",
  "#category-specifics": "category-specifics",
  "#ai-research": "ai-research",
  "#ai-review": "ai-research",
  "#pricing-evidence": "pricing-evidence",
  "#listings-channels": "listings-channels",
  "#sales-valuations": "sales-valuations"
};

export function ItemDetail() {
  const { id } = useParams();
  const itemId = id as UUID;
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const item = useQuery({ queryKey: ["item", itemId], queryFn: () => getItem(itemId), enabled: Boolean(itemId) });
  const categories = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const locations = useQuery({ queryKey: ["locations"], queryFn: listLocations });
  const lots = useQuery({ queryKey: ["lots", "item-detail"], queryFn: listLots });
  const sources = useQuery({ queryKey: ["sources", "item-detail"], queryFn: listSources });
  const [files, setFiles] = useState<File[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<PhotoAsset | "item" | null>(null);
  const [openSections, setOpenSections] = useState<OpenSections>(() => readStoredSections(itemId));

  const [form, setForm] = useState<ItemFormPayload & { status: string }>({
    title: "",
    category: null,
    status: "captured",
    condition: "ungraded",
    quantity_total: 1,
    location: null,
    lot: null,
    source: null,
    disposition: "for_sale",
    scrapped_at: null,
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
      lot: item.data.lot,
      source: item.data.source,
      disposition: item.data.disposition,
      scrapped_at: item.data.scrapped_at,
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

  useEffect(() => {
    setOpenSections(readStoredSections(itemId));
  }, [itemId]);

  useEffect(() => {
    try {
      localStorage.setItem(sectionStorageKey(itemId), JSON.stringify(openSections));
    } catch {
      // Collapsed section state is a convenience only; failure should not block item editing.
    }
  }, [itemId, openSections]);

  useEffect(() => {
    const targetSection = hashSectionMap[location.hash];
    if (!targetSection) {
      return;
    }
    setOpenSections((current) => ({ ...current, [targetSection]: true }));
    window.setTimeout(() => {
      scrollToElement(location.hash.replace(/^#/, ""));
    }, 0);
  }, [location.hash]);

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

  function setSection(sectionId: ItemSectionId, open: boolean) {
    setOpenSections((current) => ({ ...current, [sectionId]: open }));
  }

  function setAllSections(open: boolean) {
    setOpenSections(Object.fromEntries(itemSections.map((section) => [section.id, open])) as OpenSections);
  }

  function jumpToSection(sectionId: ItemSectionId, anchorId: string = sectionId) {
    setSection(sectionId, true);
    window.history.replaceState(null, "", `#${anchorId}`);
    window.setTimeout(() => {
      scrollToElement(anchorId);
    }, 0);
  }

  if (item.isLoading) {
    return <PageFrame><EmptyState title="Loading item" /></PageFrame>;
  }

  if (item.error || !item.data) {
    return <PageFrame><AuthRequiredState detail="Item details need a Magpie session. Open the admin login, sign in, then return to this item." /></PageFrame>;
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

      <div className="item-detail-controls">
        <button className="ledger-button" onClick={() => setAllSections(true)} type="button">Expand all</button>
        <button className="ledger-button" onClick={() => setAllSections(false)} type="button">Collapse all</button>
      </div>

      <div className="item-detail-layout">
        <nav aria-label="Item sections" className="item-section-index">
          {itemSections.map((section) => (
            <button key={section.id} onClick={() => jumpToSection(section.id)} type="button">
              {section.label}
            </button>
          ))}
        </nav>

        <div className="item-section-stack">
          <ItemSection id="photos" label="Photos" open={openSections.photos} onToggle={() => setSection("photos", !openSections.photos)}>
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
            <div className="mt-4">
              <PhotoFixupPanel itemId={itemId} photos={orderedPhotos} onChanged={refresh} />
            </div>
          </ItemSection>

          <ItemSection id="core-details" label="Core details" open={openSections["core-details"]} onToggle={() => setSection("core-details", !openSections["core-details"])}>
            <form className="item-detail-form-grid" onSubmit={(event) => { event.preventDefault(); saveMutation.mutate(); }}>
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
                <span className="text-xs font-normal text-slate-700">
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
              <label className="label">
                <span>Location</span>
                <LocationSelect locations={locations.data?.results ?? []} value={form.location} onChange={(value) => setForm({ ...form, location: value })} />
              </label>
              <button className="btn-primary inline-flex items-center gap-2 self-end" disabled={saveMutation.isPending} type="submit">
                <Save className="h-4 w-4" aria-hidden="true" />
                Save
              </button>
            </form>
          </ItemSection>

          <ItemSection id="category-specifics" label="Category specifics" open={openSections["category-specifics"]} onToggle={() => setSection("category-specifics", !openSections["category-specifics"])}>
            <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); saveMutation.mutate(); }}>
              <SchemaFieldsForm
                categoryId={form.category}
                attributes={form.attributes ?? {}}
                onChange={(attributes) => setForm((current) => ({ ...current, attributes }))}
              />
              <div className="item-detail-form-grid">
                <label className="label">
                  <span>Lot</span>
                  <select className="field" value={form.lot ?? ""} onChange={(event) => setForm({ ...form, lot: event.target.value || null, source: event.target.value ? null : form.source })}>
                    <option value="">Single item / no lot</option>
                    {(lots.data?.results ?? []).map((lot) => <option key={lot.id} value={lot.id}>{lot.label}</option>)}
                  </select>
                  {form.lot ? <span className="text-xs font-normal text-slate-700">Source is inherited from the lot.</span> : null}
                </label>
                <label className="label">
                  <span>Source</span>
                  <select className="field" disabled={Boolean(form.lot)} value={form.source ?? ""} onChange={(event) => setForm({ ...form, source: event.target.value || null })}>
                    <option value="">No source</option>
                    {(sources.data?.results ?? []).map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}
                  </select>
                  {item.data.effective_source ? <span className="text-xs font-normal text-slate-700">Effective source: {item.data.effective_source.name}</span> : null}
                </label>
                <label className="label">
                  <span>Disposition</span>
                  <select className="field" value={form.disposition} onChange={(event) => setForm({ ...form, disposition: event.target.value as "for_sale" | "scrapped" })}>
                    <option value="for_sale">For sale</option>
                    <option value="scrapped">Scrapped</option>
                  </select>
                </label>
                <label className="label">
                  <span>Scrapped date</span>
                  <input className="field" type="date" value={form.scrapped_at ?? ""} onChange={(event) => setForm({ ...form, scrapped_at: event.target.value || null })} />
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
                <label className="label md:col-span-2">
                  <span>Notes</span>
                  <textarea className="field min-h-28" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
                </label>
                <button className="btn-primary inline-flex items-center gap-2 self-end" disabled={saveMutation.isPending} type="submit">
                  <Save className="h-4 w-4" aria-hidden="true" />
                  Save
                </button>
              </div>
            </form>
          </ItemSection>

          <ItemSection id="ai-research" label="AI research" open={openSections["ai-research"]} onToggle={() => setSection("ai-research", !openSections["ai-research"])}>
            <div className="ai-review-stack">
              <AIResearchPanel itemId={itemId} onReviewSuggestions={() => jumpToSection("ai-research", "ai-review")} />
              <div id="ai-review">
                <SuggestionReviewPanel itemId={itemId} />
              </div>
            </div>
          </ItemSection>

          <ItemSection id="pricing-evidence" label="Pricing evidence & comps" open={openSections["pricing-evidence"]} onToggle={() => setSection("pricing-evidence", !openSections["pricing-evidence"])}>
            <div className="grid gap-6">
              <DescriptorEvidencePanel
                attributes={item.data.attributes ?? {}}
                categoryId={item.data.category ?? ""}
                itemId={itemId}
                terms={item.data.title || item.data.sku}
                title="Item descriptor evidence"
              />
              <PricingEvidencePanel itemId={itemId} />
              <SoldSearchPanel itemId={itemId} />
              <ResearchLinks itemId={itemId} />
              <div className="grid gap-6 xl:grid-cols-2">
                <ComparableList itemId={itemId} />
                <ResearchLog itemId={itemId} />
              </div>
            </div>
          </ItemSection>

          <ItemSection id="listings-channels" label="Listings / channels" open={openSections["listings-channels"]} onToggle={() => setSection("listings-channels", !openSections["listings-channels"])}>
            <div className="grid gap-6">
              <TakeDownChecklist item={item.data} />
              <CopyPackPanel item={item.data} />
              <ListingPanel item={item.data} />
            </div>
          </ItemSection>

          <ItemSection id="sales-valuations" label="Sales & valuations" open={openSections["sales-valuations"]} onToggle={() => setSection("sales-valuations", !openSections["sales-valuations"])}>
            <div className="grid gap-6">
              <ValuationPanel item={item.data} />
              <ProfitBreakdown item={item.data} reportId={item.data.current_valuation?.id ?? null} />
              <SalesPanel item={item.data} />
            </div>
          </ItemSection>
        </div>
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

function ItemSection({
  children,
  id,
  label,
  onToggle,
  open
}: {
  children: ReactNode;
  id: ItemSectionId;
  label: string;
  onToggle: () => void;
  open: boolean;
}) {
  return (
    <section className="item-detail-section" id={id}>
      <button
        aria-controls={`${id}-panel`}
        aria-expanded={open}
        className="item-detail-section-header"
        onClick={onToggle}
        type="button"
      >
        <span>{label}</span>
        {open ? <ChevronDown className="h-5 w-5" aria-hidden="true" /> : <ChevronRight className="h-5 w-5" aria-hidden="true" />}
      </button>
      <div className="item-detail-section-body" hidden={!open} id={`${id}-panel`}>
        {children}
      </div>
    </section>
  );
}

function sectionStorageKey(itemId: UUID) {
  return `magpie:item-detail-sections:v1:${itemId}`;
}

function readStoredSections(itemId: UUID): OpenSections {
  try {
    const raw = localStorage.getItem(sectionStorageKey(itemId));
    if (!raw) {
      return { ...defaultOpenSections };
    }
    const parsed = JSON.parse(raw) as Partial<Record<ItemSectionId, boolean>>;
    return Object.fromEntries(
      itemSections.map((section) => [section.id, parsed[section.id] ?? defaultOpenSections[section.id]])
    ) as OpenSections;
  } catch {
    return { ...defaultOpenSections };
  }
}

function scrollToElement(id: string) {
  const target = document.getElementById(id);
  if (target && typeof target.scrollIntoView === "function") {
    target.scrollIntoView({ block: "start" });
  }
}
