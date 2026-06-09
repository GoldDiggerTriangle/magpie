import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";

import { ValuationPanel } from "./ValuationPanel";
import type { InventoryItemDetail } from "../types";

const mocks = vi.hoisted(() => ({
  createValuationReport: vi.fn(),
  comp: {
    id: "comp-1",
    item: "item-1",
    kind: "sold",
    source: "Manual",
    title: "Test comp",
    price: "50.00",
    shipping: null,
    currency: "AUD",
    condition: "",
    url: "",
    observed_on: null,
    notes: "",
    created_at: "",
    updated_at: ""
  }
}));

vi.mock("../api/comparables", () => ({
  listComparables: vi.fn(async () => ({
    count: 1,
    next: null,
    previous: null,
    results: [mocks.comp]
  }))
}));

vi.mock("../api/fees", () => ({
  listFeeSchedules: vi.fn(async () => ({
    count: 1,
    next: null,
    previous: null,
    results: [{ id: "fee-1", name: "Schedule", is_active: true }]
  }))
}));

vi.mock("../api/valuation", () => ({
  createValuationReport: (...args: unknown[]) => mocks.createValuationReport(...args),
  listItemValuationReports: vi.fn(async () => ({ count: 0, next: null, previous: null, results: [] })),
  setCurrentValuationReport: vi.fn()
}));

const item = {
  id: "item-1",
  sku: "COIN-00001",
  title: "Coin",
  status: "needs_research",
  condition: "good",
  category: "cat-1",
  category_name: "Coins",
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
  comps_count: 1,
  current_valuation: null,
  updated_at: ""
} satisfies InventoryItemDetail;

beforeEach(() => {
  mocks.createValuationReport.mockClear();
});

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ValuationPanel item={item} />
    </QueryClientProvider>
  );
}

test("ValuationPanel requires an exclusion reason for excluded comps", async () => {
  const user = userEvent.setup();
  renderPanel();

  await screen.findByText("Test comp");
  await user.click(screen.getByLabelText(/Test comp/));
  await user.click(screen.getByRole("button", { name: "Create valuation report" }));

  expect(screen.getByText("Excluded comparables require an exclusion reason.")).toBeInTheDocument();
  expect(mocks.createValuationReport).not.toHaveBeenCalled();
});

test("ValuationPanel requires override reason when overriding", async () => {
  const user = userEvent.setup();
  renderPanel();

  await screen.findByText("Test comp");
  await user.click(screen.getByLabelText("Manual override"));
  await user.click(screen.getByRole("button", { name: "Create valuation report" }));

  expect(screen.getByText("Override reason is required when manual override is enabled.")).toBeInTheDocument();
  await waitFor(() => expect(mocks.createValuationReport).not.toHaveBeenCalled());
});
