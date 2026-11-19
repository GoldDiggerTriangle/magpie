import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import type { EbayQuantityState } from "../api/ebayQuantity";
import { EbayQuantityPanel } from "./EbayQuantityPanel";

test("stock refresh keeps a dirty target but invalidates its confirmation and blocks an invalid increase", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><EbayQuantityPanel itemId="item" /></MemoryRouter></QueryClientProvider>);
  const input = await screen.findByRole("spinbutton", { name: "Intended eBay quantity" });
  fireEvent.change(input, { target: { value: "2" } });
  await userEvent.click(screen.getByRole("checkbox"));
  await act(async () => { client.setQueryData(["ebay-quantity", "item"], { ...state, target: 1, remaining: 1, stock_revision: 3 }); });
  expect(input).toHaveValue(2);
  await waitFor(() => expect(screen.getByRole("checkbox")).not.toBeChecked());
  expect(screen.getByText(/1 known remaining/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Update quantity on eBay" })).toBeDisabled();
  expect(mocks.update).not.toHaveBeenCalled();
});

const mocks = vi.hoisted(() => ({ get: vi.fn(), check: vi.fn(), update: vi.fn() }));
vi.mock("../api/ebayQuantity", () => ({ getEbayQuantity: (...a: unknown[]) => mocks.get(...a), checkEbayQuantity: (...a: unknown[]) => mocks.check(...a), updateEbayQuantity: (...a: unknown[]) => mocks.update(...a) }));
const state: EbayQuantityState = { item_id: "item", sku: "OWN-00001", state: "update_required", label: "Update eBay: 5 -> 3", urgent: true,
  can_write: true, allocation_id: "allocation", allocated: 5, target: 3, remaining: 3, inventory_available: 5, offer_available: 5,
  pending_units: 0, unlinked_orders: 0, stock_revision: 2, allocation_revision: 1, stock_fingerprint: "reviewed-stock" };
beforeEach(() => { vi.clearAllMocks(); mocks.get.mockResolvedValue(state); mocks.check.mockResolvedValue(state); mocks.update.mockResolvedValue({ ...state, state: "verified", label: "eBay stock allocation", urgent: false, inventory_available: 3, offer_available: 3 }); });
function open() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter><EbayQuantityPanel itemId="item" /></MemoryRouter></QueryClientProvider>); }

test("legacy allocation not recorded has no warning or write controls and no check on mount", async () => {
  mocks.get.mockResolvedValue({ item_id: "item", sku: "GOLD-00002", state: "allocation_not_recorded", label: "Allocation not recorded", urgent: false, can_write: false });
  open(); expect(await screen.findByText("eBay listing quantity was not recorded")).toBeVisible();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(mocks.check).not.toHaveBeenCalled(); expect(mocks.update).not.toHaveBeenCalled();
});
test("exact reduction needs explicit checkbox and click; sent review is unchanged", async () => {
  open(); const button = await screen.findByRole("button", { name: "Update quantity on eBay" });
  expect(button).toBeDisabled(); expect(mocks.update).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("checkbox", { name: "Confirm this exact quantity change" }));
  await userEvent.click(button);
  await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(state, 3));
});
test("unknown outcome offers reconcile, never another write", async () => {
  mocks.get.mockResolvedValue({ ...state, state: "unknown", label: "Check quantity result; do not retry", can_write: false, attempt_id: "attempt" });
  open(); expect(await screen.findByRole("button", { name: "Reconcile quantity result" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Update quantity on eBay" })).not.toBeInTheDocument();
  expect(mocks.update).not.toHaveBeenCalled();
});
test("zero remaining links to existing take-down checklist", async () => {
  mocks.get.mockResolvedValue({ ...state, state: "take_down", remaining: 0, target: 0, can_write: false });
  open(); expect(await screen.findByRole("link", { name: "Open take-down checklist" })).toHaveAttribute("href", "/listings");
  expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
});
test("restock is never automatic and a human edit needs fresh confirmation", async () => {
  mocks.get.mockResolvedValue({ ...state, target: 3, remaining: 8 }); open();
  const input = await screen.findByRole("spinbutton", { name: "Intended eBay quantity" });
  await userEvent.click(screen.getByRole("checkbox")); await userEvent.clear(input); await userEvent.type(input, "7");
  expect(screen.getByRole("checkbox")).not.toBeChecked();
  expect(screen.getByText(/Restock increase/)).toBeVisible(); expect(mocks.update).not.toHaveBeenCalled();
});
