import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { ListingPanel } from "./ListingPanel";
import { ListingWorkflow } from "./ListingWorkflow";
import type { InventoryItemDetail, ListingDraft } from "../types";

const longTitle = "x".repeat(81);

const mocks = vi.hoisted(() => ({
  getListingEditor: vi.fn(),
  getEbayStatus: vi.fn(),
  getEbayCategorySuggestions: vi.fn(),
  getListingAspectCheck: vi.fn(),
  getMerchantLocation: vi.fn(),
  getStagedOfferReview: vi.fn(),
  generateListingDraft: vi.fn(),
  getListingReadiness: vi.fn(),
  listItemListingDrafts: vi.fn(),
  listListingBoilerplates: vi.fn(),
  publishListingDraft: vi.fn(),
  stageListingDraft: vi.fn(),
  updateListingDraft: vi.fn(),
  withdrawListingDraft: vi.fn(),
  draft: {
    id: "draft-1",
    item: "item-1",
    status: "draft",
    channel: "ebay_au",
    channel_data: {},
    title: "x".repeat(81),
    subtitle: "",
    description_html: "<h2>What's included</h2><p>USB cable.</p>",
    listing_format: "fixed",
    price: "99.00",
    currency: "AUD",
    quantity: 1,
    est_shipping_note: "",
    item_specifics: [{ name: "Brand", value: "Samsung" }],
    photo_ids: [],
    include_sku_footer: false,
    boilerplate: "bp-1",
    title_edited: true,
    description_edited: false,
    generated_meta: {},
    exported_at: null,
    readiness_summary: { fail_count: 1, warn_count: 1, pass_count: 8 },
    created_at: "",
    updated_at: ""
  } as ListingDraft
}));

vi.mock("../api/listing", () => ({
  archiveListingDraft: vi.fn(),
  getListingCategoryChildren: vi.fn(),
  getListingEditor: (...args: unknown[]) => mocks.getListingEditor(...args),
  refreshListingMetadata: vi.fn(),
  createItemListingDraft: vi.fn(),
  deleteListingDraft: vi.fn(),
  downloadListingZip: vi.fn(),
  generateListingDraft: (...args: unknown[]) => mocks.generateListingDraft(...args),
  getListingAspectCheck: (...args: unknown[]) => mocks.getListingAspectCheck(...args),
  getListingReadiness: (...args: unknown[]) => mocks.getListingReadiness(...args),
  getStagedOfferReview: (...args: unknown[]) => mocks.getStagedOfferReview(...args),
  listItemListingDrafts: (...args: unknown[]) => mocks.listItemListingDrafts(...args),
  listListingBoilerplates: (...args: unknown[]) => mocks.listListingBoilerplates(...args),
  publishListingDraft: (...args: unknown[]) => mocks.publishListingDraft(...args),
  stageListingDraft: (...args: unknown[]) => mocks.stageListingDraft(...args),
  withdrawListingDraft: (...args: unknown[]) => mocks.withdrawListingDraft(...args),
  updateListingDraft: (...args: unknown[]) => mocks.updateListingDraft(...args)
}));

vi.mock("../api/ebay", () => ({
  createMerchantLocation: vi.fn(),
  getEbayCategorySuggestions: (...args: unknown[]) => mocks.getEbayCategorySuggestions(...args),
  getEbayStatus: (...args: unknown[]) => mocks.getEbayStatus(...args),
  getMerchantLocation: (...args: unknown[]) => mocks.getMerchantLocation(...args)
}));

const item = {
  id: "item-1",
  sku: "PH-00001",
  title: "Phone",
  status: "ready_to_list",
  condition: "good",
  category: "cat-1",
  category_name: "Phones",
  lot: null,
  source: null,
  source_name: null,
  disposition: "for_sale",
  scrapped_at: null,
  quantity_total: 1,
  quantity_sold: 0,
  quantity_remaining: 1,
  estimated_value: null,
  currency: "AUD",
  main_thumb_url: null,
  created_at: "",
  location: null,
  acquisition: null,
  acquisition_cost: null,
  refurb_cost: null,
  inbound_shipping_cost: null,
  est_outbound_shipping: null,
  est_packaging_cost: null,
  min_price: null,
  target_price: null,
  notes: "",
  attributes: {},
  owner: null,
  photos: [],
  comps_count: 0,
  current_valuation: null,
  effective_source: null,
  updated_at: ""
} satisfies InventoryItemDetail;

beforeEach(() => {
  mocks.getListingEditor.mockResolvedValue({ metadata: { category_snapshot: null, category_search: {}, policies: { payment: [], fulfillment: [], return: [] }, locations: [], policies_stale: true, category_stale: true }, sources: {}, price_options: [], checks: [{ key: "title_missing", level: "fail", message: "Title is required.", field: "title" }], price_source: null, read_only: false, staged_local_changes: false });
  mocks.generateListingDraft.mockReset();
  mocks.generateListingDraft.mockResolvedValue({ ...mocks.draft, title_edited: false, title: "Generated title" });
  mocks.getEbayStatus.mockReset();
  mocks.getEbayStatus.mockResolvedValue({
    configured: true,
    environment: "production",
    connected: true,
    ebay_username: "seller",
    scopes: [],
    access_token_expires_at: null,
    refresh_token_expires_at: null,
    last_refresh_error: "",
    snapshot: { opted_in: true, policy_counts: { payment: 1, fulfillment: 1, return: 1 }, fetched_at: null }
  });
  mocks.getListingAspectCheck.mockReset();
  mocks.getListingAspectCheck.mockResolvedValue({
    satisfied_required: ["Brand"],
    missing_required: [],
    optional_known: [],
    unmapped_specifics: [],
    aspects: [],
    fetched_at: null
  });
  mocks.getMerchantLocation.mockReset();
  mocks.getMerchantLocation.mockResolvedValue({ configured: true, location: null });
  mocks.getEbayCategorySuggestions.mockReset();
  mocks.getEbayCategorySuggestions.mockResolvedValue({
    supported: true,
    suggestions: []
  });
  mocks.getStagedOfferReview.mockReset();
  mocks.getStagedOfferReview.mockResolvedValue({
    offer_id: "offer-1",
    sku: "PH-00001",
    title: "x",
    category_id: "260",
    category_name: "Stamps",
    condition: "USED_GOOD",
    price: "99.00",
    currency: "AUD",
    quantity: 1,
    format: "FIXED_PRICE",
    payment_policy_id: "payment-1",
    fulfillment_policy_id: "fulfillment-1",
    return_policy_id: "return-1",
    merchant_location_key: "loc-1",
    photo_count: 1,
    aspect_warnings: []
  });
  mocks.getListingReadiness.mockReset();
  mocks.getListingReadiness.mockResolvedValue([
    { key: "title_missing", level: "fail", message: "Title is required." },
    { key: "no_boilerplate", level: "warn", message: "No boilerplate selected." },
    { key: "description_present", level: "pass", message: "Description is present." }
  ]);
  mocks.listItemListingDrafts.mockReset();
  mocks.listItemListingDrafts.mockResolvedValue({ count: 1, next: null, previous: null, results: [mocks.draft] });
  mocks.listListingBoilerplates.mockReset();
  mocks.listListingBoilerplates.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{ id: "bp-1", name: "Boilerplate", body_html: "<p>Terms</p>", channel: "ebay_au", is_active: true, notes: "", created_at: "", updated_at: "" }]
  });
  mocks.updateListingDraft.mockReset();
  mocks.updateListingDraft.mockResolvedValue(mocks.draft);
  mocks.stageListingDraft.mockReset();
  mocks.stageListingDraft.mockResolvedValue({ ...mocks.draft, status: "staged", channel_data: { offer_id: "offer-1" } });
  mocks.withdrawListingDraft.mockReset();
  mocks.publishListingDraft.mockReset();
  mocks.publishListingDraft.mockResolvedValue({ ...mocks.draft, status: "published", channel_data: { listing_id: "listing-1" } });
});

function renderPanel(legacyPipeline = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      {legacyPipeline ? <LegacyPipeline /> : <ListingPanel item={item} />}
    </QueryClientProvider>
  );
}

function LegacyPipeline() {
  const drafts = useQuery({ queryKey: ["legacy-test-draft"], queryFn: () => mocks.listItemListingDrafts(item.id) });
  const [draft, setDraft] = useState<ListingDraft | null>(null);
  const row = draft ?? drafts.data?.results[0];
  return row ? <ListingWorkflow draft={row} item={item} mode="full" onUpdated={setDraft} beforeReview={() => Promise.resolve(row)} /> : null;
}

test("ListingPanel flags titles over 80 characters and unready exports", async () => {
  renderPanel();

  await screen.findByDisplayValue(longTitle);

  expect(screen.getByText("81/80")).toHaveClass("text-rose-300");
  expect(screen.getByText("Export is not ready to list")).toBeInTheDocument();
});

test("ListingPanel asks before regenerating edited title only", async () => {
  const user = userEvent.setup();
  renderPanel();

  await screen.findByDisplayValue(longTitle);
  await user.click(screen.getByRole("button", { name: "Regenerate specifics" }));

  await waitFor(() => expect(mocks.generateListingDraft).toHaveBeenCalledWith("draft-1", ["specifics"], false));
  expect(screen.queryByText("Overwrite edited title?")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Regenerate title" }));

  expect(screen.getByText("Overwrite edited title?")).toBeInTheDocument();
});

test("ListingPanel names readiness blockers with a field jump", async () => {
  renderPanel();

  expect(await screen.findByText("1 blockers · 0 recommendations")).toBeInTheDocument();
  expect(screen.getByText("Required: Title is required.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Go to field" })).toBeInTheDocument();
});

test("ListingPanel keeps published listing read-only and hides publish gate", async () => {
  mocks.listItemListingDrafts.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{
      ...mocks.draft,
      status: "published",
      channel_data: {
        offer_id: "offer-1",
        listing_id: "listing-1",
        staged_at: "2026-06-13T00:00:00Z",
        category_id: "260"
      }
    }]
  });
  renderPanel(true);

  expect(await screen.findByText("Published listing")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Review & publish" })).not.toBeInTheDocument();
  expect(screen.queryByText("Unpublished offer offer-1")).not.toBeInTheDocument();
  expect(screen.queryByText("Publish live eBay listing")).not.toBeInTheDocument();
  expect(mocks.publishListingDraft).not.toHaveBeenCalled();
});
