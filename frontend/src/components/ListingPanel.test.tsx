import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { ListingPanel } from "./ListingPanel";
import type { InventoryItemDetail, ListingDraft } from "../types";

const longTitle = "x".repeat(81);

const mocks = vi.hoisted(() => ({
  generateListingDraft: vi.fn(),
  getListingReadiness: vi.fn(),
  listItemListingDrafts: vi.fn(),
  listListingBoilerplates: vi.fn(),
  updateListingDraft: vi.fn(),
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
  getListingReadiness: (...args: unknown[]) => mocks.getListingReadiness(...args),
  listItemListingDrafts: (...args: unknown[]) => mocks.listItemListingDrafts(...args),
  listListingBoilerplates: (...args: unknown[]) => mocks.listListingBoilerplates(...args),
  updateListingDraft: (...args: unknown[]) => mocks.updateListingDraft(...args)
}));

vi.mock("../api/items", () => ({
  updateItem: vi.fn()
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
