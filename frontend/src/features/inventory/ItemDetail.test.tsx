import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, vi } from "vitest";

import { ItemDetail } from "./ItemDetail";
import type { InventoryItemDetail } from "../../types";

const mocks = vi.hoisted(() => ({
  getItem: vi.fn(),
  listCategories: vi.fn(),
  getCategorySchema: vi.fn(),
  listLocations: vi.fn(),
  listLots: vi.fn(),
  listSources: vi.fn(),
  updateItem: vi.fn()
}));

vi.mock("../../api/items", () => ({
  deleteItem: vi.fn(),
  getItem: (...args: unknown[]) => mocks.getItem(...args),
  reorderPhotos: vi.fn(),
  updateItem: (...args: unknown[]) => mocks.updateItem(...args),
  uploadItemPhoto: vi.fn()
}));

vi.mock("../../api/categories", () => ({
  listCategories: (...args: unknown[]) => mocks.listCategories(...args),
  getCategorySchema: (...args: unknown[]) => mocks.getCategorySchema(...args)
}));

vi.mock("../../api/locations", () => ({
  listLocations: (...args: unknown[]) => mocks.listLocations(...args)
}));

vi.mock("../../api/lots", () => ({
  listLots: (...args: unknown[]) => mocks.listLots(...args),
  listSources: (...args: unknown[]) => mocks.listSources(...args)
}));

vi.mock("../../api/photos", () => ({
  deletePhoto: vi.fn(),
  updatePhoto: vi.fn()
}));

vi.mock("../../components/AIResearchPanel", () => ({
  AIResearchPanel: ({ onReviewSuggestions }: { onReviewSuggestions?: () => void }) => (
    <button onClick={onReviewSuggestions} type="button">Review staged suggestions mock</button>
  )
}));
vi.mock("../../components/ComparableList", () => ({ ComparableList: () => null }));
vi.mock("../../components/CopyPackPanel", () => ({ CopyPackPanel: () => null }));
vi.mock("../../components/DescriptorEvidencePanel", () => ({ DescriptorEvidencePanel: () => null }));
vi.mock("../../components/ListingPanel", () => ({ ListingPanel: () => null }));
vi.mock("../../components/PhotoFixupPanel", () => ({ PhotoFixupPanel: () => null }));
vi.mock("../../components/PhotoGallery", () => ({ PhotoGallery: () => <div data-testid="photo-gallery" /> }));
vi.mock("../../components/PricingEvidencePanel", () => ({ PricingEvidencePanel: () => null }));
vi.mock("../../components/ProfitBreakdown", () => ({ ProfitBreakdown: () => null }));
vi.mock("../../components/ResearchLinks", () => ({ ResearchLinks: () => null }));
vi.mock("../../components/ResearchLog", () => ({ ResearchLog: () => null }));
vi.mock("../../components/SalesPanel", () => ({ SalesPanel: () => null }));
vi.mock("../../components/SoldSearchPanel", () => ({ SoldSearchPanel: () => null }));
vi.mock("../../components/SuggestionReviewPanel", () => ({ SuggestionReviewPanel: () => <div data-testid="suggestion-review-panel">Suggestion review panel</div> }));
vi.mock("../../components/TakeDownChecklist", () => ({ TakeDownChecklist: () => null }));
vi.mock("../../components/ValuationPanel", () => ({ ValuationPanel: () => null }));

const item: InventoryItemDetail = {
  id: "item-1",
  sku: "NOTE-00001",
  title: "Australian $10 banknote",
  status: "captured",
  condition: "good",
  category: "cat-banknotes",
  category_name: "Banknotes",
  lot: null,
  source: null,
  source_name: null,
  disposition: "for_sale",
  scrapped_at: null,
  quantity_total: 1,
  quantity_sold: 0,
  quantity_remaining: 1,
  estimated_value: null,
  currency: "AUD",
  main_thumb_url: null,
  created_at: "2026-07-01T00:00:00Z",
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
  effective_source: null,
  updated_at: "2026-07-01T00:00:00Z"
};

beforeEach(() => {
  localStorage.clear();
  mocks.getItem.mockResolvedValue(item);
  mocks.listCategories.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.listLocations.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.listLots.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.listSources.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.getCategorySchema.mockResolvedValue({ profile_key: "", fields: [] });
  mocks.updateItem.mockResolvedValue(item);
});

function renderItemDetail(initialEntry = "/inventory/item-1") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/inventory/:id" element={<ItemDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

test("ItemDetail edit exposes separate camera and library photo inputs", async () => {
  renderItemDetail();

  const takePhoto = await screen.findByLabelText(/take photo/i);
  const library = screen.getByLabelText(/choose from library/i);

  expect(takePhoto).toHaveAttribute("capture", "environment");
  expect(library).not.toHaveAttribute("capture");
  expect(library).toHaveAttribute("multiple");
});

test("ItemDetail edit saves banknote picker selections and custom country values", async () => {
  mocks.listCategories.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{
      id: "cat-banknotes",
      name: "Banknotes",
      slug: "banknotes",
      parent: null,
      sku_prefix: "NOTE",
      profile_key: "banknotes",
      description: ""
    }]
  });
  mocks.getCategorySchema.mockResolvedValue({
    profile_key: "banknotes",
    fields: [
      {
        name: "country",
        label: "Country",
        type: "str",
        required: false,
        choices: [],
        min: null,
        max: null,
        help_text: "",
        suggestions: ["Australia", "Canada", "Rhodesia"]
      },
      {
        name: "denomination",
        label: "Denomination",
        type: "str",
        required: false,
        choices: [],
        min: null,
        max: null,
        help_text: "",
        suggestions: ["$1", "$2", "$5", "$10", "$20"]
      }
    ]
  });
  const user = userEvent.setup();
  renderItemDetail();

  await user.selectOptions(await screen.findByLabelText("Denomination"), "$20");
  await user.selectOptions(screen.getByLabelText("Country"), "__custom__");
  await user.type(screen.getByLabelText("Country custom value"), "Rhodesia");
  await user.click(screen.getByRole("button", { name: /^save$/i }));

  await waitFor(() => {
    expect(mocks.updateItem).toHaveBeenCalledWith("item-1", expect.objectContaining({
      attributes: {
        country: "Rhodesia",
        denomination: "$20"
      }
    }));
  });
});

test("ItemDetail sections default open state, expand all, collapse all, and persisted state", async () => {
  const user = userEvent.setup();
  const view = renderItemDetail();

  expect(await screen.findByTestId("photo-gallery")).toBeVisible();
  expect(screen.getByLabelText("Title")).toBeVisible();
  expect(screen.getByLabelText("Lot")).not.toBeVisible();

  const categoryHeader = screen.getAllByRole("button", { name: "Category specifics" })
    .find((button) => button.getAttribute("aria-controls") === "category-specifics-panel");
  expect(categoryHeader).toBeDefined();
  await user.click(categoryHeader as HTMLElement);
  expect(screen.getByLabelText("Lot")).toBeVisible();
  view.unmount();

  renderItemDetail();
  expect(await screen.findByLabelText("Lot")).toBeVisible();

  await user.click(screen.getByRole("button", { name: "Collapse all" }));
  expect(screen.getByTestId("photo-gallery")).not.toBeVisible();
  await user.click(screen.getByRole("button", { name: "Expand all" }));
  expect(await screen.findByTestId("suggestion-review-panel")).toBeVisible();
});

test("ItemDetail desktop section index jumps and expands the AI review section", async () => {
  const user = userEvent.setup();
  renderItemDetail();

  const aiButtons = await screen.findAllByRole("button", { name: "AI research" });
  await user.click(aiButtons[0]);
  expect(screen.getByTestId("suggestion-review-panel")).toBeVisible();

  await user.click(screen.getByRole("button", { name: "Review staged suggestions mock" }));
  expect(window.location.hash).toBe("#ai-review");
  expect(screen.getByTestId("suggestion-review-panel")).toBeVisible();
});

test("ItemDetail deep link opens the AI review section", async () => {
  renderItemDetail("/inventory/item-1#ai-review");

  expect(await screen.findByTestId("suggestion-review-panel")).toBeVisible();
});
