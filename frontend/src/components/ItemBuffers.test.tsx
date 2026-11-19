import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { test, expect, vi } from "vitest";
import type { InventoryItemDetail } from "../types";
import source from "../fixtures/listingEditor.json";
import { ProfitBreakdown } from "./ProfitBreakdown";
import { SalesPanel } from "./SalesPanel";
import { ComparableForm } from "./ComparableForm";

vi.mock("../api/sales", () => ({ listItemSales: () => Promise.resolve({ results: [] }), createItemSale: vi.fn(), correctSaleRecord: vi.fn() }));
vi.mock("../api/listing", () => ({ listItemListingDrafts: () => Promise.resolve({ results: [] }) }));
const item = { ...source.item, acquisition_cost: "10.00", est_packaging_cost: "2.00", current_valuation: null } as unknown as InventoryItemDetail;
test("cost inputs preserve dirty values while fresh clean costs update", () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><ProfitBreakdown item={item} reportId={null} /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Acquisition"), { target: { value: "99.00" } });
  view.rerender(<QueryClientProvider client={client}><ProfitBreakdown item={{ ...item, acquisition_cost: "15.00", est_packaging_cost: "3.00" }} reportId={null} /></QueryClientProvider>);
  expect(screen.getByLabelText("Acquisition")).toHaveValue("99.00");
  expect(screen.getByLabelText("Packaging")).toHaveValue("3.00");
});
test("sale price and notes survive a stock refresh while quantity is revalidated", () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><SalesPanel item={{ ...item, quantity_remaining: 2 }} /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Sale price"), { target: { value: "18.00" } });
  fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "Pending sale" } });
  view.rerender(<QueryClientProvider client={client}><SalesPanel item={{ ...item, quantity_remaining: 0, quantity_sold: 2 }} /></QueryClientProvider>);
  expect(screen.getByLabelText("Sale price")).toHaveValue("18.00");
  expect(screen.getByLabelText("Notes")).toHaveValue("Pending sale");
  expect(screen.getByRole("button", { name: "Record sale" })).toBeDisabled();
});
test("comparable editing retains dirty notes across refresh and changes identity deliberately", () => {
  const initial = { id: "comp-one", kind: "sold", source: "Owner", title: "Saved", price: "5.00", price_basis: "seller_receives", shipping: null, currency: "AUD", condition: "good", url: "", observed_on: null, notes: "" } as never;
  const view = render(<ComparableForm itemId="item-one" initial={initial} onSubmit={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "Pending note" } });
  view.rerender(<ComparableForm itemId="item-one" initial={{ ...initial as object, title: "New title", notes: "Remote note" } as never} onSubmit={vi.fn()} />);
  expect(screen.getByLabelText("Notes")).toHaveValue("Pending note");
  expect(screen.getByLabelText("Title")).toHaveValue("New title");
});
