import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, vi } from "vitest";

import { ItemDetail } from "./ItemDetail";
import type { InventoryItemDetail } from "../../types";

const mocks = vi.hoisted(() => ({
  getItem: vi.fn(),
  listCategories: vi.fn(),
  listLocations: vi.fn(),
  listLots: vi.fn(),
  listSources: vi.fn()
}));

vi.mock("../../api/items", () => ({
  deleteItem: vi.fn(),
  getItem: (...args: unknown[]) => mocks.getItem(...args),
  reorderPhotos: vi.fn(),
  updateItem: vi.fn(),
  uploadItemPhoto: vi.fn()
}));

vi.mock("../../api/categories", () => ({
  listCategories: (...args: unknown[]) => mocks.listCategories(...args),
  getCategorySchema: vi.fn().mockResolvedValue({ profile_key: "", fields: [] })
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

vi.mock("../../components/AIResearchPanel", () => ({ AIResearchPanel: () => null }));
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
vi.mock("../../components/SuggestionReviewPanel", () => ({ SuggestionReviewPanel: () => null }));
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
  mocks.getItem.mockResolvedValue(item);
  mocks.listCategories.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.listLocations.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.listLots.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mocks.listSources.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
});

function renderItemDetail() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/inventory/item-1"]}>
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
