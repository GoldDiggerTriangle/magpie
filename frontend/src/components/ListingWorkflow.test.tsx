import { act, render, screen, waitFor, within } from "@testing-library/react";
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
  expect(screen.getAllByText("Insertion Fee: $0.06")[0]).toBeVisible();
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

test("preview preserves description headings, paragraphs and breaks without active HTML", async () => {
  draft.description_html = "<h2>Overview</h2><p>Own nugget.<br>Wear retained.</p><h3>Details</h3><p>Second paragraph.</p><img src='https://example.invalid/tracker'><script>window.injected = true</script>";
  review.listing.description_html = draft.description_html;
  review.specifics = [{ name: "Metal", value: "Gold" }, { name: "Form", value: "Nugget" }, { name: "Weight", value: "1.4 g" }];
  draft.item_specifics = review.specifics;
  open(); await userEvent.click(screen.getByRole("button", { name: "Review listing" }));
  const description = await screen.findByLabelText("Listing description");
  expect(within(description).getByRole("heading", { name: "Overview", level: 2 })).toBeVisible();
  expect(within(description).getByRole("heading", { name: "Details", level: 3 })).toBeVisible();
  expect(description.querySelectorAll("p")).toHaveLength(2);
  expect(description.querySelector("br")).not.toBeNull();
  expect(description.querySelector("img,script")).toBeNull();
  const specifics = screen.getByLabelText("Item specifics");
  expect(specifics.children[0]).toHaveTextContent("Metal: Gold");
  expect(specifics.children[1]).toHaveTextContent("Form: Nugget");
  expect(specifics.children[2]).toHaveTextContent("Weight: 1.4 g");
});

test("fee estimate shows nonzero fees and exact total with full breakdown collapsed", async () => {
  review.fees = [{ type: "InsertionFee", currency: "AUD", value: "0.06" }, { type: "UpgradeFee", currency: "AUD", value: "0.10" }, { type: "GalleryFee", currency: "AUD", value: "0.00" }];
  open(); await userEvent.click(screen.getByRole("button", { name: "Review listing" }));
  expect(await screen.findByText("AUD listing fee total: $0.16")).toBeVisible();
  const zero = screen.getByText("Gallery Fee: $0.00");
  expect(zero).not.toBeVisible();
  const toggle = screen.getByText("Show all fees");
  expect(toggle.parentElement).not.toHaveAttribute("open");
  await userEvent.click(toggle);
  expect(toggle.parentElement).toHaveAttribute("open");
  expect(zero).toBeVisible();
  expect(screen.getByRole("heading", { name: "eBay listing fee estimate" }).parentElement?.querySelector(".font-mono")).toBeNull();
  expect(screen.getByText("Listing fees only; final selling fees depend on the sale.")).toBeVisible();
});

test("zero fees still show an honest zero total, without zero fee rows in the summary", async () => {
  review.fees = [{ type: "InsertionFee", currency: "AUD", value: "0" }];
  open(); await userEvent.click(screen.getByRole("button", { name: "Review listing" }));
  expect(await screen.findByText("AUD listing fee total: $0.00")).toBeVisible();
  expect(screen.getByText("Insertion Fee: $0.00")).not.toBeVisible();
});

test("repeated photo blockers group once and drift jumps to Update staged offer without staging", async () => {
  review.can_publish = false;
  review.publish_checks = [
    ...Array.from({ length: 6 }, () => ({ key: "photo_freshness", field: "photos", message: "Photo upload date unknown" })),
    { key: "staged_drift", field: "category_id", message: "Local staging is unverified" },
  ];
  open(); await userEvent.click(screen.getByRole("button", { name: "Review listing" }));
  expect(await screen.findByText("6 photos need re-uploading. Use Update staged offer.")).toBeVisible();
  expect(screen.queryByText("Photo upload date unknown")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Go to category id" })).not.toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("button", { name: "Go to Update staged offer" })[1]);
  await waitFor(() => expect(screen.getByRole("button", { name: "Update staged offer" })).toHaveFocus());
  expect(screen.getByLabelText("Reviewed listing")).toBeVisible();
  expect(mocks.stage).not.toHaveBeenCalled(); expect(mocks.publish).not.toHaveBeenCalled();
});

test.each(["title", "subtitle", "description_html", "est_shipping_note", "item_specifics"])("placeholder blocker jumps to the named %s editor field", async (fieldName) => {
  review.can_stage = false; review.can_publish = false;
  review.checks = [{ key: `placeholder:${fieldName}`, field: fieldName, message: "Remove PLACEHOLDER text before staging or publishing." }];
  const field = document.createElement("textarea"); field.id = `listing-${draft.id}-${fieldName}`; document.body.append(field);
  open(); await userEvent.click(screen.getByRole("button", { name: "Review listing" }));
  await userEvent.click(await screen.findByRole("button", { name: `Go to ${fieldName.replace(/_/g, " ")}` }));
  await waitFor(() => expect(field).toHaveFocus());
  expect(mocks.stage).not.toHaveBeenCalled(); expect(mocks.publish).not.toHaveBeenCalled(); field.remove();
});

test("reviewed revision renders the browser-local date and time, not ISO prose", async () => {
  open(); await userEvent.click(screen.getByRole("button", { name: "Review listing" }));
  await screen.findByLabelText("Reviewed listing");
  const time = document.querySelector("time");
  const expected = new Intl.DateTimeFormat("en-AU", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", hour12: true }).format(new Date(draft.updated_at));
  expect(time).toHaveTextContent(`Reviewed ${expected}`);
  expect(time).toHaveAttribute("dateTime", draft.updated_at);
  expect(screen.queryByText(`Reviewed revision ${draft.updated_at}`)).not.toBeInTheDocument();
});
