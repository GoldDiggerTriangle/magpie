import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { ProfitBreakdown } from "./ProfitBreakdown";
import type { InventoryItemDetail } from "../types";

const mocks = vi.hoisted(() => ({
  projection: (label: string, sale: string, net: string, margin: string) => ({
    label,
    sale_price: sale,
    final_value_fee: "1.00",
    per_order_fee: "0.30",
    promoted_fee: "0.00",
    gst_on_fees: "0.13",
    outbound_shipping: "5.00",
    packaging: "1.00",
    true_cost: "20.00",
    total_deductions: "40.00",
    net_profit: net,
    margin_pct: margin
  })
}));

vi.mock("../api/items", () => ({
  updateItem: vi.fn()
}));

vi.mock("../api/valuation", () => ({
  getReportProfit: vi.fn(),
  getValuationReport: vi.fn(async () => ({
    id: "report-1",
    profit_projection: [
      mocks.projection("fast_sale", "50.00", "10.00", "0.2000"),
      mocks.projection("suggested", "75.00", "20.00", "0.2667"),
      mocks.projection("patient", "100.00", "30.00", "0.3000")
    ]
  }))
}));

const item = {
  id: "item-1",
  sku: "STM-1",
  title: "Stamp",
  status: "captured",
  condition: "good",
  category: null,
  category_name: null,
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
  updated_at: ""
} satisfies InventoryItemDetail;

test("ProfitBreakdown renders the three report projections", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ProfitBreakdown item={item} reportId="report-1" />
    </QueryClientProvider>
  );

  expect(await screen.findByText(/fast_sale/)).toBeInTheDocument();
  expect(screen.getByText(/suggested/)).toBeInTheDocument();
  expect(screen.getByText(/patient/)).toBeInTheDocument();
});
