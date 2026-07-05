import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import type { MockInstance } from "vitest";

import { CopyPackPanel } from "./CopyPackPanel";
import type { CopyPack, InventoryItemDetail } from "../types";

vi.mock("../api/listing", () => ({
  getItemCopyPack: vi.fn()
}));

vi.mock("../api/items", () => ({
  downloadItemPhotoZip: vi.fn()
}));

const listingApi = await import("../api/listing");
const itemApi = await import("../api/items");
let writeTextSpy: MockInstance<(data: string) => Promise<void>>;

const item: InventoryItemDetail = {
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
  updated_at: "2026-06-01T00:00:00Z"
};

const pack: CopyPack = {
  item: "item-1",
  channel: "facebook_marketplace",
  channel_label: "Facebook Marketplace",
  sections: {
    title: "Kangaroo 2d red stamp",
    description: "Kangaroo 2d red stamp\nCategory: Stamps\nCondition: Good\nDetails: [details not set]",
    price_line: "Price: [price not set - choose an item asking price or human-picked evidence]",
    postage_pickup_line: "Pickup / postage: [postage or pickup not set]"
  },
  whole_ad: "Kangaroo 2d red stamp\n\nPrice: [price not set - choose an item asking price or human-picked evidence]",
  price_source: {
    basis: "missing",
    label: "missing",
    hint: "Set an asking/listed price or pick an evidence figure before copying a price line."
  },
  rendered_at: "2026-06-01T00:00:00Z"
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listingApi.getItemCopyPack).mockResolvedValue(pack);
  vi.mocked(itemApi.downloadItemPhotoZip).mockResolvedValue(new Blob(["zip"]));
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: async () => undefined }
  });
});

test("CopyPackPanel renders visible gaps and copies whole ad", async () => {
  const user = userEvent.setup();
  writeTextSpy = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
  renderPanel();

  expect(await screen.findByText(/Price: \[price not set/)).toBeInTheDocument();
  expect(screen.getByText(/Details: \[details not set\]/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /copy whole ad/i }));

  expect(writeTextSpy).toHaveBeenCalledWith(pack.whole_ad);
  expect(await screen.findByText("Whole ad copied.")).toBeInTheDocument();
});

test("CopyPackPanel sends human-picked evidence price without persisting it", async () => {
  const user = userEvent.setup();
  renderPanel();

  await screen.findByText(/Price:/);
  await user.clear(screen.getByLabelText("Human evidence price"));
  await user.type(screen.getByLabelText("Human evidence price"), "123.45");

  await waitFor(() => {
    expect(vi.mocked(listingApi.getItemCopyPack)).toHaveBeenLastCalledWith("item-1", expect.objectContaining({ evidence_price: "123.45" }));
  });
});

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  render(
    <QueryClientProvider client={client}>
      <CopyPackPanel item={item} />
    </QueryClientProvider>
  );
}
