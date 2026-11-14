import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import fixture from "../fixtures/listingEditor.json";
import type { InventoryItemDetail, ListingDraft } from "../types";
import type { ListingReview } from "../api/listingWorkflow";
import { ListingWorkflow } from "./ListingWorkflow";

const mocks = vi.hoisted(() => ({ review: vi.fn(), publish: vi.fn(), stage: vi.fn(), remove: vi.fn(), reconcile: vi.fn() }));
vi.mock("../api/listing", () => ({ publishListingDraft: (...a: unknown[]) => mocks.publish(...a), stageListingDraft: (...a: unknown[]) => mocks.stage(...a), withdrawListingDraft: (...a: unknown[]) => mocks.remove(...a) }));
vi.mock("../api/listingWorkflow", () => ({ reviewListing: (...a: unknown[]) => mocks.review(...a), reconcileListing: (...a: unknown[]) => mocks.reconcile(...a) }));
let review: ListingReview;
let draft: ListingDraft;
const item = fixture.item as unknown as InventoryItemDetail;
beforeEach(() => {
  vi.clearAllMocks(); draft = structuredClone(fixture.draft) as ListingDraft;
  review = { id: "review-1", draft_revision: draft.updated_at, expires_at: "2099-01-01T00:00:00Z", mode: "full", offer_id: "offer-1", sku: item.sku, price: draft.price,
    listing: { title: draft.title, description_html: draft.description_html, listing_format: "fixed", quantity: 1, currency: "AUD" },
    sources: { price: "Human asking price", category_id: "from Gold defaults" }, mapping: draft.channel_data as Record<string, string>,
    specifics: draft.item_specifics, photos: draft.photo_ids.map((id) => ({ id, sha256: "owned-sha", derivative: "" })),
    metadata: { category_snapshot: { condition_policy: { required: false, conditions: [] } }, policies: { fulfillment: [{ id: "f4", name: "Tracked", terms: ["Australia Post: $23.95", "Handling: 2 business days"] }] } },
    checks: [], publish_checks: [], fees: [{ type: "InsertionFee", currency: "AUD", value: "0.06" }], can_stage: true, can_publish: true };
  mocks.review.mockImplementation(async () => structuredClone(review));
  mocks.publish.mockResolvedValue({ ...draft, status: "published" });
});
function open(mode: "full" | "quick" = "full", updated = vi.fn()) { return { updated, ...render(<ListingWorkflow draft={draft} item={item} mode={mode} onUpdated={updated} />) }; }
test("full path reviews exact values, policy terms, price source and fees before SKU confirmation", async () => {
  const { updated } = open();
  expect(mocks.publish).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Review listing" }));
  expect(await screen.findByText("Australia Post: $23.95")).toBeInTheDocument();
  expect(screen.getByText("Source: Human asking price")).toBeInTheDocument();
  expect(screen.getByText("InsertionFee: AUD 0.06")).toBeInTheDocument();
  const post = screen.getByRole("button", { name: "Confirm publish to eBay" });
  expect(post).toBeDisabled();
  await userEvent.type(screen.getByRole("textbox", { name: `Type ${item.sku} to confirm` }), item.sku);
  await userEvent.click(post);
  expect(mocks.publish).toHaveBeenCalledWith(draft.id, item.sku, { review_id: "review-1", mode: "full" });
  expect(updated).toHaveBeenCalled();
});
test("quick post has no SKU typing, no staging, and uses the exact reviewed revision", async () => {
  review.mode = "quick"; review.draft_revision = draft.updated_at.replace("Z", "+00:00"); open("quick");
  await userEvent.click(screen.getByRole("button", { name: "Preview eBay listing" }));
  await screen.findByText("Listing fees only; final selling fees depend on the sale.");
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Post live to eBay" }));
  expect(mocks.publish).toHaveBeenCalledWith(draft.id, "", { review_id: "review-1", mode: "quick" });
  expect(mocks.stage).not.toHaveBeenCalled();
});
test.each(["staged_drift", "photo_freshness", "price_source", "category_id", "fulfillment_policy", "ebay_condition"])("quick path cannot bypass %s blocker", async (key) => {
  review.mode = "quick"; review.can_publish = false; review.publish_checks = [{ key, field: "category_id", message: `Resolve ${key}` }];
  open("quick"); await userEvent.click(screen.getByRole("button", { name: "Preview eBay listing" }));
  expect(await screen.findByText(`Resolve ${key}`)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Post live to eBay" })).toBeDisabled();
  expect(mocks.stage).not.toHaveBeenCalled(); expect(mocks.publish).not.toHaveBeenCalled();
});
test("stage/update is an explicit click then a fresh staged review", async () => {
  review.can_publish = false; review.publish_checks = [{ key: "staged_drift", field: "title", message: "Local changes are not yet on eBay" }];
  mocks.stage.mockResolvedValue(draft);
  open(); await userEvent.click(screen.getByRole("button", { name: "Review listing" }));
  const update = await screen.findByRole("button", { name: "Update staged offer" });
  expect(mocks.stage).not.toHaveBeenCalled(); await userEvent.click(update);
  await waitFor(() => expect(mocks.review).toHaveBeenCalledTimes(2));
  expect(mocks.stage).toHaveBeenCalledWith(draft.id, { review_id: "review-1" }); expect(mocks.publish).not.toHaveBeenCalled();
});
test("blocker jumps to and focuses the field using the existing editor entry point", async () => {
  review.checks = [{ key: "category_id", field: "category_id", message: "Choose category" }]; review.can_publish = false;
  const handler = vi.fn(); window.addEventListener(`magpie:open-draft:${item.id}`, handler);
  const field = document.createElement("input"); field.id = `listing-${draft.id}-category_id`; document.body.append(field);
  open(); await userEvent.click(screen.getByRole("button", { name: "Review listing" }));
  await userEvent.click(await screen.findByRole("button", { name: "Go to category id" }));
  await waitFor(() => expect(field).toHaveFocus()); expect(handler).toHaveBeenCalled();
  field.remove(); window.removeEventListener(`magpie:open-draft:${item.id}`, handler);
});
test("unknown outcome offers reconcile only; no retry or remove control", async () => {
  draft.status = "publish_unknown"; mocks.reconcile.mockResolvedValue(draft); const { updated } = open();
  expect(screen.getByRole("button", { name: "Review listing" })).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Remove unpublished offer" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Reconcile offer" }));
  expect(updated).toHaveBeenCalledWith(draft); expect(mocks.publish).not.toHaveBeenCalled();
});
test("remove requires explicit confirmation and published history has no publish controls", async () => {
  mocks.remove.mockResolvedValue({ ...draft, channel_data: {} }); const { rerender, updated } = open();
  await userEvent.click(screen.getByRole("button", { name: "Remove unpublished offer" }));
  expect(mocks.remove).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Confirm removal" }));
  await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith(draft.id));
  act(() => rerender(<ListingWorkflow draft={{ ...draft, status: "published", channel_data: { listing_id: "123" } }} item={item} mode="full" onUpdated={updated} />));
  expect(screen.getByRole("link", { name: "Open live listing" })).toHaveAttribute("href", "https://www.ebay.com.au/itm/123");
  expect(screen.queryByRole("button", { name: "Review listing" })).not.toBeInTheDocument();
});

test("unsaved visible edits invalidate Post even before the server revision changes", async () => {
  review.mode = "quick"; const { rerender, updated } = open("quick");
  await userEvent.click(screen.getByRole("button", { name: "Preview eBay listing" }));
  expect(await screen.findByRole("button", { name: "Post live to eBay" })).toBeEnabled();
  rerender(<ListingWorkflow draft={{ ...draft, title: "Unsaved human title" }} item={item} mode="quick" onUpdated={updated} />);
  expect(screen.getByRole("button", { name: "Post live to eBay" })).toBeDisabled();
  expect(mocks.publish).not.toHaveBeenCalled();
});
