import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ItemDetail } from "./ItemDetail";
import { AppShell } from "../../components/AppShell";
import { EbayHub } from "../ebay/EbayHub";
import { listingStates, phase6Fixture, type ListingState } from "../../../e2e/phase6.fixture";

// No panel mocks: the real item page and every inventory/listing panel must remain reachable.
beforeEach(() => { localStorage.clear(); });
afterEach(() => vi.unstubAllGlobals());
function EvidenceDestination() {
  const location = useLocation();
  return <h1>Calculator evidence {location.state?.ownedEvidence?.rowId}</h1>;
}
function open(state: ListingState, route?: string, olderHistory = false, withEvidence = false) {
  const data = phase6Fixture(state);
  if (olderHistory) data.drafts.splice(0, 1);
  if (withEvidence) data.evidenceRows.push({ id: "sale:owned-1", record_type: "sale", source: "own_sale_exact", label: "Own exact sale", source_label: "Own sale", match_reason: "same item", seller_receives: "100.00", basis_uncertain: false, basis_label: "Seller receives", currency: "AUD", own_sale: true, date: "2026-11-01" });
  const errors: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => {
    try { return new Response(JSON.stringify(data.response(path, options?.method, options?.body ? JSON.parse(String(options.body)) : undefined)), { status: 200, headers: { "Content-Type": "application/json" } }); }
    catch (error) { errors.push(String(error)); return new Response("Unexpected synthetic request", { status: 500 }); }
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route ?? `/inventory/${data.item.id}`]}>
    <Routes><Route element={<AppShell />}><Route path="/inventory/:id" element={<ItemDetail />} /><Route path="/ebay" element={<EbayHub />} /><Route path="/settings/ebay" element={<h1>eBay Settings destination</h1>} /><Route path="/ebay/orders" element={<h1>Orders destination</h1>} /><Route path="/buy-calculator" element={<EvidenceDestination />} /></Route></Routes>
  </MemoryRouter></QueryClientProvider>);
  return { ...data, errors };
}

test.each(listingStates)("real-panel reachability gate: %s", async (state) => {
  const data = open(state);
  await screen.findByRole("heading", { name: data.item.title, level: 1 });
  await userEvent.click(screen.getByRole("button", { name: "Collapse all" }));
  const top = screen.getByRole("button", { name: "List on eBay" });
  await waitFor(() => expect(top).toBeEnabled());
  expect(top).toBeVisible();
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
  await userEvent.click(top);
  const section = document.getElementById("listings-channels-content") ?? document.querySelector(".listing-panel");
  expect(section).toBeVisible();
  expect(await screen.findByRole("heading", { name: "eBay listing editor" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Ready-to-paste ad copy" })).toBeVisible();
  const title = screen.getByRole("textbox", { name: "Title" });
  const terminal = ["published", "archived-history"].includes(state);
  await waitFor(() => expect(title).toHaveValue(state === "published" ? "Earlier published title" : data.base.title));
  if (terminal || ["publishing", "publish_unknown"].includes(state)) expect(title).toBeDisabled();
  else expect(title).toBeEnabled();
  if (["publishing", "publish_unknown"].includes(state)) {
    expect(screen.getByRole("button", { name: "Reconcile offer" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Review listing" })).toBeDisabled();
  } else if (!terminal) {
    await userEvent.click(screen.getByRole("button", { name: "Review listing" }));
    expect(await screen.findByLabelText("Reviewed listing")).toBeVisible();
  }
  if (state === "published" || state === "published-plus-active") expect(screen.getByRole("link", { name: "View on eBay" })).toHaveAttribute("href", "https://www.ebay.com.au/itm/test-listing");
  if (state === "sold") expect(screen.getByRole("region", { name: "Take-down checklist" })).toBeVisible();
  if (state === "partially-sold") expect(screen.getByText(/sold 1 of 2 - listings still valid/)).toBeVisible();
  expect(data.errors).toEqual([]);
}, 30000);

test("every real inventory panel retains its section and usable controls", async () => {
  const data = open("staged");
  await screen.findByRole("button", { name: "Expand all" });
  await userEvent.click(screen.getByRole("button", { name: "Expand all" }));
  for (const heading of ["Local photo fix-up", "Suggested fields", "Own sales first", "Comparables", "Assisted research", "Research log", "Valuation", "Profit breakdown", "Sales", "Ready-to-paste ad copy", "eBay listing editor"]) {
    expect(await screen.findByRole("heading", { name: heading })).toBeVisible();
  }
  for (const label of ["Fix up all photos", "Run OCR", "Scan duplicates", "Copy whole ad", "Photo zip", "Record sale", "Save costs"]) {
    expect(screen.getByRole("button", { name: label })).toBeVisible();
  }
  expect(screen.getByLabelText(/choose from library/i)).toHaveAttribute("multiple");
  expect(screen.getByLabelText(/choose from library/i)).not.toHaveAttribute("capture");
  expect(screen.getByRole("textbox", { name: "Shipping note" })).toBeVisible();
  const lookup = screen.getByRole("button", { name: /Item descriptor evidence/ });
  if (lookup.getAttribute("aria-expanded") === "false") await userEvent.click(lookup);
  expect(await screen.findByText("No matching evidence", { exact: true })).toBeVisible();
  expect(data.errors).toEqual([]);
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
});

test("hub destinations open the requested editor/history; reconnect and orders are real routes", async () => {
  const data = open("published-plus-active", "/ebay");
  await userEvent.click(within(await screen.findByRole("region", { name: "Staged offers" })).getByRole("link", { name: `${data.item.sku} - ${data.base.title}` }));
  const editor = within(await screen.findByRole("region", { name: "Canonical eBay listing" }));
  expect(await editor.findByRole("textbox", { name: "Title" })).toHaveValue(data.base.title);
  expect(editor.getByRole("textbox", { name: "Title" })).toBeEnabled();
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
  expect(data.errors).toEqual([]);
});

test("history deep link expands the collapsed section without saves or creating a draft", async () => {
  const data = phase6Fixture("published-plus-active");
  open("published-plus-active", `/inventory/${data.item.id}?draft=published-history#listings-channels`);
  const editor = within(await screen.findByRole("region", { name: "Canonical eBay listing" }));
  await waitFor(() => expect(editor.getByRole("textbox", { name: "Title" })).toHaveValue("Earlier published title"));
  expect(editor.getByRole("textbox", { name: "Title" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Collapse all" }));
  await userEvent.click(screen.getByRole("button", { name: "List on eBay" }));
  expect(await editor.findByRole("textbox", { name: "Title" })).toHaveValue(data.base.title);
});

test("a history deep link outside the first list page still opens the exact retained draft", async () => {
  const data = phase6Fixture("published-plus-active");
  const current = open("published-plus-active", `/inventory/${data.item.id}?draft=published-history#listings-channels`, true);
  const editor = within(await screen.findByRole("region", { name: "Canonical eBay listing" }));
  await waitFor(() => expect(editor.getByRole("textbox", { name: "Title" })).toHaveValue("Earlier published title"));
  expect(editor.getByRole("textbox", { name: "Title" })).toBeDisabled();
  expect(current.calls).toContain("GET /api/listing-drafts/published-history/");
  expect(current.errors).toEqual([]);
  expect(current.calls.every((call) => call.startsWith("GET "))).toBe(true);
});

test("hub mount is GET-only, names stale/unavailable data and reconciles only on a click", async () => {
  const data = open("publish_unknown", "/ebay");
  expect(await screen.findByRole("region", { name: "Connection health" })).toHaveTextContent("stale");
  expect(screen.getByRole("region", { name: "Orders" })).toHaveTextContent("Unavailable");
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
  await userEvent.click(screen.getByRole("button", { name: `Reconcile ${data.item.sku}` }));
  await waitFor(() => expect(data.calls).toContain(`POST /api/listing-drafts/${data.base.id}/reconcile/`));
  expect(data.calls.filter((call) => call.startsWith("POST "))).toHaveLength(1);
  expect(data.errors).toEqual([]);
});

test.each([["Manage connection and policies", "eBay Settings destination"], ["Open eBay orders", "Orders destination"]])("hub %s reaches a working destination", async (link, destination) => {
  const data = open("staged", "/ebay");
  await userEvent.click(await screen.findByRole("link", { name: link }));
  expect(await screen.findByRole("heading", { name: destination })).toBeVisible();
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
});

test("previously hidden item-detail Use this reaches Buy with an owned record ID", async () => {
  const data = open("staged", undefined, false, true);
  await userEvent.click(await screen.findByRole("button", { name: "Expand all" }));
  const lookup = screen.getByRole("button", { name: /Item descriptor evidence/ });
  if (lookup.getAttribute("aria-expanded") === "false") await userEvent.click(lookup);
  await userEvent.click(await screen.findByRole("button", { name: "Use this" }));
  expect(await screen.findByRole("heading", { name: "Calculator evidence sale:owned-1" })).toBeVisible();
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
  expect(data.errors).toEqual([]);
});
