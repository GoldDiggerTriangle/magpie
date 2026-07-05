import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import parityFixture from "../../fixtures/sprint19FormulaParity.json";
import { BuyCalculator } from "./BuyCalculator";
import { buyerProtectionFee, buyerVisibleTotal, calculateLocalBuy, sellerPriceFromBuyerVisible } from "./localCalculator";

const mocks = vi.hoisted(() => ({
  captureDescriptorComparable: vi.fn(),
  createBoughtItItem: vi.fn(),
  getDescriptorEvidence: vi.fn(),
  listItems: vi.fn(),
  listCategories: vi.fn(),
  getBuyCalculatorEvidence: vi.fn()
}));

vi.mock("../../api/categories", () => ({
  listCategories: (...args: unknown[]) => mocks.listCategories(...args)
}));

vi.mock("../../api/evidence", () => ({
  captureDescriptorComparable: (...args: unknown[]) => mocks.captureDescriptorComparable(...args),
  getDescriptorEvidence: (...args: unknown[]) => mocks.getDescriptorEvidence(...args)
}));

vi.mock("../../api/items", () => ({
  listItems: (...args: unknown[]) => mocks.listItems(...args)
}));

vi.mock("../../api/profit", () => ({
  createBoughtItItem: (...args: unknown[]) => mocks.createBoughtItItem(...args),
  getBuyCalculatorEvidence: (...args: unknown[]) => mocks.getBuyCalculatorEvidence(...args)
}));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listItems.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{ id: "item-1", sku: "STM-00003", title: "KGV stamp", category: "cat-1" }]
  });
  mocks.listCategories.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{ id: "cat-1", name: "Stamps", slug: "stamps", parent: null, sku_prefix: "STM", profile_key: "stamps", description: "" }]
  });
  mocks.getDescriptorEvidence.mockResolvedValue({
    lookup: { category: "cat-1", category_label: "Stamps", terms: ["kgv", "stamp"], attributes: {}, transient: true },
    rows: [
      {
        id: "sale:descriptor-1",
        record_type: "sale",
        source: "own_sale_exact",
        source_label: "Own sale",
        label: "Descriptor exact sale",
        rank: 0,
        match_scope: "exact",
        match_reason: "same category; matched terms: kgv",
        price: "100.00",
        price_basis: "seller_receives",
        seller_receives: "100.00",
        basis_uncertain: false,
        basis_label: "Seller receives",
        currency: "AUD",
        date: "2026-06-20",
        url: "",
        item: "item-1",
        item_sku: "STM-00003",
        own_sale: true
      },
      {
        id: "comp:descriptor-uncertain",
        record_type: "comparable",
        source: "approved_comp",
        source_label: "Manual comp",
        label: "Basis uncertain comp",
        rank: 2,
        match_scope: "similar",
        match_reason: "same category",
        price: "120.00",
        price_basis: "unknown",
        seller_receives: null,
        basis_uncertain: true,
        basis_label: "Basis uncertain",
        currency: "AUD",
        date: "2026-06-21",
        url: "",
        item: null,
        item_sku: "",
        own_sale: false
      }
    ],
    stats: {
      basis: "seller_receives",
      low: "100.00",
      median: "100.00",
      high: "100.00",
      count: 1,
      unknown_basis_count: 1,
      newest_date: "2026-06-20",
      newest_age_days: 15
    },
    strength: {
      label: "THIN",
      known_basis_count: 1,
      newest_age_days: 15,
      tooltip: "STRONG = at least 3 known-basis rows from the last 12 months, including at least 1 from the last 90 days. Otherwise THIN."
    },
    empty: false,
    empty_state: { title: "Thin descriptor evidence", detail: "Use the known-basis rows as evidence." }
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
  mocks.captureDescriptorComparable.mockResolvedValue({
    comparable: {
      id: "comp-new",
      item: null,
      descriptor_category: "cat-1",
      descriptor_terms: ["kgv", "stamp"],
      descriptor_attributes: {},
      kind: "sold",
      source: "Auction archive",
      title: "Captured KGV sold comp",
      price: "65.00",
      price_basis: "unknown",
      shipping: null,
      currency: "AUD",
      condition: "",
      grade: "",
      sale_format: "unknown",
      source_tag: "manual",
      match_scope: "similar",
      match_reason: "user-captured from descriptor lookup",
      url: "",
      observed_on: null,
      notes: "",
      created_at: "",
      updated_at: ""
    },
    lookup: {
      lookup: { category: "cat-1", category_label: "Stamps", terms: ["kgv", "stamp"], attributes: {}, transient: true },
      rows: [],
      stats: { basis: "seller_receives", low: null, median: null, high: null, count: 0, unknown_basis_count: 1, newest_date: null, newest_age_days: null },
      strength: { label: "THIN", known_basis_count: 0, newest_age_days: null, tooltip: "STRONG = at least 3 known-basis rows from the last 12 months, including at least 1 from the last 90 days. Otherwise THIN." },
      empty: false,
      empty_state: { title: "Evidence basis needs review", detail: "Basis uncertain." }
    }
  });
  mocks.createBoughtItItem.mockResolvedValue({
    id: "bought-1",
    sku: "STM-00004",
    title: "Bought from calculator",
    status: "captured",
    condition: "ungraded",
    category: "cat-1",
    category_name: "Stamps",
    quantity_total: 1,
    quantity_sold: 0,
    quantity_remaining: 1,
    estimated_value: "100.00",
    currency: "AUD",
    main_thumb_url: null,
    created_at: "",
    location: null,
    acquisition: null,
    acquisition_cost: "60.00",
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
  });
});

test("BuyCalculator renders max buy result and evidence confidence", async () => {
  renderWithClient(<BuyCalculator />);

  expect(await screen.findByText("Max Buy / Max Bid")).toBeInTheDocument();
  expect(await screen.findByText("$69.23")).toBeInTheDocument();
  expect(screen.getByText("NO ASKING PRICE")).toBeInTheDocument();
  expect(screen.getAllByText(/own sale - exact/i).length).toBeGreaterThan(0);
});

test("BuyCalculator labels what-if input and does not call persistence APIs", async () => {
  const user = userEvent.setup();
  renderWithClient(<BuyCalculator />);

  await screen.findByText("$69.23");
  const input = screen.getByLabelText(/Expected sell price/i);
  await user.clear(input);
  await user.type(input, "120");

  await waitFor(() => expect(screen.getByText("$92.31")).toBeInTheDocument());
  expect(screen.getByText(/What-if inputs are calculation-only/i)).toBeInTheDocument();
  expect(mocks.captureDescriptorComparable).not.toHaveBeenCalled();
  expect(mocks.createBoughtItItem).not.toHaveBeenCalled();
});

test("BuyCalculator still calculates typed what-if input when authenticated lookups fail", async () => {
  const user = userEvent.setup();
  mocks.listItems.mockRejectedValue(new Error("Authentication credentials were not provided."));
  mocks.getBuyCalculatorEvidence.mockRejectedValue(new Error("Authentication credentials were not provided."));

  renderWithClient(<BuyCalculator />);

  await user.type(screen.getByLabelText(/Expected sell price/i), "100");
  await user.type(screen.getByLabelText(/Asking price/i), "60");

  expect(await screen.findByText("$76.92")).toBeInTheDocument();
  expect(screen.getByText("BUY")).toBeInTheDocument();
  expect(screen.getByText(/typed what-if calculations still work/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open admin login" })).toHaveAttribute("href", "/admin/login/?next=%2F");
});

test("BuyCalculator keeps unknown-basis evidence out of max-buy maths", async () => {
  renderWithClient(<BuyCalculator />);

  const unknown = await screen.findByRole("button", { name: /Unknown eBay comp/i });
  expect(unknown).toBeDisabled();
  expect(screen.getByText(/basis uncertain/i)).toBeInTheDocument();
});

test("BuyCalculator descriptor use-this applies seller-receives price and source label", async () => {
  const user = userEvent.setup();
  renderWithClient(<BuyCalculator />);

  await screen.findByRole("option", { name: /STM-00003/i });
  await user.selectOptions(await screen.findByLabelText(/Evidence item/i), "item-1");
  const useThis = (await screen.findAllByRole("button", { name: /Use this/i })).find((button) => !button.hasAttribute("disabled"));
  if (!useThis) {
    throw new Error("Expected an enabled Use this button.");
  }
  await user.click(useThis);

  await waitFor(() => expect(screen.getByDisplayValue("100.00")).toBeInTheDocument());
  expect(screen.getByText(/\$76.92/)).toBeInTheDocument();
  expect(screen.getAllByText(/own sale - exact/i).length).toBeGreaterThan(0);
});

test("BuyCalculator fast capture defaults basis unknown and refreshes descriptor lookup", async () => {
  const user = userEvent.setup();
  renderWithClient(<BuyCalculator />);

  await screen.findByRole("option", { name: /STM-00003/i });
  await user.selectOptions(await screen.findByLabelText(/Evidence item/i), "item-1");
  await user.type(await screen.findByLabelText(/Human-entered price/i), "65");
  await user.type(screen.getByLabelText(/^Source$/i), "Auction archive");
  await user.click(screen.getByRole("button", { name: /Save approved comp/i }));

  await waitFor(() => expect(mocks.captureDescriptorComparable).toHaveBeenCalled());
  expect(mocks.captureDescriptorComparable.mock.calls[0][0]).toMatchObject({
    category: "cat-1",
    terms: "KGV stamp",
    price: "65",
    price_basis: "unknown",
    source: "Auction archive"
  });
});

test("BuyCalculator bought-it flow creates an item from calculator context", async () => {
  const user = userEvent.setup();
  renderWithClient(<BuyCalculator />);

  await screen.findByDisplayValue("90.00");
  const expectedSellPrice = await screen.findByLabelText(/Expected sell price/i);
  await user.clear(expectedSellPrice);
  await user.type(expectedSellPrice, "100");
  await user.type(screen.getByLabelText(/Asking price/i), "60");
  await user.click(await screen.findByRole("button", { name: /Bought it/i }));

  await waitFor(() => expect(mocks.createBoughtItItem).toHaveBeenCalled());
  expect(mocks.createBoughtItItem.mock.calls[0][0]).toMatchObject({
    agreed_price: "60",
    expected_sell_price: "100",
    price_basis: "seller_receives"
  });
});

test("shared Sprint 19 formula fixture matches the frontend calculator", () => {
  for (const buyCase of parityFixture.buy_cases) {
    const result = calculateLocalBuy({
      expected_sell_price: buyCase.expected_sell_price,
      price_basis: buyCase.price_basis as "seller_receives" | "buyer_visible" | "unknown",
      seller_mode: buyCase.seller_mode as "free_selling" | "pro_starter" | "pro_other" | "legacy_manual",
      target_type: buyCase.target_type as "roi" | "flat",
      flat_profit_target: buyCase.flat_profit_target,
      roi_pct: buyCase.roi_pct,
      roi_basis: buyCase.roi_basis as "all_in_cash" | "buy_price",
      postage: buyCase.postage,
      packaging: buyCase.packaging,
      refurb: buyCase.refurb,
      asking_price: buyCase.asking_price,
      evidence_source: "what_if",
      confidence_label: "what-if (your estimate)"
    });
    expect(result.max_buy).toBe(buyCase.expected.max_buy);
    expect(result.verdict).toBe(buyCase.expected.verdict);
    expect(result.expected_profit_at_asking).toBe(buyCase.expected.expected_profit_at_asking);
    expect(result.roi_at_asking).toBe(buyCase.expected.roi_at_asking);
    expect(result.seller_fees).toBe(buyCase.expected.seller_fees);
    expect(result.non_buy_costs).toBe(buyCase.expected.non_buy_costs);
  }

  for (const roundTrip of parityFixture.bpf_round_trips) {
    const seller = Number(roundTrip.seller_receives);
    const buyer = Number(roundTrip.buyer_visible_total);
    expect(buyerProtectionFee(seller).toFixed(2)).toBe(roundTrip.buyer_protection_fee);
    expect(buyerVisibleTotal(seller).toFixed(2)).toBe(roundTrip.buyer_visible_total);
    expect(sellerPriceFromBuyerVisible(buyer).toFixed(2)).toBe(roundTrip.seller_receives);
  }
});

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>
  );
}
