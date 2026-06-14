import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import { Dashboard } from "./Dashboard";
import type {
  AnalyticsAging,
  AnalyticsByCategory,
  AnalyticsEstimateVsActual,
  AnalyticsListingOpportunities,
  AnalyticsPnl,
  AnalyticsSummary,
  DashboardPreference,
  PaginatedResponse,
  ProductCategory
} from "../../types";

vi.mock("../../api/dashboard", () => ({
  getDashboardPreferences: vi.fn(),
  updateDashboardPreferences: vi.fn(),
  getAnalyticsSummary: vi.fn(),
  getAnalyticsPnl: vi.fn(),
  getAnalyticsByCategory: vi.fn(),
  getAnalyticsEstimateVsActual: vi.fn(),
  getAnalyticsAging: vi.fn(),
  getAnalyticsListingOpportunities: vi.fn()
}));

vi.mock("../../api/categories", () => ({
  listCategories: vi.fn()
}));

const dashboardApi = await import("../../api/dashboard");
const categoryApi = await import("../../api/categories");

const availableTiles = [
  { id: "realised_profit", label: "Realised profit", format: "currency", description: "Known-cost sales only." },
  { id: "net_proceeds", label: "Net proceeds", format: "currency", description: "Revenue less fees and shipping." },
  { id: "sell_through", label: "Sell-through", format: "percent", description: "Sold divided by sold plus available." },
  { id: "items_sold", label: "Items sold", format: "integer", description: "Quantity sold." },
  { id: "avg_realised_margin", label: "Avg margin", format: "percent", description: "Known-cost margin." },
  { id: "gross_revenue", label: "Revenue", format: "currency", description: "Gross revenue." }
] satisfies DashboardPreference["available_tiles"];

const preference: DashboardPreference = {
  kpi_tiles: ["realised_profit", "net_proceeds", "sell_through", "items_sold", "avg_realised_margin"],
  schema_version: 1,
  available_tiles: availableTiles,
  updated_at: null
};

const categories: PaginatedResponse<ProductCategory> = {
  count: 1,
  next: null,
  previous: null,
  results: [{
    id: "cat-1",
    name: "Stamps",
    slug: "stamps",
    parent: null,
    sku_prefix: "STM",
    profile_key: "",
    description: ""
  }]
};

const summary: AnalyticsSummary = {
  currency: "AUD",
  filters: { range: "12m", start: null, end: null, category: [], channel: "all", unknown: "honest" },
  tiles: {
    realised_profit: tile("realised_profit", "Realised profit", "currency", "50.00", "+1 unknown-cost sale excluded."),
    gross_revenue: tile("gross_revenue", "Revenue", "currency", "130.00"),
    net_proceeds: tile("net_proceeds", "Net proceeds", "currency", "115.00"),
    items_sold: tile("items_sold", "Items sold", "integer", "3"),
    sell_through: tile("sell_through", "Sell-through", "percent", "18.18"),
    avg_realised_margin: tile("avg_realised_margin", "Avg margin", "percent", "62.50"),
    avg_time_to_sale: tile("avg_time_to_sale", "Avg time to sale", "days", "12"),
    inventory_cost_basis: tile("inventory_cost_basis", "Inventory cost", "currency", "180.00"),
    estimated_inventory_value: tile("estimated_inventory_value", "Est. inventory value", "currency", "394.00"),
    aged_inventory_count: tile("aged_inventory_count", "Aged stock", "integer", "1"),
    unresolved_ebay_staging_count: tile("unresolved_ebay_staging_count", "eBay to triage", "integer", "4"),
    cost_basis_unknown_sales_count: tile("cost_basis_unknown_sales_count", "Unknown-cost sales", "integer", "1")
  },
  action_counts: {
    unresolved_ebay_staging: 4,
    cost_basis_unknown_sales: 1,
    listing_opportunities: 1
  },
  sample: { sales: 2, known_profit_sales: 1, linked_sales: 1 }
};

const pnl: AnalyticsPnl = {
  currency: "AUD",
  small_sample: true,
  empty: false,
  series: [{
    month: "2026-06-01",
    realised_profit: "50.00",
    net_proceeds: "115.00",
    gross_revenue: "130.00",
    quantity: 3,
    unknown_cost_sales: 1
  }]
};

const byCategory: AnalyticsByCategory = {
  currency: "AUD",
  empty: false,
  small_sample: true,
  categories: [{
    category_id: "cat-1",
    category: "Stamps",
    gross_revenue: "80.00",
    realised_profit: "50.00",
    margin: "62.50",
    sell_through: "18.18",
    items_sold: 2,
    available_units: 9,
    unknown_cost_sales: 0
  }]
};

const estimate: AnalyticsEstimateVsActual = {
  currency: "AUD",
  accuracy: {
    sample_size: 1,
    within_20_pct: "100.00",
    median_abs_pct_error: "6.67",
    small_sample: true,
    empty: false
  },
  fees: {
    sample_size: 1,
    estimated_fees_total: "8.00",
    actual_fees_total: "8.00",
    delta: "0.00"
  },
  points: [{
    sale_id: "sale-1",
    item_id: "item-1",
    sku: "STM-00001",
    title: "Stamp lot",
    sale_date: "2026-06-14",
    estimated: "75.00",
    actual: "80.00",
    delta_pct: "6.67"
  }]
};

const aging: AnalyticsAging = {
  currency: "AUD",
  empty: false,
  buckets: [
    { id: "0_30", label: "0-30 days", count: 0, quantity_remaining: 0, cost_basis: "0.00", estimated_value: "0.00" },
    { id: "31_90", label: "31-90 days", count: 1, quantity_remaining: 8, cost_basis: "80.00", estimated_value: "64.00" },
    { id: "91_180", label: "91-180 days", count: 1, quantity_remaining: 1, cost_basis: "100.00", estimated_value: "330.00" },
    { id: "180_plus", label: "180+ days", count: 0, quantity_remaining: 0, cost_basis: "0.00", estimated_value: "0.00" }
  ]
};

const opportunities: AnalyticsListingOpportunities = {
  currency: "AUD",
  empty: false,
  items: [{
    item_id: "item-2",
    sku: "STM-00002",
    title: "Gold ring",
    category: "Stamps",
    quantity_remaining: 1,
    estimated_value: "330.00",
    cost_basis: "100.00",
    estimated_margin: "230.00",
    status: "ready_to_list"
  }]
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(dashboardApi.getDashboardPreferences).mockResolvedValue(preference);
  vi.mocked(dashboardApi.updateDashboardPreferences).mockResolvedValue({
    ...preference,
    kpi_tiles: ["net_proceeds", "realised_profit", "sell_through"]
  });
  vi.mocked(dashboardApi.getAnalyticsSummary).mockResolvedValue(summary);
  vi.mocked(dashboardApi.getAnalyticsPnl).mockResolvedValue(pnl);
  vi.mocked(dashboardApi.getAnalyticsByCategory).mockResolvedValue(byCategory);
  vi.mocked(dashboardApi.getAnalyticsEstimateVsActual).mockResolvedValue(estimate);
  vi.mocked(dashboardApi.getAnalyticsAging).mockResolvedValue(aging);
  vi.mocked(dashboardApi.getAnalyticsListingOpportunities).mockResolvedValue(opportunities);
  vi.mocked(categoryApi.listCategories).mockResolvedValue(categories);
});

test("Dashboard renders the default command-centre KPI row and sections", async () => {
  renderDashboard();

  expect(await screen.findByRole("heading", { name: "Dealer's ledger" })).toBeInTheDocument();
  expect(await screen.findByText("Realised profit")).toBeInTheDocument();
  expect(screen.getAllByText("Net proceeds").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Sell-through").length).toBeGreaterThan(0);
  expect(screen.getByText("Estimate vs actual")).toBeInTheDocument();
  expect(screen.getByLabelText("Estimate versus actual table")).toHaveTextContent("STM-00001");
  expect(screen.getByText("What's worth listing next")).toBeInTheDocument();
  expect(screen.getByText("STM-00002")).toBeInTheDocument();
});

test("Dashboard persists KPI preference ordering from the picker", async () => {
  const user = userEvent.setup();
  renderDashboard();

  await screen.findByText("Realised profit");
  await user.click(screen.getByRole("button", { name: /customise/i }));
  const netRow = screen.getByRole("checkbox", { name: /Net proceeds/i }).closest(".kpi-picker-row");
  expect(netRow).not.toBeNull();
  await user.click(within(netRow as HTMLElement).getByRole("button", { name: "Move Net proceeds up" }));
  await user.click(screen.getByRole("checkbox", { name: /Avg margin/i }));
  await user.click(screen.getByRole("button", { name: /save row/i }));

  expect(vi.mocked(dashboardApi.updateDashboardPreferences).mock.calls[0][0]).toEqual([
    "net_proceeds",
    "realised_profit",
    "sell_through",
    "items_sold"
  ]);
});

test("Dashboard empty states point to the next operational action", async () => {
  vi.mocked(dashboardApi.getAnalyticsPnl).mockResolvedValue({ ...pnl, empty: true, series: [] });
  vi.mocked(dashboardApi.getAnalyticsEstimateVsActual).mockResolvedValue({
    ...estimate,
    accuracy: { ...estimate.accuracy, sample_size: 0, empty: true, small_sample: false },
    points: []
  });
  vi.mocked(dashboardApi.getAnalyticsListingOpportunities).mockResolvedValue({
    ...opportunities,
    empty: true,
    items: []
  });

  renderDashboard();

  expect(await screen.findByText("No sales yet.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Review eBay orders" })).toHaveAttribute("href", "/ebay/orders");
  expect(screen.getByText("No valuation pairs yet.")).toBeInTheDocument();
  expect(screen.getByText("Nothing waiting to be listed.")).toBeInTheDocument();
});

function renderDashboard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function tile(id: AnalyticsSummary["tiles"][keyof AnalyticsSummary["tiles"]]["id"], label: string, format: AnalyticsSummary["tiles"][keyof AnalyticsSummary["tiles"]]["format"], value: string, secondary = "") {
  return {
    id,
    label,
    format,
    value,
    secondary,
    excluded_count: secondary ? 1 : 0,
    description: label
  };
}
