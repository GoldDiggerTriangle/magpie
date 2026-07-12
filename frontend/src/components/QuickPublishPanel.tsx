import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Send, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getEbayCategorySuggestions, getEbayStatus } from "../api/ebay";
import {
  createItemListingDraft,
  getItemCopyPack,
  listItemListingDrafts,
  publishListingDraft,
  stageListingDraft,
  updateListingDraft
} from "../api/listing";
import type { EbayCategorySuggestion, EbayCategorySuggestionsResponse, EbayStatus, InventoryItemDetail, ListingDraft } from "../types";

type PriceChoice =
  | { status: "ready"; value: string; label: string; basis: "item_asking_or_listed_price" | "human_picked_evidence" }
  | { status: "missing"; label: string; basis: "missing" };

interface Blocker {
  key: string;
  label: string;
  detail: string;
  actionLabel: string;
}

export function QuickPublishPanel({ item }: { item: InventoryItemDetail }) {
  const queryClient = useQueryClient();
  const drafts = useQuery({
    queryKey: ["item-listing-drafts", item.id],
    queryFn: () => listItemListingDrafts(item.id)
  });
  const ebayStatus = useQuery({
    queryKey: ["ebay-status"],
    queryFn: getEbayStatus
  });
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewDraft, setPreviewDraft] = useState<ListingDraft | null>(null);
  const [humanEvidencePrice, setHumanEvidencePrice] = useState("");
  const [humanEvidenceLabel, setHumanEvidenceLabel] = useState("");
  const [categorySearch, setCategorySearch] = useState("");
  const [categoryResult, setCategoryResult] = useState<EbayCategorySuggestionsResponse | null>(null);
  const [shippingNoteDraft, setShippingNoteDraft] = useState("");
  const [publishResult, setPublishResult] = useState<{ listingId: string; url: string } | null>(null);
  const [previewError, setPreviewError] = useState("");

  const currentDraft = previewDraft ?? drafts.data?.results?.[0] ?? null;
  const priceChoice = useMemo(
    () => chooseQuickPublishPrice(item, currentDraft, humanEvidencePrice, humanEvidenceLabel),
    [currentDraft, humanEvidenceLabel, humanEvidencePrice, item]
  );
  const copyPack = useQuery({
    queryKey: ["item-copy-pack", item.id, "ebay", humanEvidencePrice, humanEvidenceLabel],
    queryFn: () =>
      getItemCopyPack(item.id, {
        channel: "ebay",
        evidence_price: humanEvidencePrice || undefined,
        evidence_label: humanEvidenceLabel || undefined
      }),
    enabled: previewOpen
  });
  const blockers = useMemo(
    () => quickPublishBlockers(item, currentDraft, ebayStatus.data, ebayStatus.isLoading, priceChoice),
    [currentDraft, ebayStatus.data, ebayStatus.isLoading, item, priceChoice]
  );

  useEffect(() => {
    setShippingNoteDraft(currentDraft?.est_shipping_note || fallbackShippingNote(item));
  }, [currentDraft?.est_shipping_note, item.currency, item.est_packaging_cost, item.est_outbound_shipping]);

  async function ensureDraft() {
    if (currentDraft) {
      return currentDraft;
    }
    const draft = await createItemListingDraft(item.id);
    setPreviewDraft(draft);
    queryClient.invalidateQueries({ queryKey: ["item-listing-drafts", item.id] });
    return draft;
  }

  const openPreview = useMutation({
    mutationFn: async () => {
      return ensureDraft();
    },
    onSuccess: (draft) => {
      setPreviewDraft(draft);
      setPublishResult(null);
      setPreviewError("");
      setPreviewOpen(true);
      queryClient.invalidateQueries({ queryKey: ["item-listing-drafts", item.id] });
    },
    onError: (error) => {
      setPreviewError(error instanceof Error ? error.message : "Could not prepare the eBay preview.");
      setPreviewOpen(true);
    }
  });

  const publish = useMutation({
    mutationFn: async () => {
      if (!currentDraft) {
        throw new Error("Prepare the preview before posting.");
      }
      if (priceChoice.status !== "ready") {
        throw new Error("Choose an item asking price or human evidence price before posting.");
      }
      if (blockers.length > 0) {
        throw new Error("Resolve the blockers before posting live to eBay.");
      }
      const draft = await updateListingDraft(currentDraft.id, {
        price: priceChoice.value,
        description_html: copyPack.data?.sections.description
          ? textToHtml(copyPack.data.sections.description)
          : currentDraft.description_html,
        photo_ids: currentDraft.photo_ids.length > 0
          ? currentDraft.photo_ids
          : item.photos.map((photo) => photo.id),
        est_shipping_note: currentDraft.est_shipping_note || fallbackShippingNote(item),
        channel_data: currentDraft.channel_data
      });
      const staged = await stageListingDraft(draft.id);
      const published = await publishListingDraft(staged.id, item.sku);
      const listingId = stringValue(published.channel_data?.listing_id);
      if (!listingId) {
        throw new Error("eBay publish succeeded but no listing ID was returned.");
      }
      return {
        draft: published,
        listingId,
        url: ebayListingUrl(listingId)
      };
    },
    onSuccess: ({ draft, listingId, url }) => {
      setPreviewDraft(draft);
      setPublishResult({ listingId, url });
      queryClient.invalidateQueries({ queryKey: ["item", item.id] });
      queryClient.invalidateQueries({ queryKey: ["item-listing-drafts", item.id] });
      queryClient.invalidateQueries({ queryKey: ["channel-listings"] });
    }
  });

  const categorySearchMutation = useMutation({
    mutationFn: () => getEbayCategorySuggestions(categorySearch.trim()),
    onSuccess: setCategoryResult
  });
  const categorySelectMutation = useMutation({
    mutationFn: async (category: EbayCategorySuggestion) => {
      if (category.is_leaf !== true) {
        throw new Error("Select a leaf eBay category before saving.");
      }
      const draft = await ensureDraft();
      const channelData = {
        ...draft.channel_data,
        category_id: category.category_id,
        category_tree_id: category.category_tree_id,
        category_name: categoryLabel(category),
        last_ebay_error: ""
      };
      return updateListingDraft(draft.id, { channel_data: channelData });
    },
    onSuccess: (draft) => {
      setPreviewDraft(draft);
      setCategorySearch(categorySummary(draft));
      setCategoryResult(null);
      queryClient.invalidateQueries({ queryKey: ["item-listing-drafts", item.id] });
    }
  });
  const shippingNoteMutation = useMutation({
    mutationFn: async () => {
      const draft = await ensureDraft();
      return updateListingDraft(draft.id, { est_shipping_note: shippingNoteDraft.trim() });
    },
    onSuccess: (draft) => {
      setPreviewDraft(draft);
      queryClient.invalidateQueries({ queryKey: ["item-listing-drafts", item.id] });
    }
  });

  function handleBlockerAction(key: string) {
    if (key === "price") {
      focusElement("quick-human-evidence-price");
      return;
    }
    if (key === "category") {
      setPreviewOpen(false);
      focusElement("quick-ebay-category-search");
      return;
    }
    if (key === "postage") {
      setPreviewOpen(false);
      focusElement("quick-shipping-note");
      return;
    }
    if (key === "condition") {
      setPreviewOpen(false);
      jumpToItemSection("core-details");
      return;
    }
    if (key === "photos") {
      setPreviewOpen(false);
      jumpToItemSection("photos");
    }
  }

  return (
    <section className="intelligence-panel quick-publish-panel">
      <div className="intelligence-panel-header">
        <div>
          <p className="intelligence-kicker">Quick publish</p>
          <h2>Post to eBay</h2>
          <p>Two taps: preview the exact listing Magpie will send, then confirm the live eBay post. No batch or background posting.</p>
        </div>
        <button className="btn-primary gap-2 whitespace-nowrap" disabled={openPreview.isPending} onClick={() => openPreview.mutate()} type="button">
          <Send className="h-4 w-4" aria-hidden="true" />
          Post to eBay
        </button>
      </div>
      {previewError ? <p className="intelligence-error mt-3">{previewError}</p> : null}
      <p className="mt-3 text-sm text-slate-700">
        Uses the existing eBay draft, stage, and publish pipeline. A ChannelListing is written only after eBay returns a live listing ID.
      </p>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <EbayCategoryMappingControl
          categoryResult={categoryResult}
          currentDraft={currentDraft}
          error={categorySearchMutation.error}
          onSearch={() => categorySearchMutation.mutate()}
          onSearchChange={setCategorySearch}
          onSelect={(category) => categorySelectMutation.mutate(category)}
          pending={categorySearchMutation.isPending}
          search={categorySearch}
          selectError={categorySelectMutation.error}
          selecting={categorySelectMutation.isPending}
        />
        <div className="rounded border border-slate-300 bg-white p-3">
          <h3 className="text-base font-semibold text-slate-950">eBay postage / pickup</h3>
          <p className="mt-1 text-sm text-slate-700">Save the note Magpie will carry into the listing draft. A typed but unsaved what-if note does not clear the preview gate.</p>
          <label className="label mt-3 text-slate-950">
            <span>Postage / pickup note</span>
            <input
              className="field"
              id="quick-shipping-note"
              placeholder="e.g. Tracked postage or local pickup"
              value={shippingNoteDraft}
              onChange={(event) => setShippingNoteDraft(event.target.value)}
            />
          </label>
          <button className="btn-secondary mt-3 gap-2" disabled={!shippingNoteDraft.trim() || shippingNoteMutation.isPending} onClick={() => shippingNoteMutation.mutate()} type="button">
            Save postage / pickup
          </button>
          {shippingNoteMutation.error ? <p className="mt-2 text-sm font-semibold text-rose-700">{errorText(shippingNoteMutation.error)}</p> : null}
        </div>
      </div>

      {previewOpen ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/70 p-3 sm:items-center sm:p-6" role="dialog" aria-modal="true" aria-label="eBay quick publish preview">
          <div className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded border border-slate-300 bg-white p-4 text-slate-950 shadow-2xl sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-4">
              <div>
                <p className="intelligence-kicker">Tap 1 preview</p>
                <h3 className="text-2xl font-semibold">eBay live listing preview</h3>
                <p className="mt-1 text-sm text-slate-700">This is the confirmation gate. The post button stays disabled until every blocker is clear.</p>
              </div>
              <button className="btn-secondary gap-2 whitespace-nowrap" onClick={() => setPreviewOpen(false)} type="button">
                <X className="h-4 w-4" aria-hidden="true" />
                Close
              </button>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
              <div className="grid gap-3">
                <PreviewRow label="Title" value={currentDraft?.title || item.title || "[title not set]"} />
                <PreviewRow label="Photos" value={`${currentDraft?.photo_ids.length || item.photos.length} selected display photo${(currentDraft?.photo_ids.length || item.photos.length) === 1 ? "" : "s"}`} />
                <PreviewRow label="Price" value={priceChoice.status === "ready" ? `${item.currency} ${priceChoice.value}` : "[price not set]"} note={`Source: ${priceChoice.label}`} />
                <PreviewRow label="Postage / pickup" value={currentDraft?.est_shipping_note || fallbackShippingNote(item) || "[postage or pickup not set]"} />
                <PreviewRow label="Condition" value={conditionLabel(item.condition)} />
                <PreviewRow label="Category mapping" value={categorySummary(currentDraft)} />
                <PreviewRow label="Description" value={copyPack.data?.sections.description || stripHtml(currentDraft?.description_html || "[description not set]")} large />
              </div>

              <div className="grid gap-4">
                <div className="rounded border border-slate-300 bg-slate-50 p-3">
                  <h4 className="font-semibold text-slate-950">Human-picked evidence price</h4>
                  <p className="mt-1 text-sm text-slate-700">Optional. Use only when you have deliberately chosen an evidence figure. This does not create or persist evidence.</p>
                  <label className="label mt-3 text-slate-950">
                    <span>Evidence price</span>
                    <input className="field" id="quick-human-evidence-price" inputMode="decimal" placeholder="e.g. 125.00" value={humanEvidencePrice} onChange={(event) => setHumanEvidencePrice(event.target.value)} />
                  </label>
                  <label className="label mt-3 text-slate-950">
                    <span>Source label</span>
                    <input className="field" placeholder="e.g. approved comp" value={humanEvidenceLabel} onChange={(event) => setHumanEvidenceLabel(event.target.value)} />
                  </label>
                </div>

                <div className="rounded border border-slate-300 bg-white p-3">
                  <h4 className="font-semibold text-slate-950">Readiness blockers</h4>
                  {blockers.length > 0 ? (
                    <ul className="mt-3 grid gap-2">
                      {blockers.map((blocker) => (
                        <li key={blocker.key} className="rounded border border-rose-300 bg-rose-50 p-3 text-sm text-rose-950">
                          <strong>{blocker.label}</strong>
                          <p>{blocker.detail}</p>
                          {blocker.key === "ebay" ? (
                            <Link className="mt-2 inline-flex font-semibold underline" to="/settings">Reconnect eBay</Link>
                          ) : (
                            <button className="mt-2 inline-flex font-semibold underline" onClick={() => handleBlockerAction(blocker.key)} type="button">{blocker.actionLabel}</button>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 rounded border border-emerald-300 bg-emerald-50 p-3 text-sm font-semibold text-emerald-900">Ready to post live to eBay.</p>
                  )}
                </div>

                {publish.error ? (
                  <p className="rounded border border-rose-300 bg-rose-50 p-3 text-sm font-semibold text-rose-950">
                    {publish.error instanceof Error ? publish.error.message : "eBay publish failed."} If this looks like a subscription or plan gate, use the draft path and resolve the eBay account issue before retrying.
                  </p>
                ) : null}
                {publishResult ? (
                  <a className="rounded border border-emerald-300 bg-emerald-50 p-3 text-sm font-semibold text-emerald-900 underline" href={publishResult.url} rel="noreferrer" target="_blank">
                    Live eBay listing {publishResult.listingId} <ExternalLink className="inline h-4 w-4" aria-hidden="true" />
                  </a>
                ) : null}

                <button className="btn-primary gap-2" disabled={blockers.length > 0 || publish.isPending || !currentDraft} onClick={() => publish.mutate()} type="button">
                  <Send className="h-4 w-4" aria-hidden="true" />
                  Post live to eBay
                </button>
                <p className="text-xs font-semibold text-slate-700">No zero-tap path: opening this preview never publishes. Live posting only happens from the button above.</p>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export function chooseQuickPublishPrice(
  item: InventoryItemDetail,
  draft: ListingDraft | null,
  humanEvidencePrice = "",
  humanEvidenceLabel = ""
): PriceChoice {
  const evidence = normalizeMoney(humanEvidencePrice);
  if (evidence) {
    return {
      status: "ready",
      value: evidence,
      label: humanEvidenceLabel.trim() || "human-picked evidence figure",
      basis: "human_picked_evidence"
    };
  }
  if (item.target_price) {
    return {
      status: "ready",
      value: normalizeMoney(item.target_price) ?? item.target_price,
      label: "item asking price",
      basis: "item_asking_or_listed_price"
    };
  }
  if (draft?.price && !hasGeneratedPriceSource(draft)) {
    return {
      status: "ready",
      value: normalizeMoney(draft.price) ?? draft.price,
      label: "listing draft price",
      basis: "item_asking_or_listed_price"
    };
  }
  return {
    status: "missing",
    label: draft?.price ? "generated draft price ignored" : "missing",
    basis: "missing"
  };
}

export function quickPublishBlockers(
  item: InventoryItemDetail,
  draft: ListingDraft | null,
  ebayStatus: EbayStatus | undefined,
  ebayStatusLoading: boolean,
  priceChoice: PriceChoice
): Blocker[] {
  const blockers: Blocker[] = [];
  if (priceChoice.status !== "ready") {
    blockers.push({
      key: "price",
      label: "Price source required",
      detail: "Set the item's asking price, manually edit a draft price, or enter a human-picked evidence price in this preview.",
      actionLabel: "Enter evidence price"
    });
  }
  const photoCount = draft?.photo_ids.length || item.photos.length;
  if (photoCount < 1) {
    blockers.push({
      key: "photos",
      label: "At least one photo required",
      detail: "Add an own photo before posting live.",
      actionLabel: "Add photos"
    });
  }
  if (!draft?.est_shipping_note && !fallbackShippingNote(item)) {
    blockers.push({
      key: "postage",
      label: "Postage or pickup required",
      detail: "Set a postage, packaging, or pickup note so the listing is not ambiguous.",
      actionLabel: "Set postage / pickup"
    });
  }
  if (!item.condition || item.condition === "ungraded") {
    blockers.push({
      key: "condition",
      label: "Condition required",
      detail: "Choose a condition before posting live.",
      actionLabel: "Set condition"
    });
  }
  if (!draft?.channel_data?.category_id) {
    blockers.push({
      key: "category",
      label: "eBay category required",
      detail: "Select and save the eBay category mapping before posting live.",
      actionLabel: "Set eBay category"
    });
  }
  if (ebayStatusLoading || !ebayStatus?.connected) {
    blockers.push({
      key: "ebay",
      label: "eBay connection required",
      detail: ebayStatusLoading ? "Magpie is checking the eBay connection." : "Reconnect eBay before posting.",
      actionLabel: "Reconnect eBay"
    });
  }
  return blockers;
}

function EbayCategoryMappingControl({
  categoryResult,
  currentDraft,
  error,
  onSearch,
  onSearchChange,
  onSelect,
  pending,
  search,
  selectError,
  selecting
}: {
  categoryResult: EbayCategorySuggestionsResponse | null;
  currentDraft: ListingDraft | null;
  error: unknown;
  onSearch: () => void;
  onSearchChange: (value: string) => void;
  onSelect: (category: EbayCategorySuggestion) => void;
  pending: boolean;
  search: string;
  selectError: unknown;
  selecting: boolean;
}) {
  const selected = categorySummary(currentDraft);
  return (
    <div className="rounded border border-slate-300 bg-white p-3">
      <h3 className="text-base font-semibold text-slate-950">eBay category mapping</h3>
      <p className="mt-1 text-sm text-slate-700">Search eBay categories and choose the leaf category yourself. Magpie never silently applies a category.</p>
      <p className="mt-2 rounded border border-slate-200 bg-slate-50 p-2 text-sm font-semibold text-slate-950">
        Current: {selected}
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="label min-w-56 flex-1 text-slate-950">
          <span>eBay category</span>
          <input
            className="field"
            id="quick-ebay-category-search"
            placeholder="Search eBay category"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </label>
        <button className="btn-secondary gap-2" disabled={!search.trim() || pending} onClick={onSearch} type="button">
          Search
        </button>
      </div>
      {categoryResult?.supported === false ? <p className="mt-2 text-sm font-semibold text-amber-700">{categoryResult.detail}</p> : null}
      {categoryResult?.suggestions.length ? (
        <div className="mt-3 grid gap-2">
          {categoryResult.suggestions.map((category) => (
            <button
              aria-label={`Select eBay category ${categoryLabel(category)} ${category.category_id}`}
              className="row-link w-full items-start"
              disabled={category.is_leaf !== true || selecting}
              key={category.category_id}
              onClick={() => onSelect(category)}
              type="button"
            >
              <span className="min-w-0">
                <span className="block font-semibold text-slate-950">{categoryLabel(category)}</span>
                <span className="mt-1 block text-xs text-slate-700">{categoryPath(category)}</span>
              </span>
              <span className="shrink-0 text-xs font-semibold text-slate-700">ID {category.category_id}</span>
            </button>
          ))}
        </div>
      ) : null}
      {error ? <p className="mt-2 text-sm font-semibold text-rose-700">{errorText(error)}</p> : null}
      {selectError ? <p className="mt-2 text-sm font-semibold text-rose-700">{errorText(selectError)}</p> : null}
    </div>
  );
}

function PreviewRow({ label, value, note, large = false }: { label: string; value: string; note?: string; large?: boolean }) {
  return (
    <article className="rounded border border-slate-300 bg-white p-3">
      <p className="text-xs font-semibold uppercase text-slate-700">{label}</p>
      <p className={large ? "mt-2 whitespace-pre-wrap break-words text-sm text-slate-950" : "mt-1 break-words text-base font-semibold text-slate-950"}>{value}</p>
      {note ? <p className="mt-1 text-xs font-semibold text-slate-700">{note}</p> : null}
    </article>
  );
}

function fallbackShippingNote(item: InventoryItemDetail) {
  const parts = [];
  if (item.est_outbound_shipping) {
    parts.push(`Postage estimate ${item.currency} ${item.est_outbound_shipping}`);
  }
  if (item.est_packaging_cost) {
    parts.push(`Packaging estimate ${item.currency} ${item.est_packaging_cost}`);
  }
  return parts.join(" - ");
}

function hasGeneratedPriceSource(draft: ListingDraft) {
  const source = draft.generated_meta?.price_source;
  return Boolean(source && typeof source === "object");
}

function normalizeMoney(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return "";
  }
  return numeric.toFixed(2);
}

function categorySummary(draft: ListingDraft | null) {
  if (!draft) {
    return "[category mapping not set]";
  }
  const name = stringValue(draft.channel_data?.category_name);
  const id = stringValue(draft.channel_data?.category_id);
  if (name && id) {
    return `${name} (${id})`;
  }
  return name || id || "[category mapping not set]";
}

function categoryLabel(category: EbayCategorySuggestion) {
  return category.category_name || category.name || "-";
}

function categoryPath(category: EbayCategorySuggestion) {
  const path = category.category_path?.filter(Boolean) ?? [];
  return path.length ? path.join(" > ") : categoryLabel(category);
}

function conditionLabel(condition: string) {
  return condition && condition !== "ungraded" ? condition.replace(/_/g, " ") : "[condition not set]";
}

function stripHtml(value: string) {
  return value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function textToHtml(value: string) {
  return value
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${escapeHtml(paragraph.trim()).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : "";
}

function ebayListingUrl(listingId: string) {
  return `https://www.ebay.com.au/itm/${encodeURIComponent(listingId)}`;
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : error ? "Request failed." : "";
}

function focusElement(id: string) {
  window.setTimeout(() => {
    document.getElementById(id)?.focus();
  }, 0);
}

function jumpToItemSection(sectionId: string) {
  window.location.hash = sectionId;
  focusElement(sectionId);
}
