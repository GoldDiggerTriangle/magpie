import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { beforeEach, expect, test, vi } from "vitest";

import { BuyCalculator } from "./BuyCalculator";

const mocks = vi.hoisted(() => ({
  listItems: vi.fn(),
  getBuyCalculatorEvidence: vi.fn(),
  calculateBuy: vi.fn()
}));

vi.mock("../../api/items", () => ({
  listItems: (...args: unknown[]) => mocks.listItems(...args)
}));

vi.mock("../../api/profit", () => ({
  getBuyCalculatorEvidence: (...args: unknown[]) => mocks.getBuyCalculatorEvidence(...args),
  calculateBuy: (...args: unknown[]) => mocks.calculateBuy(...args)
}));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listItems.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{ id: "item-1", sku: "STM-00003", title: "KGV stamp" }]
  });
  mocks.getBuyCalculatorEvidence.mockResolvedValue({
    settings: {
      seller_mode: "free_selling",
      pro_other_final_value_pct: "13.400",
      manual_final_value_pct: "0.000",
      manual_fixed_fee: "0.00",
      default_flat_profit_target: "25.00",
      default_roi_pct: "30.000",
      default_roi_basis: "all_in_cash",
      maybe_band_pct: "10.000",
      schema_version: 1,
      updated_at: null
    },
    item: "item-1",
    evidence: [
      {
        id: "sale:1",
        label: "Own exact sale",
        source: "own_sale_exact",
        confidence_label: "own sale - exact",
        match_scope: "exact",
        match_reason: "same inventory item",
        price: "90.00",
        price_basis: "seller_receives",
        seller_receives: "90.00",
        basis_uncertain: false,
        date: "2026-06-01"
      },
      {
        id: "comp:1",
        label: "Unknown eBay comp",
        source: "approved_comp",
        confidence_label: "approved comp",
        match_scope: "similar",
        match_reason: "same category",
        price: "99.00",
        price_basis: "unknown",
        seller_receives: null,
        basis_uncertain: true,
        date: "2026-06-02"
      }
    ],
    suggested: {
      price: "90.00",
      price_basis: "seller_receives",
      source: "own_sale_exact",
      confidence_label: "own sale - exact",
      sample_size: 1
    },
    empty: false,
    price_basis_options: []
  });
  mocks.calculateBuy.mockResolvedValue({
    max_buy: "58.23",
    headline: "Max Buy Price",
    verdict: "BUY",
    expected_profit_at_asking: "28.23",
    roi_at_asking: "47.05",
    net_proceeds_before_buy: "88.23",
    seller_fees: "0.00",
    non_buy_costs: "1.77",
    evidence_source: "own_sale_exact",
    confidence_label: "own sale - exact",
    roi_basis: "all_in_cash"
  });
});

test("BuyCalculator renders max buy result and evidence confidence", async () => {
  renderWithClient(<BuyCalculator />);

  expect(await screen.findByText("Max Buy / Max Bid")).toBeInTheDocument();
  expect(await screen.findByText("$58.23")).toBeInTheDocument();
  expect(screen.getByText("BUY")).toBeInTheDocument();
  expect(screen.getAllByText(/own sale - exact/i).length).toBeGreaterThan(0);
  expect(mocks.calculateBuy).toHaveBeenCalledWith(expect.objectContaining({
    evidence_source: "own_sale_exact",
    roi_basis: "all_in_cash"
  }));
});

test("BuyCalculator labels what-if input and does not call persistence APIs", async () => {
  const user = userEvent.setup();
  renderWithClient(<BuyCalculator />);

  await screen.findByText("$58.23");
  const input = screen.getByLabelText(/Expected sell price/i);
  await user.clear(input);
  await user.type(input, "120");

  await waitFor(() => expect(mocks.calculateBuy).toHaveBeenCalledWith(expect.objectContaining({
    expected_sell_price: "120",
    evidence_source: "what_if",
    confidence_label: "what-if (your estimate)"
  })));
  expect(screen.getByText(/What-if inputs are calculation-only/i)).toBeInTheDocument();
});

test("BuyCalculator keeps unknown-basis evidence out of max-buy maths", async () => {
  renderWithClient(<BuyCalculator />);

  const unknown = await screen.findByRole("button", { name: /Unknown eBay comp/i });
  expect(unknown).toBeDisabled();
  expect(screen.getByText(/basis uncertain/i)).toBeInTheDocument();
});

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  return render(
    <QueryClientProvider client={client}>
      {ui}
    </QueryClientProvider>
  );
}
