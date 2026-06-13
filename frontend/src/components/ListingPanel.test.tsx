import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { ListingPanel } from "./ListingPanel";
import type { InventoryItemDetail, ListingDraft } from "../types";

const longTitle = "x".repeat(81);

const mocks = vi.hoisted(() => ({
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
  updated_at: ""
} satisfies InventoryItemDetail;

beforeEach(() => {
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

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ListingPanel item={item} />
    </QueryClientProvider>
  );
}

test("ListingPanel flags titles over 80 characters and unready exports", async () => {
  renderPanel();

  await screen.findByDisplayValue(longTitle);

  expect(screen.getByText("81/80")).toHaveClass("text-rose-300");
  expect(screen.getByText("Unready export")).toBeInTheDocument();
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

test("ListingPanel groups readiness checks by level", async () => {
  renderPanel();

  expect(await screen.findByText("Fails (1)")).toBeInTheDocument();
  expect(screen.getByText("Warnings (1)")).toBeInTheDocument();
  expect(screen.getByText("Passes (1)")).toBeInTheDocument();
  expect(screen.getByText("Title is required.")).toBeInTheDocument();
});

test("ListingPanel requires an override reason before staging with missing aspects", async () => {
  const user = userEvent.setup();
  mocks.listItemListingDrafts.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{
      ...mocks.draft,
      channel_data: {
        category_id: "260",
        category_tree_id: "15",
        category_name: "Stamps",
        condition_id: "3000",
        merchant_location_key: "loc-1",
        payment_policy_id: "payment-1",
        fulfillment_policy_id: "fulfillment-1",
        return_policy_id: "return-1"
      }
    }]
  });
  mocks.getListingAspectCheck.mockResolvedValue({
    satisfied_required: ["Brand"],
    missing_required: ["Country/Region of Manufacture"],
    optional_known: [],
    unmapped_specifics: [],
    aspects: [],
    fetched_at: null
  });
  renderPanel();

  const stageButton = await screen.findByRole("button", { name: "Stage offer" });
  expect(stageButton).toBeDisabled();

  await user.click(screen.getByLabelText("Override and stage anyway"));
  expect(stageButton).toBeDisabled();

  await user.type(screen.getByLabelText("Override reason"), "Known stamp provenance");
  await user.click(stageButton);

  await waitFor(() => expect(mocks.stageListingDraft).toHaveBeenCalledWith("draft-1", {
    override_missing_aspects: true,
    override_reason: "Known stamp provenance"
  }));
});

test("ListingPanel renders category labels, paths, and leaf safety", async () => {
  const user = userEvent.setup();
  mocks.listItemListingDrafts.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{
      ...mocks.draft,
      channel_data: {
        category_id: "260",
        category_tree_id: "15",
        category_name: "Stamps",
        condition_id: "3000",
        merchant_location_key: "loc-1",
        payment_policy_id: "payment-1",
        fulfillment_policy_id: "fulfillment-1",
        return_policy_id: "return-1"
      }
    }]
  });
  mocks.getEbayCategorySuggestions.mockResolvedValue({
    supported: true,
    suggestions: [
      {
        category_id: "260",
        category_tree_id: "15",
        category_name: "Stamps",
        name: "Stamps",
        category_path: ["Stamps"],
        is_leaf: false,
        child_count: 3,
        source: "fake"
      },
      {
        category_id: "105848",
        category_tree_id: "15",
        category_name: "Australian Stamps",
        name: "Australian Stamps",
        category_path: ["Stamps", "Australia", "Australian Stamps"],
        is_leaf: true,
        child_count: 0,
        source: "fake"
      }
    ]
  });
  renderPanel();

  await user.type(await screen.findByLabelText("Category search"), "postage stamps");
  await user.click(screen.getByRole("button", { name: "Search" }));

  expect(await screen.findByText("Australian Stamps")).toBeInTheDocument();
  expect(screen.getByText("Stamps > Australia > Australian Stamps")).toBeInTheDocument();
  expect(screen.getByText("ID 105848")).toBeInTheDocument();
  expect(screen.getByText("Leaf category")).toBeInTheDocument();
  expect(screen.getByText("Not a leaf")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /ID 260/i })).toBeDisabled();

  await user.click(screen.getByRole("button", { name: /Australian Stamps/i }));

  expect(screen.getByLabelText("Manual category ID")).toHaveValue("105848");
  expect(screen.getByLabelText("Tree ID")).toHaveValue("15");
  expect(screen.getByLabelText("Category name")).toHaveValue("Australian Stamps");
  expect(await screen.findByText("Selected category")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /ID 105848/i })).not.toBeInTheDocument();
  await waitFor(() => expect(mocks.updateListingDraft).toHaveBeenCalledWith("draft-1", {
    channel_data: expect.objectContaining({
      category_id: "105848",
      category_tree_id: "15",
      category_name: "Australian Stamps"
    })
  }));
});

test("ListingPanel disables staging when category pre-flight has a hard error", async () => {
  mocks.listItemListingDrafts.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{
      ...mocks.draft,
      channel_data: {
        category_id: "260",
        category_tree_id: "15",
        category_name: "Stamps",
        condition_id: "3000",
        merchant_location_key: "loc-1",
        payment_policy_id: "payment-1",
        fulfillment_policy_id: "fulfillment-1",
        return_policy_id: "return-1"
      }
    }]
  });
  mocks.getListingAspectCheck.mockRejectedValue(new Error("The specified category ID must be a leaf category."));
  renderPanel();

  expect(await screen.findByText("The specified category ID must be a leaf category.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Stage offer" })).toBeDisabled();
  expect(screen.getByText("Resolve the category/aspects pre-flight error before staging.")).toBeInTheDocument();
});

test("ListingPanel enables publish only after exact SKU confirmation", async () => {
  const user = userEvent.setup();
  mocks.listItemListingDrafts.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{
      ...mocks.draft,
      status: "staged",
      channel_data: {
        offer_id: "offer-1",
        staged_at: "2026-06-13T00:00:00Z",
        category_id: "260"
      }
    }]
  });
  renderPanel();

  await user.click(await screen.findByRole("button", { name: "Review & publish" }));
  await screen.findByText("This will create a live eBay listing");
  await user.click(screen.getByRole("button", { name: "Publish" }));

  const publishButtons = screen.getAllByRole("button", { name: "Publish" });
  const confirmButton = publishButtons[publishButtons.length - 1];
  expect(confirmButton).toBeDisabled();

  await user.type(screen.getByLabelText("SKU confirmation"), "PH-00001");
  expect(confirmButton).toBeEnabled();
  await user.click(confirmButton);

  await waitFor(() => expect(mocks.publishListingDraft).toHaveBeenCalledWith("draft-1", "PH-00001"));
});
