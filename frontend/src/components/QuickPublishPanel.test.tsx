import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { QuickPublishPanel, chooseQuickPublishPrice } from "./QuickPublishPanel";
import type { InventoryItemDetail, ListingDraft } from "../types";

const mocks = vi.hoisted(() => ({
  createItemListingDraft: vi.fn(),
  getEbayCategorySuggestions: vi.fn(),
  getEbayStatus: vi.fn(),
  getItemCopyPack: vi.fn(),
  listItemListingDrafts: vi.fn(),
  publishListingDraft: vi.fn(),
  stageListingDraft: vi.fn(),
  updateListingDraft: vi.fn()
}));

vi.mock("../api/listing", () => ({
  createItemListingDraft: (...args: unknown[]) => mocks.createItemListingDraft(...args),
  getItemCopyPack: (...args: unknown[]) => mocks.getItemCopyPack(...args),
  listItemListingDrafts: (...args: unknown[]) => mocks.listItemListingDrafts(...args),
  publishListingDraft: (...args: unknown[]) => mocks.publishListingDraft(...args),
  stageListingDraft: (...args: unknown[]) => mocks.stageListingDraft(...args),
  updateListingDraft: (...args: unknown[]) => mocks.updateListingDraft(...args)
}));

vi.mock("../api/ebay", () => ({
  getEbayCategorySuggestions: (...args: unknown[]) => mocks.getEbayCategorySuggestions(...args),
  getEbayStatus: (...args: unknown[]) => mocks.getEbayStatus(...args)
}));

const baseItem: InventoryItemDetail = {
  id: "item-1",
  sku: "STM-00001",
  title: "Kangaroo 2d red stamp",
  status: "ready_to_list",
  condition: "good",
  category: "cat-1",
  category_name: "Stamps",
  lot: null,
  source: null,
  source_name: null,
  disposition: "for_sale",
  scrapped_at: null,
  quantity_total: 1,
  quantity_sold: 0,
  quantity_remaining: 1,
  estimated_value: "100.00",
  currency: "AUD",
  main_thumb_url: null,
  created_at: "2026-06-01T00:00:00Z",
  location: null,
  acquisition: null,
  acquisition_cost: "20.00",
  refurb_cost: null,
  inbound_shipping_cost: null,
  est_outbound_shipping: "10.00",
  est_packaging_cost: null,
  min_price: null,
  target_price: null,
  notes: "",
  attributes: {},
  owner: null,
  photos: [{
    id: "photo-1",
    item: "item-1",
    role: "other",
    is_main: true,
    order_index: 0,
    original_path: "original.jpg",
    processed_path: "processed.jpg",
    thumb_path: "thumb.jpg",
    original_url: "/media/original.jpg",
    processed_url: "/media/processed.jpg",
    thumb_url: "/media/thumb.jpg",
    width: 1200,
    height: 900,
    bytes_original: 10,
    exif_stripped: true,
    quality_score: null,
    fixup_status: "none",
    active_derivative: null,
    active_derivative_detail: null,
    pending_derivative: null,
    derivatives: []
  }],
  comps_count: 0,
  current_valuation: null,
  effective_source: null,
  updated_at: "2026-06-01T00:00:00Z"
};

const baseDraft: ListingDraft = {
  id: "draft-1",
  item: "item-1",
  status: "ready",
  channel: "ebay_au",
  channel_data: {
    category_id: "105848",
    category_name: "Australian Stamps",
    condition_id: "3000",
    merchant_location_key: "loc-1",
    payment_policy_id: "payment-1",
    fulfillment_policy_id: "fulfillment-1",
    return_policy_id: "return-1"
  },
  title: "Kangaroo 2d red stamp",
  subtitle: "",
  description_html: "<p>Clean stamp listing.</p>",
  listing_format: "fixed",
  price: "95.00",
  currency: "AUD",
  quantity: 1,
  est_shipping_note: "Tracked postage available.",
  item_specifics: [],
  photo_ids: ["photo-1"],
  include_sku_footer: false,
  boilerplate: null,
  title_edited: false,
  description_edited: false,
  generated_meta: {},
  exported_at: null,
  readiness_summary: { fail_count: 0, warn_count: 0, pass_count: 0 },
  created_at: "",
  updated_at: ""
};

const categorySuggestion = {
  category_id: "105848",
  category_tree_id: "15",
  category_name: "Australian Stamps",
  name: "Australian Stamps",
  category_path: ["Stamps", "Australia", "Australian Stamps"],
  is_leaf: true,
  child_count: 0
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getEbayStatus.mockResolvedValue({
    configured: true,
    environment: "production",
    connected: true,
    requires_reconsent: false,
    missing_scopes: [],
    ebay_username: "seller",
    scopes: [],
    access_token_expires_at: null,
    refresh_token_expires_at: null,
    last_refresh_error: "",
    snapshot: { opted_in: true, policy_counts: { payment: 1, fulfillment: 1, return: 1 }, fetched_at: null }
  });
  mocks.getEbayCategorySuggestions.mockResolvedValue({
    supported: true,
    suggestions: [categorySuggestion]
  });
  mocks.listItemListingDrafts.mockResolvedValue({ count: 1, next: null, previous: null, results: [baseDraft] });
  mocks.createItemListingDraft.mockResolvedValue(baseDraft);
  mocks.getItemCopyPack.mockResolvedValue({
    item: "item-1",
    channel: "ebay",
    channel_label: "eBay",
    sections: {
      title: "Kangaroo 2d red stamp",
      description: "eBay template description\nCondition: good",
      price_line: "Price: A$95.00",
      postage_pickup_line: "Postage estimate A$10.00"
    },
    whole_ad: "Kangaroo 2d red stamp",
    price_source: {
      basis: "item_asking_or_listed_price",
      label: "listing draft price",
      hint: "Price copied from the item's listing draft."
    },
    rendered_at: ""
  });
  mocks.updateListingDraft.mockResolvedValue(baseDraft);
  mocks.stageListingDraft.mockResolvedValue({ ...baseDraft, status: "staged", channel_data: { ...baseDraft.channel_data, offer_id: "offer-1" } });
  mocks.publishListingDraft.mockResolvedValue({ ...baseDraft, status: "published", channel_data: { ...baseDraft.channel_data, listing_id: "1234567890" } });
});

test("QuickPublishPanel previews a ready listing and only publishes after explicit confirmation", async () => {
  const user = userEvent.setup();
  renderPanel();

  await user.click(await screen.findByRole("button", { name: "Post to eBay" }));

  expect(await screen.findByText("eBay live listing preview")).toBeInTheDocument();
  expect(screen.getByText("Kangaroo 2d red stamp")).toBeInTheDocument();
  expect(await screen.findByText(/eBay template description/)).toBeInTheDocument();
  expect(screen.getByText("AUD 95.00")).toBeInTheDocument();
  expect(screen.getByText("Source: listing draft price")).toBeInTheDocument();
  expect(screen.getByText("1 selected display photo")).toBeInTheDocument();
  expect(screen.getByText("Ready to post live to eBay.")).toBeInTheDocument();
  expect(mocks.publishListingDraft).not.toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: "Post live to eBay" }));

  await waitFor(() => expect(mocks.updateListingDraft).toHaveBeenCalledWith("draft-1", expect.objectContaining({
    description_html: "<p>eBay template description<br>Condition: good</p>",
    price: "95.00"
  })));
  expect(mocks.stageListingDraft).toHaveBeenCalledWith("draft-1");
  expect(mocks.publishListingDraft).toHaveBeenCalledWith("draft-1", "STM-00001");
  expect(await screen.findByText(/Live eBay listing 1234567890/)).toBeInTheDocument();
});

test("QuickPublishPanel blocks missing price photo postage condition and eBay connection", async () => {
  const user = userEvent.setup();
  mocks.getEbayStatus.mockResolvedValue({
    configured: true,
    environment: "production",
    connected: false,
    requires_reconsent: false,
    missing_scopes: [],
    ebay_username: "",
    scopes: [],
    access_token_expires_at: null,
    refresh_token_expires_at: null,
    last_refresh_error: "",
    snapshot: { opted_in: true, policy_counts: { payment: 1, fulfillment: 1, return: 1 }, fetched_at: null }
  });
  mocks.listItemListingDrafts.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{ ...baseDraft, price: null, est_shipping_note: "", photo_ids: [], generated_meta: { price_source: { value: "88.00" } } }]
  });
  renderPanel({ ...baseItem, condition: "ungraded", photos: [], est_outbound_shipping: null });

  await user.click(await screen.findByRole("button", { name: "Post to eBay" }));

  expect(await screen.findByText("Price source required")).toBeInTheDocument();
  expect(screen.getByText("At least one photo required")).toBeInTheDocument();
  expect(screen.getByText("Postage or pickup required")).toBeInTheDocument();
  expect(screen.getByText("Condition required")).toBeInTheDocument();
  expect(screen.getByText("eBay connection required")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Post live to eBay" })).toBeDisabled();
  expect(mocks.publishListingDraft).not.toHaveBeenCalled();
});

test("QuickPublishPanel blocks missing category and links to the category mapping control", async () => {
  const user = userEvent.setup();
  const missingCategoryDraft = {
    ...baseDraft,
    channel_data: {
      ...baseDraft.channel_data,
      category_id: "",
      category_name: "",
      category_tree_id: ""
    }
  };
  mocks.listItemListingDrafts.mockResolvedValue({ count: 1, next: null, previous: null, results: [missingCategoryDraft] });
  renderPanel();

  await user.click(await screen.findByRole("button", { name: "Post to eBay" }));

  expect(await screen.findByText("eBay category required")).toBeInTheDocument();
  expect(screen.getByText("[category mapping not set]")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Post live to eBay" })).toBeDisabled();

  await user.click(screen.getByRole("button", { name: "Set eBay category" }));

  await waitFor(() => expect(screen.queryByText("eBay live listing preview")).not.toBeInTheDocument());
  await waitFor(() => expect(screen.getByLabelText("eBay category")).toHaveFocus());
});

test("QuickPublishPanel persists a selected category and previews it before posting", async () => {
  const user = userEvent.setup();
  const missingCategoryDraft = {
    ...baseDraft,
    channel_data: {
      ...baseDraft.channel_data,
      category_id: "",
      category_name: "",
      category_tree_id: ""
    }
  };
  mocks.listItemListingDrafts.mockResolvedValue({ count: 1, next: null, previous: null, results: [missingCategoryDraft] });
  mocks.updateListingDraft.mockImplementation(async (_id: string, payload: Partial<ListingDraft>) => ({
    ...missingCategoryDraft,
    ...payload,
    channel_data: {
      ...missingCategoryDraft.channel_data,
      ...(payload.channel_data ?? {})
    }
  }));
  renderPanel();

  await user.type(await screen.findByLabelText("eBay category"), "Australian stamps");
  await user.click(screen.getByRole("button", { name: "Search" }));
  await user.click(await screen.findByRole("button", { name: "Select eBay category Australian Stamps 105848" }));

  await waitFor(() => expect(mocks.updateListingDraft).toHaveBeenCalledWith("draft-1", expect.objectContaining({
    channel_data: expect.objectContaining({
      category_id: "105848",
      category_name: "Australian Stamps",
      category_tree_id: "15"
    })
  })));
  expect(await screen.findByText("Current: Australian Stamps (105848)")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Post to eBay" }));

  expect(await screen.findByText("eBay live listing preview")).toBeInTheDocument();
  expect(screen.getByText("Australian Stamps (105848)")).toBeInTheDocument();
  expect(screen.queryByText("eBay category required")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Post live to eBay" })).not.toBeDisabled();
});

test("QuickPublishPanel ignores generated draft prices but accepts human-picked evidence", async () => {
  const user = userEvent.setup();
  mocks.listItemListingDrafts.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{ ...baseDraft, generated_meta: { price_source: { valuation_report_id: "report-1", value: "88.00" } } }]
  });
  renderPanel();

  await user.click(await screen.findByRole("button", { name: "Post to eBay" }));
  expect(await screen.findByText("Source: generated draft price ignored")).toBeInTheDocument();
  expect(screen.getByText("Price source required")).toBeInTheDocument();

  await user.type(screen.getByLabelText("Evidence price"), "123.45");
  await user.type(screen.getByLabelText("Source label"), "approved comp");

  expect(screen.getByText("AUD 123.45")).toBeInTheDocument();
  expect(screen.getByText("Source: approved comp")).toBeInTheDocument();
  expect(screen.queryByText("Price source required")).not.toBeInTheDocument();
});

test("chooseQuickPublishPrice treats target price as item asking price", () => {
  const choice = chooseQuickPublishPrice({ ...baseItem, target_price: "77" }, { ...baseDraft, price: null }, "", "");

  expect(choice).toEqual({
    status: "ready",
    value: "77.00",
    label: "item asking price",
    basis: "item_asking_or_listed_price"
  });
});

function renderPanel(item: InventoryItemDetail = baseItem) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <QuickPublishPanel item={item} />
      </QueryClientProvider>
    </MemoryRouter>
  );
}
