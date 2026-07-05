import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import { ChannelListingsPage } from "./ChannelListingsPage";
import type { ChannelListingBoard, PaginatedResponse, InventoryItemList } from "../../types";

vi.mock("../../api/listing", () => ({
  createChannelListing: vi.fn(),
  getChannelListingBoard: vi.fn(),
  markChannelListingEnded: vi.fn(),
  seedEbayChannelListings: vi.fn()
}));

vi.mock("../../api/items", () => ({
  listItems: vi.fn()
}));

const listingApi = await import("../../api/listing");
const itemApi = await import("../../api/items");

const board: ChannelListingBoard = {
  groups: [
    {
      channel: "facebook_marketplace",
      channel_label: "Facebook",
      count: 1,
      listings: [
        {
          id: "listing-1",
          item: "item-1",
          item_sku: "STM-00001",
          item_title: "Sold stamp",
          channel: "facebook_marketplace",
          channel_label: "Facebook",
          listed_at: "2026-06-01T00:00:00Z",
          ended_at: null,
          active: true,
          days_listed: 10,
          url: "",
          note: "",
          source_listing_draft: null,
          take_down_state: null,
          created_at: "2026-06-01T00:00:00Z",
          updated_at: "2026-06-01T00:00:00Z"
        }
      ]
    }
  ],
  take_down_checklist: [
    {
      item: "item-1",
      sku: "STM-00001",
      title: "Sold stamp",
      state: "take_down_required",
      message: "Still listed on: Facebook - take them down.",
      quantity_sold: 1,
      quantity_remaining: 0,
      quantity_total: 1,
      active_listings: []
    }
  ],
  partial_quantity: [],
  empty: false
};

board.take_down_checklist[0].active_listings = board.groups[0].listings;

const items: PaginatedResponse<InventoryItemList> = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: "item-1",
      sku: "STM-00001",
      title: "Sold stamp",
      status: "sold",
      condition: "good",
      category: null,
      category_name: null,
      lot: null,
      source: null,
      source_name: null,
      disposition: "for_sale",
      scrapped_at: null,
      quantity_total: 1,
      quantity_sold: 1,
      quantity_remaining: 0,
      estimated_value: null,
      currency: "AUD",
      main_thumb_url: null,
      created_at: "2026-06-01T00:00:00Z"
    }
  ]
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listingApi.getChannelListingBoard).mockResolvedValue(board);
  vi.mocked(listingApi.markChannelListingEnded).mockResolvedValue(board.groups[0].listings[0]);
  vi.mocked(listingApi.createChannelListing).mockResolvedValue(board.groups[0].listings[0]);
  vi.mocked(listingApi.seedEbayChannelListings).mockResolvedValue({ seeded: 0, existing: 0, skipped_ambiguous: 0, skipped_missing_date: 0 });
  vi.mocked(itemApi.listItems).mockResolvedValue(items);
});

test("ChannelListingsPage shows the take-down checklist and ticks rows manually", async () => {
  const user = userEvent.setup();
  renderPage();

  expect(await screen.findByText("Still listed on: Facebook - take them down.")).toBeInTheDocument();
  await user.click(screen.getAllByRole("button", { name: /mark facebook ended/i })[0]);

  expect(listingApi.markChannelListingEnded).toHaveBeenCalledWith("listing-1");
});

test("ChannelListingsPage supports manual listing add", async () => {
  const user = userEvent.setup();
  renderPage();

  await screen.findByRole("heading", { name: "Add a channel listing" });
  await screen.findByRole("option", { name: /STM-00001/ });
  await user.selectOptions(screen.getByLabelText("Item"), "item-1");
  await user.click(screen.getByRole("button", { name: /add listing/i }));

  await waitFor(() => {
    expect(listingApi.createChannelListing).toHaveBeenCalledWith(expect.objectContaining({ item: "item-1", channel: "facebook_marketplace" }));
  });
});

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ChannelListingsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}
