import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import fixture from "../fixtures/listingEditor.json";
import type { InventoryItemDetail } from "../types";
import { EbayListingEntry } from "./EbayListingEntry";

const mocks = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn() }));
vi.mock("../api/listing", () => ({ listItemListingDrafts: (...a: unknown[]) => mocks.list(...a), createItemListingDraft: (...a: unknown[]) => mocks.create(...a) }));
beforeEach(() => { vi.clearAllMocks(); mocks.list.mockResolvedValue({ results: [fixture.draft] }); mocks.create.mockResolvedValue(fixture.draft); });
function open() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><EbayListingEntry item={fixture.item as unknown as InventoryItemDetail} /></QueryClientProvider>); }
test("top entry reuses canonical draft without writes on mount or opening an existing one", async () => {
  const event = vi.fn(); window.addEventListener(`magpie:open-draft:${fixture.item.id}`, event);
  open(); await waitFor(() => expect(screen.getByRole("button", { name: "List on eBay" })).toBeEnabled());
  expect(mocks.create).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "List on eBay" }));
  expect(event.mock.calls[0][0].detail.draftId).toBe(fixture.draft.id);
  expect(mocks.create).not.toHaveBeenCalled();
  window.removeEventListener(`magpie:open-draft:${fixture.item.id}`, event);
});
test("no draft is created until the human clicks", async () => {
  mocks.list.mockResolvedValue({ results: [] }); open();
  await waitFor(() => expect(screen.getByRole("button", { name: "List on eBay" })).toBeEnabled());
  expect(mocks.create).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "List on eBay" }));
  await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(fixture.item.id));
});
test("published history never conceals the active draft; live link stays separate", async () => {
  mocks.list.mockResolvedValue({ results: [{ ...fixture.draft, id: "history", status: "published", channel_data: { listing_id: "123" } }, fixture.draft] });
  open(); expect(await screen.findByText("staged", { exact: true })).toBeVisible();
  expect(screen.getByRole("link", { name: "View on eBay" })).toHaveAttribute("href", "https://www.ebay.com.au/itm/123");
});
test("unavailable draft status cannot be mistaken for no draft", async () => {
  mocks.list.mockRejectedValue(new Error("Session expired")); open();
  expect(await screen.findByRole("alert")).toHaveTextContent("could not load");
  expect(screen.getByRole("button", { name: "List on eBay" })).toBeDisabled();
  expect(mocks.create).not.toHaveBeenCalled();
});
