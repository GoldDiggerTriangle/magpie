import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import fixture from "../fixtures/listingEditor.json";
import type { InventoryItemDetail, ListingDraft } from "../types";
import type { ListingEditorContext } from "../api/listing";
import { ListingPanel } from "./ListingPanel";
import { useDraftAutosave } from "./useDraftAutosave";

const mocks = vi.hoisted(() => ({ get: vi.fn(), list: vi.fn(), save: vi.fn(), refresh: vi.fn(), stage: vi.fn(), publish: vi.fn(), aspects: vi.fn() }));
vi.mock("../api/listing", () => ({
  listItemListingDrafts: (...args: unknown[]) => mocks.list(...args),
  listListingBoilerplates: () => Promise.resolve({ results: [] }),
  getListingEditor: (...args: unknown[]) => mocks.get(...args),
  updateListingDraft: (...args: unknown[]) => mocks.save(...args),
  refreshListingMetadata: (...args: unknown[]) => mocks.refresh(...args),
  createItemListingDraft: () => Promise.resolve(fixture.draft), deleteListingDraft: vi.fn(), generateListingDraft: vi.fn(),
  getListingReadiness: vi.fn(), downloadListingZip: vi.fn(),
  getListingAspectCheck: (...args: unknown[]) => mocks.aspects(...args), getStagedOfferReview: vi.fn(),
  stageListingDraft: (...args: unknown[]) => mocks.stage(...args), publishListingDraft: (...args: unknown[]) => mocks.publish(...args), withdrawListingDraft: vi.fn()
}));
vi.mock("../api/ebay", () => ({ getEbayStatus: () => Promise.resolve({ connected: true }), getMerchantLocation: () => Promise.resolve({ location: null }), createMerchantLocation: vi.fn(), getEbayCategorySuggestions: vi.fn() }));

let draft: ListingDraft;
let context: ListingEditorContext;
const item = fixture.item as unknown as InventoryItemDetail;
beforeEach(() => {
  vi.clearAllMocks();
  draft = structuredClone(fixture.draft) as ListingDraft;
  context = structuredClone(fixture.editor) as ListingEditorContext;
  mocks.get.mockImplementation(async () => structuredClone(context));
  mocks.list.mockImplementation(async () => ({ results: [structuredClone(draft)] }));
  mocks.save.mockImplementation(async (_id, payload) => {
    const { expected_updated_at: _expected, editor_save: _mode, price_choice: _price, ...fields } = payload;
    draft = { ...draft, ...fields, updated_at: new Date().toISOString() };
    return structuredClone(draft);
  });
  mocks.refresh.mockImplementation(async () => ({ draft, editor: context }));
});

function open() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><ListingPanel item={item} /></QueryClientProvider>);
}

test("opens offline without autosave or remote inventory calls and explains staged local edits", async () => {
  open();
  expect(await screen.findByDisplayValue(draft.title)).toBeInTheDocument();
  expect(await screen.findByText("Not used by this category")).toBeInTheDocument();
  expect(screen.getByText(/Editing here stays local/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Re-stage offer" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Review & publish" })).toBeDisabled();
  expect(mocks.save).not.toHaveBeenCalled();
  expect(mocks.refresh).not.toHaveBeenCalled();
  expect(mocks.aspects).not.toHaveBeenCalled();
  expect(mocks.stage).not.toHaveBeenCalled();
  expect(mocks.publish).not.toHaveBeenCalled();
});

test("edits every listing field, autosaves full strings, and resumes after remount", async () => {
  const user = userEvent.setup();
  const view = open();
  await screen.findByDisplayValue(draft.title);
  const title = "Full Australian gold nugget title, not a fragment";
  fireEvent.change(screen.getByLabelText("Title", { exact: true }), { target: { value: title } });
  fireEvent.change(screen.getByLabelText("Subtitle"), { target: { value: "Human subtitle" } });
  fireEvent.change(screen.getByLabelText("Description"), { target: { value: "<p>Full human description.</p>" } });
  await user.selectOptions(screen.getByLabelText("Format"), "auction");
  await user.selectOptions(screen.getByLabelText("Duration"), "DAYS_7");
  fireEvent.change(screen.getByLabelText("Price"), { target: { value: "365.00" } });
  fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Shipping note"), { target: { value: "Human postage note" } });
  fireEvent.change(screen.getByLabelText("Metal (required by eBay)"), { target: { value: "Natural gold" } });
  await user.click(screen.getAllByTitle("Move down")[0]);
  await user.click(screen.getByLabelText("SKU footer"));
  await user.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(draft.title).toBe(title));
  expect(draft.description_html).toBe("<p>Full human description.</p>");
  expect(draft.channel_data.listing_duration).toBe("DAYS_7");
  expect(draft.price).toBe("365.00");
  expect(draft.photo_ids).toEqual(["photo-b", "photo-a"]);
  expect(draft.item_specifics).toContainEqual({ name: "Metal", value: "Natural gold" });
  expect(mocks.save).toHaveBeenLastCalledWith(draft.id, expect.objectContaining({ editor_save: true, price_choice: { kind: "human_asking" }, expected_updated_at: expect.any(String) }));
  view.unmount();
  open();
  expect(await screen.findByDisplayValue(title)).toBeInTheDocument();
  expect(screen.getByDisplayValue("Human subtitle")).toBeInTheDocument();
  expect(screen.getByDisplayValue("<p>Full human description.</p>")).toBeInTheDocument();
});

test("policy dropdowns show actual terms beside names and in selected terms", async () => {
  open();
  const postage = await screen.findByRole("combobox", { name: "Postage policy" });
  expect(within(postage).getByRole("option", { name: /Tracked parcel.*AUD 12.50.*2 day/ })).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "fulfillment policy terms" })).toHaveTextContent("AUD 12.50");
  expect(screen.getByRole("list", { name: "return policy terms" })).toHaveTextContent("Return postage: BUYER");
  expect(screen.getByRole("list", { name: "payment policy terms" })).toHaveTextContent("Immediate payment required");
});

test("price choices are explicit and send evidence identity, never an inferred value", async () => {
  const user = userEvent.setup();
  open();
  await user.selectOptions(await screen.findByLabelText("Pick an evidence price (seller receives)"), "comp:owned");
  await user.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(mocks.save).toHaveBeenCalledWith(draft.id, expect.objectContaining({ price: "350.00", price_choice: { kind: "owned_evidence", id: "comp:owned" } })));
  expect(screen.queryByRole("button", { name: "Regenerate price" })).not.toBeInTheDocument();
});

test("metadata refresh is explicit and never stages or publishes", async () => {
  const user = userEvent.setup();
  open();
  await user.click(await screen.findByRole("button", { name: "Refresh from eBay" }));
  await waitFor(() => expect(mocks.refresh).toHaveBeenCalledWith(draft.id, { category_id: "139965" }));
  expect(mocks.save).not.toHaveBeenCalled();
  expect(mocks.stage).not.toHaveBeenCalled();
  expect(mocks.publish).not.toHaveBeenCalled();
});

test("readiness jump focuses the exact blocking field", async () => {
  const user = userEvent.setup();
  context.checks = [{ key: "title_missing", level: "fail", message: "Title required", field: "title" }];
  open();
  await user.click(await screen.findByRole("button", { name: "Go to field" }));
  expect(screen.getByLabelText("Title", { exact: true })).toHaveFocus();
});

test("typing during an in-flight save is never replaced by the older response", async () => {
  let resolve: ((value: ListingDraft) => void) | undefined;
  mocks.save.mockImplementationOnce(() => new Promise<ListingDraft>((done) => { resolve = done; }));
  const user = userEvent.setup();
  open();
  const title = await screen.findByDisplayValue(draft.title);
  fireEvent.change(title, { target: { value: "First partial text" } });
  await user.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(resolve).toBeDefined());
  fireEvent.change(title, { target: { value: "Full second title must survive old response" } });
  await act(async () => resolve?.({ ...draft, title: "First partial text", updated_at: "2026-11-14T01:00:00Z" }));
  expect(title).toHaveValue("Full second title must survive old response");
  await waitFor(() => expect(mocks.save).toHaveBeenLastCalledWith(draft.id, expect.objectContaining({ title: "Full second title must survive old response", expected_updated_at: "2026-11-14T01:00:00Z" })));
});

test("failed autosave retains the typed text and shows a retryable error", async () => {
  mocks.save.mockRejectedValue(new Error("Draft changed elsewhere. Reload before saving."));
  const user = userEvent.setup();
  open();
  const title = await screen.findByDisplayValue(draft.title);
  fireEvent.change(title, { target: { value: "My full unsaved title" } });
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText(/Not saved: Draft changed elsewhere/)).toBeInTheDocument();
  expect(title).toHaveValue("My full unsaved title");
});

test("archived history has no editable fields or autosaves", async () => {
  draft.status = "archived";
  context.read_only = true;
  open();
  expect(await screen.findByDisplayValue(draft.title)).toBeDisabled();
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  expect(mocks.save).not.toHaveBeenCalled();
});

test("resuming accepts fresh server data when there are no unsaved edits", () => {
  const { result, rerender } = renderHook(({ value }) => useDraftAutosave(value, () => undefined, false), { initialProps: { value: draft } });
  rerender({ value: { ...draft, title: "Newly saved server title", updated_at: "2026-11-14T02:00:00Z" } });
  expect(result.current.local.title).toBe("Newly saved server title");
  expect(mocks.save).not.toHaveBeenCalled();
});

test("background refetch cannot replace unsaved title text", () => {
  const { result, rerender } = renderHook(({ value }) => useDraftAutosave(value, () => undefined, false), { initialProps: { value: draft } });
  act(() => result.current.setLocal({ ...draft, title: "My newer unsaved title" }));
  rerender({ value: { ...draft, title: "Older server title", updated_at: "2026-11-14T02:00:00Z" } });
  expect(result.current.local.title).toBe("My newer unsaved title");
});
