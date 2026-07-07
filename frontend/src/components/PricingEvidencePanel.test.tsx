import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { beforeEach, expect, test, vi } from "vitest";

import { PricingEvidencePanel } from "./PricingEvidencePanel";
import type { PricingEvidence } from "../types";

const mocks = vi.hoisted(() => ({
  createComparable: vi.fn(),
  getPricingEvidence: vi.fn(),
  parsePricingEvidenceCaptureDraft: vi.fn()
}));

vi.mock("../api/comparables", () => ({
  createComparable: (...args: unknown[]) => mocks.createComparable(...args)
}));

vi.mock("../api/pricingEvidence", () => ({
  getPricingEvidence: (...args: unknown[]) => mocks.getPricingEvidence(...args),
  parsePricingEvidenceCaptureDraft: (...args: unknown[]) => mocks.parsePricingEvidenceCaptureDraft(...args)
}));

const pricingEvidence: PricingEvidence = {
  item: "item-1",
  currency: "AUD",
  source_links: [
    {
      id: "ebay_sold",
      label: "eBay sold",
      source_tag: "ebay_sold",
      query: "Australia 1937 Crown",
      url: "https://www.ebay.com.au/sch/i.html?_nkw=Australia%201937%20Crown&LH_Sold=1&LH_Complete=1",
      note: "Sold/completed eBay AU results. Magpie opens the URL only.",
      primary: true
    },
    {
      id: "facebook_marketplace",
      label: "Facebook Marketplace",
      source_tag: "facebook_marketplace",
      query: "Australia 1937 Crown",
      url: "https://www.facebook.com/marketplace/search/?query=Australia%201937%20Crown",
      note: "View-only marketplace search.",
      primary: false
    }
  ],
  headline: [
    {
      id: "sale-exact",
      record_type: "sale",
      own_sale: true,
      match_scope: "exact",
      match_reason: "same inventory item",
      date: "2026-06-10",
      title: "1937 Australian Crown",
      sku: "COIN-00001",
      source_tag: "own_sale",
      source_label: "Own sale",
      condition: "good",
      grade: "VF",
      sale_format: "auction",
      price: "70.00",
      price_basis: "seller_receives",
      canonical_price: "70.00",
      basis_uncertain: false,
      basis_label: "Seller receives",
      currency: "AUD",
      quantity: 1,
      url: "",
      notes: ""
    },
    {
      id: "sale-similar",
      record_type: "sale",
      own_sale: true,
      match_scope: "similar",
      match_reason: "same category; same denomination; same year",
      date: "2026-06-11",
      title: "1937 Crown second example",
      sku: "COIN-00002",
      source_tag: "own_sale",
      source_label: "Own sale",
      condition: "good",
      grade: "VF",
      sale_format: "fixed_price",
      price: "55.00",
      price_basis: "seller_receives",
      canonical_price: "55.00",
      basis_uncertain: false,
      basis_label: "Seller receives",
      currency: "AUD",
      quantity: 1,
      url: "",
      notes: ""
    }
  ],
  own_sales: [],
  comparables: [],
  grids: {
    condition_grade: [
      { key: "good / VF", label: "Good / VF", low: "55.00", median: "62.50", high: "70.00", count: 2, basis_uncertain_count: 0, own_sale_count: 2, thin: true }
    ],
    sale_format: [
      { key: "auction", label: "Auction", low: "70.00", median: "70.00", high: "70.00", count: 1, basis_uncertain_count: 0, own_sale_count: 1, thin: true }
    ],
    recency: [
      { key: "0-90 days", label: "0-90 Days", low: "55.00", median: "62.50", high: "70.00", count: 2, basis_uncertain_count: 0, own_sale_count: 2, thin: true }
    ],
    source: [
      { key: "own_sale", label: "Own Sale", low: "55.00", median: "62.50", high: "70.00", count: 2, basis_uncertain_count: 0, own_sale_count: 2, thin: true }
    ]
  },
  summary: {
    evidence_count: 2,
    priced_count: 2,
    precise_priced_count: 2,
    basis_uncertain_count: 0,
    own_sale_count: 2,
    comparable_count: 0,
    exact_count: 1,
    similar_count: 1,
    thin: true,
    empty: false
  },
  empty_state: {
    title: "Thin pricing evidence",
    detail: "Treat this as a ledger of evidence, not a price estimate."
  }
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getPricingEvidence.mockResolvedValue(pricingEvidence);
  mocks.createComparable.mockResolvedValue({ id: "comp-1" });
  mocks.parsePricingEvidenceCaptureDraft.mockResolvedValue({
    available: true,
    ocr_available: true,
    detail: "Capture form filled from your screenshot. Review it, then press Add to grid to save evidence.",
    draft: {
      title: "1954 *M/Y ASTERISK $1.00 BC-37bA * SCARCE Elizabeth II Bank of Canada",
      price: "11.13",
      price_basis: "buyer_visible",
      shipping: "24.29",
      source: "eBay sold",
      source_tag: "ebay_sold",
      url: "https://ebay.io/m/gPzKet",
      observed_on: "2026-06-14",
      condition: "",
      grade: "",
      sale_format: "fixed_price",
      match_scope: "exact",
      match_reason: "user-selected sold-result screenshot; review exactness"
    },
    parsed_from: ["link", "screenshot"],
    warnings: []
  });
});

test("PricingEvidencePanel renders outbound source links and own-sales-first rows", async () => {
  renderWithClient(<PricingEvidencePanel itemId="item-1" />);

  const ebay = await screen.findByRole("link", { name: /eBay sold/i });
  expect(ebay).toHaveAttribute("href", expect.stringContaining("www.ebay.com.au"));
  expect(ebay).toHaveAttribute("href", expect.stringContaining("LH_Sold=1"));
  expect(ebay).toHaveAttribute("target", "_blank");
  expect(screen.getByRole("link", { name: /Facebook Marketplace/i })).toHaveAttribute("target", "_blank");

  const rows = screen.getAllByRole("row");
  expect(within(rows[1]).getByText("1937 Australian Crown")).toBeInTheDocument();
  expect(within(rows[2]).getByText("1937 Crown second example")).toBeInTheDocument();
  expect(screen.getAllByText("Own sale").length).toBeGreaterThan(0);
  expect(screen.getByText(/same category; same denomination; same year/i)).toBeInTheDocument();
  expect(screen.getByText("Thin sample. Treat the table as evidence, not a valuation.")).toBeInTheDocument();
});

test("PricingEvidencePanel captures a source-tagged comparable into the grid", async () => {
  renderWithClient(<PricingEvidencePanel itemId="item-1" />);

  await screen.findByText("Capture verified comp");
  fireEvent.change(screen.getByLabelText("Source tag"), { target: { value: "price_guide" } });
  fireEvent.change(screen.getByLabelText("Source label"), { target: { value: "WorthPoint manual capture" } });
  fireEvent.change(screen.getByLabelText("Sold price"), { target: { value: "65" } });
  fireEvent.change(screen.getByLabelText("Price basis"), { target: { value: "seller_receives" } });
  fireEvent.change(screen.getByLabelText("Shipping"), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText("Format"), { target: { value: "dealer" } });
  fireEvent.change(screen.getByLabelText("Match"), { target: { value: "similar" } });
  fireEvent.change(screen.getByLabelText("Condition"), { target: { value: "good" } });
  fireEvent.change(screen.getByLabelText("Grade"), { target: { value: "VF" } });
  fireEvent.change(screen.getByLabelText("Evidence URL"), { target: { value: "https://www.worthpoint.com/inventory/search?query=1937%20crown" } });
  fireEvent.change(screen.getByLabelText("Title"), { target: { value: "1937 Australian Crown VF sold result" } });
  fireEvent.change(screen.getByLabelText("Match reason"), { target: { value: "same category; same denomination; same year" } });
  fireEvent.click(screen.getByRole("button", { name: /Add to grid/i }));

  await waitFor(() => expect(mocks.createComparable).toHaveBeenCalledWith(expect.objectContaining({
    item: "item-1",
    kind: "sold",
    source_tag: "price_guide",
    source: "WorthPoint manual capture",
    sale_format: "dealer",
    match_scope: "similar",
    match_reason: "same category; same denomination; same year",
    price_basis: "seller_receives",
    price: "65"
  })));
});

test("PricingEvidencePanel fills the comparable form from a user screenshot and link", async () => {
  renderWithClient(<PricingEvidencePanel itemId="item-1" />);

  await screen.findByText("Fill capture form from screenshot or link");
  fireEvent.change(screen.getByLabelText("Evidence link"), { target: { value: "https://ebay.io/m/gPzKet" } });
  fireEvent.change(screen.getByLabelText("Sold-result screenshot"), {
    target: { files: [new File(["fake screenshot"], "ebay-sold.png", { type: "image/png" })] }
  });
  fireEvent.change(screen.getByLabelText("Text copied from screenshot"), {
    target: { value: "SOLD 14 JUN 2026 1954 note AU $11.13 +AU $24.29 delivery" }
  });
  fireEvent.click(screen.getByRole("button", { name: /Fill capture form/i }));

  await waitFor(() => expect(mocks.parsePricingEvidenceCaptureDraft).toHaveBeenCalledWith("item-1", expect.objectContaining({
    url: "https://ebay.io/m/gPzKet",
    screenshot: expect.any(File),
    screenshotText: "SOLD 14 JUN 2026 1954 note AU $11.13 +AU $24.29 delivery"
  })));
  expect(await screen.findByText(/Capture form filled from your screenshot/i)).toBeInTheDocument();
  expect(screen.getByLabelText("Source label")).toHaveValue("eBay sold");
  expect(screen.getByLabelText("Sold price")).toHaveValue("11.13");
  expect(screen.getByLabelText("Price basis")).toHaveValue("buyer_visible");
  expect(screen.getByLabelText("Shipping")).toHaveValue("24.29");
  expect(screen.getByLabelText("Observed on")).toHaveValue("2026-06-14");
  expect(screen.getByLabelText("Evidence URL")).toHaveValue("https://ebay.io/m/gPzKet");
  expect(screen.getByLabelText("Title")).toHaveValue("1954 *M/Y ASTERISK $1.00 BC-37bA * SCARCE Elizabeth II Bank of Canada");

  fireEvent.click(screen.getByRole("button", { name: /Add to grid/i }));

  await waitFor(() => expect(mocks.createComparable).toHaveBeenCalledWith(expect.objectContaining({
    item: "item-1",
    source: "eBay sold",
    source_tag: "ebay_sold",
    title: "1954 *M/Y ASTERISK $1.00 BC-37bA * SCARCE Elizabeth II Bank of Canada",
    price: "11.13",
    price_basis: "buyer_visible",
    shipping: "24.29",
    observed_on: "2026-06-14",
    url: "https://ebay.io/m/gPzKet"
  })));
});

test("PricingEvidencePanel renders empty state honestly", async () => {
  mocks.getPricingEvidence.mockResolvedValue({
    ...pricingEvidence,
    headline: [],
    grids: { condition_grade: [], sale_format: [], recency: [], source: [] },
    summary: { ...pricingEvidence.summary, evidence_count: 0, priced_count: 0, precise_priced_count: 0, basis_uncertain_count: 0, own_sale_count: 0, exact_count: 0, similar_count: 0, thin: true, empty: true },
    empty_state: {
      title: "No pricing evidence yet",
      detail: "Open a source link, record a verified sold result, or sell this item and the pricing grid will fill from real evidence."
    }
  });

  renderWithClient(<PricingEvidencePanel itemId="item-1" />);

  expect(await screen.findByText("No pricing evidence yet")).toBeInTheDocument();
  expect(screen.getAllByText("No priced evidence yet.").length).toBeGreaterThan(0);
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
