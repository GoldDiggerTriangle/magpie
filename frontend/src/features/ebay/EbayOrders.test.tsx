import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import { ApiError } from "../../api/client";
import { EbayOrders } from "./EbayOrders";
import type { EbayOrderDuplicateCandidate, EbayOrderStaging, EbayStatus, InventoryItemList, SaleRecord } from "../../types";

const status: EbayStatus = {
  configured: true,
  environment: "production",
  connected: true,
  requires_reconsent: false,
  missing_scopes: [],
  ebay_username: "seller",
  scopes: [
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",
    "https://api.ebay.com/oauth/api_scope/sell.finances"
  ],
  access_token_expires_at: "2026-06-14T10:00:00Z",
  refresh_token_expires_at: "2026-12-14T10:00:00Z",
  last_refresh_error: "",
  snapshot: {
    opted_in: true,
    policy_counts: { payment: 1, fulfillment: 1, return: 1 },
    fetched_at: "2026-06-14T09:00:00Z"
  }
};

const item: InventoryItemList = {
  id: "item-1",
  sku: "MAG-001",
  title: "Vintage watch",
  status: "available",
  condition: "used",
  category: null,
  category_name: null,
  quantity_total: 10,
  quantity_sold: 0,
  quantity_remaining: 10,
  estimated_value: "200.00",
  currency: "AUD",
  main_thumb_url: null,
  created_at: "2026-06-01T00:00:00Z"
};

const soldOutItem = {
  ...item,
  id: "item-sold-out",
  sku: "STM-00002",
  title: "Sold stamp",
  quantity_total: 1,
  quantity_sold: 1,
  quantity_remaining: 0
} satisfies InventoryItemList;

const stagingRow: EbayOrderStaging = {
  id: "stage-1",
  environment: "production",
  ebay_order_id: "order-1",
  ebay_line_item_id: "line-1",
  sku: "UNKNOWN-SKU",
  quantity: 3,
  line_price: "150.00",
  sale_date: "2026-06-12",
  actual_fee: "18.50",
  fee_status: "estimated_or_unmapped",
  buyer_region: "AU",
  status: "pending",
  resolved_sale: null,
  notes: "",
  created_at: "2026-06-12T01:00:00Z",
  updated_at: "2026-06-12T01:00:00Z"
};

const duplicateRow: EbayOrderDuplicateCandidate = {
  id: "dupe-1",
  environment: "production",
  ebay_order_id: "order-2",
  ebay_line_item_id: "line-2",
  sku: "MAG-001",
  item: "item-1",
  item_sku: "MAG-001",
  item_title: "Vintage watch",
  manual_sale_id: "sale-manual",
  quantity: 1,
  line_price: "200.00",
  sale_date: "2026-06-13",
  status: "pending",
  notes: "",
  created_at: "2026-06-13T01:00:00Z",
  updated_at: "2026-06-13T01:00:00Z"
};

const resolvedSale: SaleRecord = {
  id: "sale-1",
  item: "item-1",
  item_sku: "MAG-001",
  item_title: "Vintage watch",
  sale_date: "2026-06-12",
  quantity: 3,
  sale_price: "150.00",
  channel: "ebay_au",
  is_external: false,
  cost_basis_unknown: false,
  actual_fees_total: "18.50",
  actual_fee_breakdown: {},
  fee_status: "estimated_or_unmapped",
  actual_shipping_cost: "0.00",
  net_proceeds: "131.50",
  allocated_cost_basis: "30.00",
  realised_profit: "101.50",
  cost_basis_override: null,
  listing_draft: null,
  valuation_snapshot: {},
  estimated_fee_snapshot: {},
  provenance: "ebay_sync",
  ebay_order_id: "order-1",
  ebay_line_item_id: "line-1",
  ebay_transaction_id: null,
  channel_data: {},
  corrected_from: null,
  is_superseded: false,
  notes: "",
  created_at: "2026-06-12T01:00:00Z",
  updated_at: "2026-06-12T01:00:00Z"
};

const externalSale = {
  ...resolvedSale,
  id: "sale-external",
  item: null,
  item_sku: "",
  item_title: "External sale",
  is_external: true,
  cost_basis_unknown: true,
  allocated_cost_basis: null,
  realised_profit: null
} satisfies SaleRecord;

const mocks = vi.hoisted(() => ({
  getEbayStatus: vi.fn(),
  listEbayOrderDuplicates: vi.fn(),
  listEbayOrderStaging: vi.fn(),
  resolveEbayOrderDuplicate: vi.fn(),
  resolveEbayOrderStaging: vi.fn(),
  syncEbayOrders: vi.fn(),
  listItems: vi.fn()
}));

vi.mock("../../api/ebay", () => ({
  getEbayStatus: (...args: unknown[]) => mocks.getEbayStatus(...args),
  listEbayOrderDuplicates: (...args: unknown[]) => mocks.listEbayOrderDuplicates(...args),
  listEbayOrderStaging: (...args: unknown[]) => mocks.listEbayOrderStaging(...args),
  resolveEbayOrderDuplicate: (...args: unknown[]) => mocks.resolveEbayOrderDuplicate(...args),
  resolveEbayOrderStaging: (...args: unknown[]) => mocks.resolveEbayOrderStaging(...args),
  syncEbayOrders: (...args: unknown[]) => mocks.syncEbayOrders(...args)
}));

vi.mock("../../api/items", () => ({
  listItems: (...args: unknown[]) => mocks.listItems(...args)
}));

let pendingStagingRows: EbayOrderStaging[];
let pendingDuplicateRows: EbayOrderDuplicateCandidate[];

beforeEach(() => {
  pendingStagingRows = [stagingRow];
  pendingDuplicateRows = [];
  mocks.getEbayStatus.mockReset();
  mocks.getEbayStatus.mockResolvedValue(status);
  mocks.listEbayOrderStaging.mockReset();
  mocks.listEbayOrderStaging.mockImplementation(() => Promise.resolve({
    count: pendingStagingRows.length,
    next: null,
    previous: null,
    results: pendingStagingRows
  }));
  mocks.listEbayOrderDuplicates.mockReset();
  mocks.listEbayOrderDuplicates.mockImplementation(() => Promise.resolve({
    count: pendingDuplicateRows.length,
    next: null,
    previous: null,
    results: pendingDuplicateRows
  }));
  mocks.listItems.mockReset();
  mocks.listItems.mockResolvedValue({ count: 1, next: null, previous: null, results: [item] });
  mocks.resolveEbayOrderStaging.mockReset();
  mocks.resolveEbayOrderStaging.mockImplementation(() => {
    pendingStagingRows = [];
    return Promise.resolve(resolvedSale);
  });
  mocks.resolveEbayOrderDuplicate.mockReset();
  mocks.resolveEbayOrderDuplicate.mockResolvedValue({ ...duplicateRow, status: "linked" });
  mocks.syncEbayOrders.mockReset();
  mocks.syncEbayOrders.mockResolvedValue({
    environment: "production",
    start: "2025-06-14T00:00:00Z",
    end: "2026-06-14T00:00:00Z",
    counts: {
      created: 1,
      staged: 4,
      duplicate_flagged: 0,
      skipped: 2,
      fee_authoritative: 3,
      fee_estimated_or_unmapped: 1
    }
  });
});

function renderOrders() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <EbayOrders />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

test("runs manual sync and shows all result counts including conservative fee mapping", async () => {
  const user = userEvent.setup();
  renderOrders();

  await user.click(await screen.findByRole("button", { name: "Sync eBay orders" }));

  await waitFor(() => expect(mocks.syncEbayOrders).toHaveBeenCalledWith());
  expect(await screen.findByText("Sync completed")).toBeInTheDocument();
  expect(screen.getByText("Created")).toBeInTheDocument();
  expect(screen.getByText("Staged")).toBeInTheDocument();
  expect(screen.getByText("Duplicates")).toBeInTheDocument();
  expect(screen.getByText("Skipped")).toBeInTheDocument();
  expect(screen.getByText("Fee actual")).toBeInTheDocument();
  expect(screen.getByText("Fee review")).toBeInTheDocument();
});

test("links a staged row to an existing item and removes it from the pending queue", async () => {
  const user = userEvent.setup();
  renderOrders();

  const row = await screen.findByRole("article", { name: "" });
  await user.selectOptions(within(row).getByLabelText("Existing item for UNKNOWN-SKU"), "item-1");
  await user.click(within(row).getByRole("button", { name: "Link to item" }));

  await waitFor(() => expect(mocks.resolveEbayOrderStaging).toHaveBeenCalledWith("stage-1", {
    action: "link",
    item: "item-1",
    cost_basis_override: null,
    notes: ""
  }));
  expect(await screen.findByText("No pending staged orders")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "View it on Sales" })).toHaveAttribute("href", "/sales");
});

test("shows a friendly remaining-quantity error when linking a sold-out item", async () => {
  const user = userEvent.setup();
  const friendly = "Can\u2019t link \u2014 STM-00002 has no remaining quantity (1 of 1 already sold). Increase that item\u2019s quantity, choose a different item, or mark this order external.";
  mocks.listItems.mockResolvedValue({ count: 1, next: null, previous: null, results: [soldOutItem] });
  mocks.resolveEbayOrderStaging.mockRejectedValue(new ApiError(400, {
    detail: friendly,
    code: "quantity_remaining_exceeded"
  }));
  renderOrders();

  const row = await screen.findByRole("article", { name: "" });
  await user.selectOptions(within(row).getByLabelText("Existing item for UNKNOWN-SKU"), "item-sold-out");
  await user.click(within(row).getByRole("button", { name: "Link to item" }));

  expect(await screen.findByText(friendly)).toBeInTheDocument();
  expect(screen.queryByText("API request failed with status 400")).not.toBeInTheDocument();
});

test("quick-creates an item for a staged row", async () => {
  const user = userEvent.setup();
  renderOrders();

  await screen.findByText("UNKNOWN-SKU");
  await user.type(screen.getByLabelText("Quick-create title"), "Imported bulk lot");
  await user.type(screen.getByLabelText("Cost basis"), "40.00");
  await user.click(screen.getByRole("button", { name: "Quick-create item" }));

  await waitFor(() => expect(mocks.resolveEbayOrderStaging).toHaveBeenCalledWith("stage-1", {
    action: "quick_create",
    title: "Imported bulk lot",
    quantity_total: 3,
    acquisition_cost: "40.00",
    notes: ""
  }));
});

test("marks a staged row external with blank cost basis left unknown", async () => {
  const user = userEvent.setup();
  mocks.resolveEbayOrderStaging.mockImplementationOnce(() => {
    pendingStagingRows = [];
    return Promise.resolve(externalSale);
  });
  renderOrders();

  await screen.findByText("UNKNOWN-SKU");
  await user.click(screen.getByRole("button", { name: "Mark external" }));

  await waitFor(() => expect(mocks.resolveEbayOrderStaging).toHaveBeenCalledWith("stage-1", {
    action: "mark_external",
    cost_basis_override: null,
    notes: ""
  }));
  expect(await screen.findByText(/Sale recorded with unknown cost basis/)).toBeInTheDocument();
  expect(screen.getByText("No pending staged orders")).toBeInTheDocument();
});

test("shows the duplicate candidate empty state", async () => {
  renderOrders();

  expect(await screen.findByText("No duplicate candidates")).toBeInTheDocument();
});

test("resolves duplicate candidates without auto-merging", async () => {
  const user = userEvent.setup();
  pendingDuplicateRows = [duplicateRow];
  renderOrders();

  expect(await screen.findByRole("heading", { name: "MAG-001 - Vintage watch" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Link candidate" }));

  await waitFor(() => expect(mocks.resolveEbayOrderDuplicate).toHaveBeenCalledWith("dupe-1", { action: "link" }));
});
