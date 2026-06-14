import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import { SalesList } from "./SalesList";
import type { SaleRecord } from "../../types";

const sale = {
  id: "sale-1",
  item: null,
  item_sku: "",
  item_title: "External sale",
  sale_date: "2026-06-12",
  quantity: 1,
  sale_price: "99.00",
  channel: "ebay_au",
  is_external: true,
  cost_basis_unknown: true,
  actual_fees_total: "10.00",
  actual_fee_breakdown: {},
  fee_status: "estimated_or_unmapped",
  actual_shipping_cost: "0.00",
  net_proceeds: "89.00",
  allocated_cost_basis: null,
  realised_profit: null,
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
} satisfies SaleRecord;

const mocks = vi.hoisted(() => ({
  listSales: vi.fn()
}));

vi.mock("../../api/sales", () => ({
  listSales: (...args: unknown[]) => mocks.listSales(...args)
}));

beforeEach(() => {
  mocks.listSales.mockReset();
  mocks.listSales.mockResolvedValue({ count: 1, next: null, previous: null, results: [sale] });
});

function renderSalesList() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SalesList />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

test("shows an eBay resolved external sale on the Sales screen", async () => {
  renderSalesList();

  expect(await screen.findByText("External sale")).toBeInTheDocument();
  expect(screen.getByText("$99.00")).toBeInTheDocument();
  expect(screen.getByText("$89.00")).toBeInTheDocument();
});
