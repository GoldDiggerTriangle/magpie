import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import { SalesPanel } from "./SalesPanel";
import type { InventoryItemDetail, SaleRecord } from "../types";

const mocks = vi.hoisted(() => ({
  correctSaleRecord: vi.fn(),
  createItemSale: vi.fn(),
  listFeeSchedules: vi.fn(),
  listItemListingDrafts: vi.fn(),
  listItemSales: vi.fn()
}));

vi.mock("../api/sales", () => ({
  correctSaleRecord: (...args: unknown[]) => mocks.correctSaleRecord(...args),
  createItemSale: (...args: unknown[]) => mocks.createItemSale(...args),
  listItemSales: (...args: unknown[]) => mocks.listItemSales(...args)
}));

vi.mock("../api/fees", () => ({
  listFeeSchedules: (...args: unknown[]) => mocks.listFeeSchedules(...args)
}));

vi.mock("../api/listing", () => ({
  listItemListingDrafts: (...args: unknown[]) => mocks.listItemListingDrafts(...args)
}));

const item = {
  id: "item-1",
  sku: "LOT-00001",
  title: "Stamp lot",
  status: "partially_sold",
  condition: "good",
  category: "cat-1",
  category_name: "Stamps",
  quantity_total: 10,
  quantity_sold: 3,
  quantity_remaining: 7,
  estimated_value: "90.00",
  currency: "AUD",
  main_thumb_url: null,
  created_at: "",
  location: null,
  acquisition: null,
  acquisition_cost: "100.00",
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

const sale = {
  id: "sale-1",
  item: "item-1",
  item_sku: "LOT-00001",
  item_title: "Stamp lot",
  sale_date: "2026-06-14",
  quantity: 3,
  sale_price: "90.00",
  channel: "manual",
  is_external: false,
  cost_basis_unknown: false,
  actual_fees_total: "9.00",
  actual_fee_breakdown: {},
  fee_status: "authoritative",
  actual_shipping_cost: "5.00",
  net_proceeds: "76.00",
  allocated_cost_basis: "30.00",
  realised_profit: "46.00",
  cost_basis_override: null,
  listing_draft: null,
  valuation_snapshot: {},
  estimated_fee_snapshot: {},
  provenance: "manual",
  ebay_order_id: null,
  ebay_line_item_id: null,
  ebay_transaction_id: null,
  channel_data: {},
  corrected_from: null,
  is_superseded: false,
  notes: "",
  created_at: "",
  updated_at: ""
} satisfies SaleRecord;

beforeEach(() => {
  mocks.createItemSale.mockReset();
  mocks.createItemSale.mockResolvedValue({ id: "sale-new" });
  mocks.correctSaleRecord.mockReset();
  mocks.correctSaleRecord.mockResolvedValue({ id: "sale-correction", corrected_from: "sale-1" });
  mocks.listFeeSchedules.mockReset();
  mocks.listFeeSchedules.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{
      id: "fee-1",
      name: "Manual fee",
      effective_from: "2026-01-01",
      is_active: true,
      final_value_pct: "10.00",
      per_order_fee: "0.00",
      promoted_pct: "0.00",
      gst_pct: "0.00",
      default_packaging_cost: "0.00",
      default_outbound_shipping: "0.00",
      notes: "",
      created_at: "",
      updated_at: ""
    }]
  });
  mocks.listItemListingDrafts.mockReset();
  mocks.listItemListingDrafts.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.listItemSales.mockReset();
  mocks.listItemSales.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
});

function renderPanel(panelItem: InventoryItemDetail = item) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SalesPanel item={panelItem} />
    </QueryClientProvider>
  );
}

test("SalesPanel records a manual sale with fee prefill and cost-basis preview", async () => {
  const user = userEvent.setup();
  renderPanel();

  expect(screen.getByText("3 sold / 7 remaining from 10")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByLabelText("Fees")).toHaveValue("9.00"));

  await user.clear(screen.getByLabelText("Sale price"));
  await user.type(screen.getByLabelText("Sale price"), "80.00");
  await waitFor(() => expect(screen.getByLabelText("Fees")).toHaveValue("8.00"));
  expect(screen.getByText("Cost basis $10.00")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Record sale" }));

  await waitFor(() => expect(mocks.createItemSale).toHaveBeenCalledWith("item-1", expect.objectContaining({
    quantity: 1,
    sale_price: "80.00",
    actual_fees_total: "8.00",
    actual_shipping_cost: "0.00",
    cost_basis_override: null
  })));
});

test("SalesPanel writes corrections as a correction endpoint call", async () => {
  mocks.listItemSales.mockResolvedValue({ count: 1, next: null, previous: null, results: [sale] });
  const user = userEvent.setup();
  renderPanel();

  await user.click(await screen.findByRole("button", { name: "Correct" }));
  expect(screen.getByText("Correction for sale 2026-06-14")).toBeInTheDocument();

  await user.clear(screen.getByLabelText(/Quantity/));
  await user.type(screen.getByLabelText(/Quantity/), "2");
  await user.click(screen.getByRole("button", { name: "Save correction" }));

  await waitFor(() => expect(mocks.correctSaleRecord).toHaveBeenCalledWith("sale-1", expect.objectContaining({
    quantity: 2,
    sale_price: "90.00"
  })));
});
