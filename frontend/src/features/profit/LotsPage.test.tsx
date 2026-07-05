import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import type { LotSummary } from "../../types";
import { LotDetail } from "./LotsPage";

const mocks = vi.hoisted(() => ({
  allocateLotEqual: vi.fn(),
  allocateLotManual: vi.fn(),
  allocateLotProportional: vi.fn(),
  createLot: vi.fn(),
  getLot: vi.fn(),
  listLots: vi.fn(),
  listSources: vi.fn(),
  scrapLotMember: vi.fn()
}));

vi.mock("../../api/lots", () => ({
  allocateLotEqual: (...args: unknown[]) => mocks.allocateLotEqual(...args),
  allocateLotManual: (...args: unknown[]) => mocks.allocateLotManual(...args),
  allocateLotProportional: (...args: unknown[]) => mocks.allocateLotProportional(...args),
  createLot: (...args: unknown[]) => mocks.createLot(...args),
  getLot: (...args: unknown[]) => mocks.getLot(...args),
  listLots: (...args: unknown[]) => mocks.listLots(...args),
  listSources: (...args: unknown[]) => mocks.listSources(...args),
  scrapLotMember: (...args: unknown[]) => mocks.scrapLotMember(...args)
}));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getLot.mockResolvedValue(sampleLot);
  mocks.allocateLotManual.mockResolvedValue({
    ...sampleLot,
    allocated: "100.00",
    unallocated: "0.00",
    tally_label: "allocated $100.00 of $100.00 · remainder $0.00",
    members: sampleLot.members.map((member) => member.id === "item-unsold" ? { ...member, acquisition_cost: "70.00" } : member)
  });
  mocks.scrapLotMember.mockResolvedValue(sampleLot);
});

test("LotDetail shows the live allocation tally and locked sold member", async () => {
  const user = userEvent.setup();
  renderWithClient(<LotDetail />, "/lots/lot-1");

  expect(await screen.findByText("Estate phone lot")).toBeInTheDocument();
  expect(screen.getByText("allocated $80.00 of $100.00 · remainder $20.00")).toBeInTheDocument();
  expect(screen.getByText("Partially allocated lot. Remainder stays visible until you finish.")).toBeInTheDocument();
  expect(screen.getByText(/sold · cost locked/i)).toBeInTheDocument();
  const shareInputs = screen.getAllByDisplayValue("40.00");
  expect(shareInputs[0]).toBeDisabled();
  expect(shareInputs[1]).not.toBeDisabled();

  const unlockedShare = shareInputs[1];
  await user.clear(unlockedShare);
  await user.type(unlockedShare, "60");

  expect(screen.getByText("allocated $100.00 of $100.00 · remainder $0.00")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Save manual allocation/i }));
  await waitFor(() => expect(mocks.allocateLotManual).toHaveBeenCalled());
});

const sampleLot: LotSummary = {
  id: "lot-1",
  label: "Estate phone lot",
  purchase_date: "2026-06-01",
  total_cost: "100.00",
  source: { id: "source-1", name: "Estate sale", type: "estate" },
  note: "",
  allocated: "80.00",
  unallocated: "20.00",
  is_partially_allocated: true,
  is_over_allocated: false,
  warning: "",
  tally_label: "allocated $80.00 of $100.00 · remainder $20.00",
  proportional_available: false,
  members: [
    {
      id: "item-sold",
      sku: "PH-00001",
      title: "Sold phone",
      category: "Phones",
      state: "sold",
      locked: true,
      quantity_sold: 1,
      acquisition_cost: "40.00",
      estimated_value: "80.00",
      scrapped_at: null,
      detail_url: "/inventory/item-sold"
    },
    {
      id: "item-unsold",
      sku: "PH-00002",
      title: "Unsold phone",
      category: "Phones",
      state: "unsold",
      locked: false,
      quantity_sold: 0,
      acquisition_cost: "40.00",
      estimated_value: null,
      scrapped_at: null,
      detail_url: "/inventory/item-unsold"
    }
  ],
  pnl: {
    total_cost: "100.00",
    allocated: "80.00",
    unallocated: "20.00",
    realised_revenue: "90.00",
    realised_profit: "50.00",
    remaining_cost_basis: "40.00",
    recovered_label: "recovered $90.00 of $100.00",
    is_loss: false,
    is_part_allocated: true
  }
};

function renderWithClient(ui: ReactElement, route = "/lots/lot-1") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/lots/:id" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}
