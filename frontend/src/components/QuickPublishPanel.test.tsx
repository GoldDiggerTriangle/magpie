import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import fixture from "../fixtures/listingEditor.json";
import type { InventoryItemDetail } from "../types";
import { QuickPublishPanel } from "./QuickPublishPanel";

const mocks = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), review: vi.fn(), publish: vi.fn(), stage: vi.fn() }));
vi.mock("../api/listing", () => ({ listItemListingDrafts: (...a: unknown[]) => mocks.list(...a), createItemListingDraft: (...a: unknown[]) => mocks.create(...a), publishListingDraft: (...a: unknown[]) => mocks.publish(...a), stageListingDraft: (...a: unknown[]) => mocks.stage(...a), withdrawListingDraft: vi.fn() }));
vi.mock("../api/listingWorkflow", () => ({ reviewListing: (...a: unknown[]) => mocks.review(...a), reconcileListing: vi.fn() }));
beforeEach(() => { vi.clearAllMocks(); mocks.list.mockResolvedValue({ results: [fixture.draft] }); mocks.create.mockResolvedValue(fixture.draft); });
function open() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><QuickPublishPanel item={fixture.item as unknown as InventoryItemDetail} /></QueryClientProvider>); }
test("quick entry reuses canonical draft without staging, editing or posting on mount", async () => {
  open(); await screen.findByRole("button", { name: "Open eBay draft" });
  expect(mocks.create).not.toHaveBeenCalled(); expect(mocks.review).not.toHaveBeenCalled(); expect(mocks.stage).not.toHaveBeenCalled(); expect(mocks.publish).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Open eBay draft" }));
  await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(fixture.item.id));
});
test("quick preview requests the same server-bound review, not a private price/draft pipeline", async () => {
  mocks.review.mockRejectedValue(new Error("Live metadata unavailable; nothing published"));
  open(); await userEvent.click(await screen.findByRole("button", { name: "Preview eBay listing" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Live metadata unavailable");
  expect(mocks.review).toHaveBeenCalledWith(fixture.draft.id, "quick");
  expect(mocks.stage).not.toHaveBeenCalled(); expect(mocks.publish).not.toHaveBeenCalled();
});
