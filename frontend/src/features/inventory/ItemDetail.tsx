import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ChevronLeft, ChevronRight, MoreHorizontal, Save, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { itemTabs, tabAnchors, tabForAnchor, rememberedItemTab, focusItemField, type ItemTab } from "../../components/itemNavigation";
import { useRefreshableForm } from "../../components/useRefreshableForm";
import { EbayItemWarnings } from "../../components/EbayItemWarnings";

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
import { EbayListingEntry } from "../../components/EbayListingEntry";
import { EbayQuantityPanel } from "../../components/EbayQuantityPanel";
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

type ItemEditorForm = ItemFormPayload & { status: string };

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
  const [activeTab, setActiveTab] = useState<ItemTab>(() => tabForAnchor(location.hash) ?? (new URLSearchParams(location.search).has("draft") ? "eBay" : rememberedItemTab(itemId)));
  const [more, setMore] = useState(false);
  const [tabOverflow, setTabOverflow] = useState({ left: false, right: true, any: true });

  const savedForm = useMemo<ItemEditorForm | null>(() => item.data ? {
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

  } : null, [item.data]);
  const [form, setForm, acknowledge] = useRefreshableForm<ItemEditorForm>(itemId, savedForm, {
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

  const orderedPhotos = useMemo(
    () => [...(item.data?.photos ?? [])].sort((a, b) => a.order_index - b.order_index),
    [item.data?.photos]
  );

  useEffect(() => {
    const strip = document.querySelector<HTMLElement>(".item-tabs");
    if (!strip) return;
    const update = () => setTabOverflow({ left: strip.scrollLeft > 1, right: strip.scrollLeft + strip.clientWidth < strip.scrollWidth - 1, any: strip.scrollWidth > strip.clientWidth + 1 });
    update();
    strip.addEventListener("scroll", update);
    window.addEventListener("resize", update);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(strip);
    return () => { strip.removeEventListener("scroll", update); window.removeEventListener("resize", update); observer?.disconnect(); };
  }, [itemId, item.isSuccess]);

  useEffect(() => {
    const explicit = tabForAnchor(location.hash) ?? (new URLSearchParams(location.search).has("draft") ? "eBay" : undefined);
    setActiveTab(explicit ?? rememberedItemTab(itemId));
    if (location.hash && item.isSuccess) focusItemField(location.hash.slice(1));
  }, [itemId, location.hash, location.search, location.key, item.isSuccess]);

  useEffect(() => {
    try { localStorage.setItem(`magpie:item-tab:v1:${itemId}`, activeTab); } catch { /* Optional preference. */ }
    const tab = document.getElementById(`item-tab-${activeTab}`);
    const strip = tab?.parentElement;
    if (tab && strip) {
      if (tab.offsetLeft < strip.scrollLeft) strip.scrollLeft = tab.offsetLeft;
      else if (tab.offsetLeft + tab.offsetWidth > strip.scrollLeft + strip.clientWidth) strip.scrollLeft = tab.offsetLeft + tab.offsetWidth - strip.clientWidth;
    }
  }, [itemId, activeTab]);

  useEffect(() => {
    const reveal = (event: Event) => {
      const anchor = (event as CustomEvent<{ id: string }>).detail.id;
      const panel = document.getElementById(anchor)?.closest<HTMLElement>("[data-item-tab]");
      const tab = tabForAnchor(anchor) ?? panel?.dataset.itemTab as ItemTab | undefined;
      if (tab) {
        setActiveTab(tab);
        if (location.hash !== `#${anchor}`) navigate({ search: location.search, hash: `#${anchor}` }, { replace: true });
      }
    };
    const open = (event: Event) => {
      const draftId = (event as CustomEvent<{ draftId?: string }>).detail?.draftId;
      const search = new URLSearchParams(location.search);
      if (draftId) search.set("draft", draftId);
      setActiveTab("eBay");
      navigate({ search: search.toString(), hash: "#listings-channels" }, { replace: true });
      focusItemField(`listing-entry-${itemId}`);
    };
    const openPhotos = () => {
      setActiveTab("Photos");
      navigate({ search: location.search, hash: "#photos" });
      window.setTimeout(() => { document.querySelector<HTMLInputElement>('#photos input[type="file"]')?.focus({ preventScroll: true }); }, 0);
    };
    window.addEventListener("magpie:reveal-item-field", reveal);
    window.addEventListener(`magpie:open-draft:${itemId}`, open);
    window.addEventListener(`magpie:upload-photos:${itemId}`, openPhotos);
    return () => {
      window.removeEventListener("magpie:reveal-item-field", reveal);
      window.removeEventListener(`magpie:open-draft:${itemId}`, open);
      window.removeEventListener(`magpie:upload-photos:${itemId}`, openPhotos);
    };
  }, [itemId, location.search, location.hash, navigate]);

  function selectTab(tab: ItemTab) {
    setActiveTab(tab);
    navigate({ search: location.search, hash: `#${tabAnchors[tab]}` });
  }

  const refresh = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ["item", itemId] }),
    queryClient.invalidateQueries({ queryKey: ["ebay-quantity", itemId] }),
    queryClient.invalidateQueries({ queryKey: ["ebay-hub"] })
  ]);

  const saveMutation = useMutation({
    mutationFn: (payload: Partial<ItemFormPayload>) => updateItem(itemId, payload),
    onSuccess: (_result, payload) => { acknowledge(payload); return refresh(); }
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

  function coreDetailsPayload(): Partial<ItemFormPayload> {
    return {
      title: form.title,
      category: form.category,
      status: form.status,
      condition: form.condition,
      quantity_total: form.quantity_total,
      location: form.location
    };
  }

  function categorySpecificsPayload(): Partial<ItemFormPayload> {
    return {
      category: form.category,
      lot: form.lot,
      source: form.source,
      disposition: form.disposition,
      scrapped_at: form.scrapped_at,
      acquisition_cost: form.acquisition_cost,
      refurb_cost: form.refurb_cost,
      inbound_shipping_cost: form.inbound_shipping_cost,
      est_outbound_shipping: form.est_outbound_shipping,
      est_packaging_cost: form.est_packaging_cost,
      estimated_value: form.estimated_value,
      notes: form.notes,
      attributes: sanitizeSchemaAttributes(form.attributes ?? {})
    };
  }

  if (item.isLoading) {
    return <PageFrame><EmptyState title="Loading item" /></PageFrame>;
  }

  if (item.error || !item.data) {
    return <PageFrame><AuthRequiredState detail="Sign in to see this item, then return here after signing in." /></PageFrame>;
  }

  return (
    <PageFrame>
      <div className="item-identity">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="page-title listing-title min-w-0">{item.data.title || "Untitled item"}</h1>
            <StatusBadge status={item.data.status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">{item.data.sku}</p>
        </div>
        <div className="item-more">
          <button className="icon-button" aria-label="More actions" aria-expanded={more} title="More actions" onClick={() => setMore(!more)} type="button"><MoreHorizontal size={22} aria-hidden="true" /></button>
          {more ? <div className="item-more-menu"><button className="btn-danger gap-2" onClick={() => { setMore(false); setDeleteTarget("item"); }} type="button"><Trash2 size={18} aria-hidden="true" />Delete item</button></div> : null}
        </div>
      </div>

      <EbayListingEntry item={item.data} />
      <EbayItemWarnings item={item.data} />
      <div className={`item-tabs-shell${tabOverflow.any ? " has-overflow" : ""}`}>
        <div aria-label="Item tabs" role="tablist" className="item-tabs">
          {itemTabs.map((tab, index) => <button key={tab} id={`item-tab-${tab}`} role="tab" aria-selected={activeTab === tab} aria-controls={`item-panel-${tab}`} tabIndex={activeTab === tab ? 0 : -1}
            onClick={() => selectTab(tab)} onKeyDown={(event) => {
              const next = event.key === "Home" ? 0 : event.key === "End" ? itemTabs.length - 1 : event.key === "ArrowRight" ? (index + 1) % itemTabs.length : event.key === "ArrowLeft" ? (index + itemTabs.length - 1) % itemTabs.length : -1;
              if (next >= 0) { event.preventDefault(); selectTab(itemTabs[next]); document.getElementById(`item-tab-${itemTabs[next]}`)?.focus(); }
            }} type="button">{tab}</button>)}
        </div>
        {tabOverflow.any ? <button className="icon-button item-tabs-overflow" aria-label={tabOverflow.right ? "More item tabs" : "Previous item tabs"} title={tabOverflow.right ? "More item tabs" : "Previous item tabs"} onClick={() => {
          const strip = document.querySelector<HTMLElement>(".item-tabs");
          strip?.scrollBy({ left: (tabOverflow.right ? 1 : -1) * strip.clientWidth * 0.75, behavior: "smooth" });
        }} type="button">{tabOverflow.right ? <ChevronRight size={20} aria-hidden="true" /> : <ChevronLeft size={20} aria-hidden="true" />}</button> : null}
      </div>
      <div className="item-tab-panels" key={itemId}>
        <TabPanel tab="Photos" active={activeTab}>
          <ItemSection id="photos" label="Photos">
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <PhotoUploader files={files} onFiles={setFiles} compact />
              <button className="btn-primary" disabled={files.length === 0 || uploadMutation.isPending} onClick={() => uploadMutation.mutate()} type="button">
                Upload selected
              </button>
            </div>
            <PhotoGallery
              photos={orderedPhotos}
              onSetMain={(photo) => setMainMutation.mutate(photo)}
              onMove={movePhoto}
              onDelete={(photo) => setDeleteTarget(photo)}
            />
            <details className="mt-4"><summary className="min-h-11 cursor-pointer py-3 font-semibold">Photo adjustments</summary>
              <PhotoFixupPanel itemId={itemId} photos={orderedPhotos} onChanged={refresh} />
            </details>
          </ItemSection>

        </TabPanel>
        <TabPanel tab="Details" active={activeTab}>
          <ItemSection id="core-details" label="Core details">
            <form className="item-detail-form-grid" onSubmit={(event) => { event.preventDefault(); saveMutation.mutate(coreDetailsPayload()); }}>
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

          <ItemSection id="category-specifics" label="Category specifics">
            <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); saveMutation.mutate(categorySpecificsPayload()); }}>
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

        </TabPanel>
        <TabPanel tab="Research" active={activeTab}>
          <ItemSection id="ai-research" label="AI research">
            <div className="ai-review-stack">
            <AIResearchPanel itemId={itemId} onReviewSuggestions={() => focusItemField("ai-review")} />
              <div id="ai-review">
                <SuggestionReviewPanel itemId={itemId} />
              </div>
            </div>
          </ItemSection>

          <ResearchLinks itemId={itemId} />
          <div id="research-log"><ResearchLog itemId={itemId} /></div>
        </TabPanel>
        <TabPanel tab="Pricing" active={activeTab}>
          <section id="sales-valuations" tabIndex={-1} className="item-detail-section">
            <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="section-title">Pricing</h2><button className="row-link gap-2" onClick={() => selectTab("Sales")} type="button">Sales<ArrowRight size={18} aria-hidden="true" /></button></div>
            <ValuationPanel item={item.data} />
            <ProfitBreakdown item={item.data} reportId={item.data.current_valuation?.id ?? null} />
          </section>
          <ItemSection id="pricing-evidence" label="Pricing evidence & comps">
            <div className="grid gap-6">
              <DescriptorEvidencePanel
                attributes={item.data.attributes ?? {}}
                categoryId={item.data.category ?? ""}
                itemId={itemId}
                terms={item.data.title || item.data.sku}
                title="Matching item evidence"
                onUsePrice={(row) => navigate("/buy-calculator", { state: { ownedEvidence: {
                  rowId: row.id, itemId, category: item.data.category ?? "", terms: item.data.title || item.data.sku,
                  attributes: item.data.attributes ?? {}
                } } })}
              />
              <PricingEvidencePanel itemId={itemId} />
              <SoldSearchPanel itemId={itemId} />
              <div className="grid gap-6 xl:grid-cols-2">
                <ComparableList itemId={itemId} />
              </div>
            </div>
          </ItemSection>

        </TabPanel>
        <TabPanel tab="eBay" active={activeTab}>
          <EbayQuantityPanel itemId={itemId} showAllocationUnknown={item.data.quantity_total > 1} />
          <ItemSection id="listings-channels" label="Listings / channels">
            <div className="grid gap-6">
                <ListingPanel key={itemId} item={item.data} initialDraftId={new URLSearchParams(location.search).get("draft")} />
                <div id={`take-down-${itemId}`} tabIndex={-1}><TakeDownChecklist item={item.data} /></div>
                <CopyPackPanel item={item.data} />
            </div>
          </ItemSection>

        </TabPanel>
        <TabPanel tab="Sales" active={activeTab}>
          <section id="item-sales" tabIndex={-1}><SalesPanel item={item.data} /></section>
        </TabPanel>
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        title={deleteTarget === "item" ? "Delete item?" : "Delete photo?"}
        detail={deleteTarget === "item" ? `${item.data.title || "Untitled item"} (${item.data.sku})` : `Photo from ${item.data.title || item.data.sku}`}
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
  return <div className="item-page-frame mx-auto w-full max-w-7xl">{children}</div>;
}

function TabPanel({ tab, active, children }: { tab: ItemTab; active: ItemTab; children: ReactNode }) {
  return <div className="item-tab-panel" id={`item-panel-${tab}`} role="tabpanel" aria-labelledby={`item-tab-${tab}`} data-item-tab={tab} hidden={active !== tab}>{children}</div>;
}

function ItemSection({ children, id, label }: { children: ReactNode; id: string; label: string }) {
  return <section className="item-detail-section" id={id} tabIndex={-1}>
    <h2 className="section-title">{label}</h2>
    <div className="item-detail-section-body" id={`${id}-panel`}>{children}</div>
  </section>;
}
