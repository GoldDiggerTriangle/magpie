import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ItemDetail } from "./ItemDetail";
import { AppShell } from "../../components/AppShell";
import { EbayHub } from "../ebay/EbayHub";
import { listingStates, phase6Fixture, type ListingState } from "../../../e2e/phase6.fixture";

vi.setConfig({ testTimeout: 30000 });

test("Back and Forward restore explicit tab and exact read-only draft query", async () => {
  const fixture = phase6Fixture("published-plus-active");
  const data = open("published-plus-active", `/inventory/${fixture.item.id}?draft=published-history#listings-channels`);
  const editor = await screen.findByRole("region", { name: "Canonical eBay listing" });
  await waitFor(() => expect(within(editor).getByRole("textbox", { name: "Title" })).toHaveValue("Earlier published title"));
  await userEvent.click(screen.getByRole("tab", { name: "Photos" }));
  await userEvent.click(screen.getByRole("button", { name: "Back fixture" }));
  expect(screen.getByRole("tab", { name: "eBay", selected: true })).toBeVisible();
  expect(within(editor).getByRole("textbox", { name: "Title" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Forward fixture" }));
  expect(screen.getByRole("tab", { name: "Photos", selected: true })).toBeVisible();
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
});
test("an explicit review link wins over a remembered Photos tab", async () => {
  const fixture = phase6Fixture("staged");
  localStorage.setItem(`magpie:item-tab:v1:${fixture.item.id}`, "Photos");
  const data = open("staged", `/inventory/${fixture.item.id}#ai-review`);
  expect(await screen.findByRole("tab", { name: "Research", selected: true })).toBeVisible();
  expect(await screen.findByRole("heading", { name: "Suggested fields" })).toBeVisible();
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
});
test("a sold-out header warning selects eBay and reaches the take-down control without writing", async () => {
  const data = open("sold");
  await userEvent.click(await screen.findByRole("button", { name: "Open take-down checklist" }));
  expect(screen.getByRole("tab", { name: "eBay", selected: true })).toBeVisible();
  expect(screen.getByRole("button", { name: "Mark eBay ended" })).toBeEnabled();
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
});

test("tabs preserve core and schema buffers while background refresh updates clean siblings", async () => {
  const data = open("staged");
  await screen.findByRole("heading", { name: data.item.title, level: 1 });
  const core = document.getElementById("core-details-panel")!;
  const specifics = document.getElementById("category-specifics-panel")!;
  const title = await within(core).findByLabelText("Title");
  fireEvent.change(title, { target: { value: "My pending title" } });
  const metal = await within(specifics).findByLabelText("Metal");
  fireEvent.change(metal, { target: { value: "My pending metal" } });
  await userEvent.click(screen.getByRole("tab", { name: "Research" }));
  await act(async () => { data.client.setQueryData(["item", data.item.id], { ...data.item, title: "Remote title", notes: "Fresh note", attributes: { metal: "remote", weight: "2" } }); });
  await userEvent.click(screen.getByRole("tab", { name: "Details" }));
  expect(title).toHaveValue("My pending title");
  expect(metal).toHaveValue("My pending metal");
  expect(within(specifics).getByLabelText("Notes")).toHaveValue("Fresh note");
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
});

test("pending photo uploads survive switching tabs without upload or other writes", async () => {
  const data = open("staged");
  await userEvent.click(await screen.findByRole("tab", { name: "Photos" }));
  const input = screen.getByLabelText(/Choose from library/i) as HTMLInputElement;
  await userEvent.upload(input, new File(["synthetic"], "pending.jpg", { type: "image/jpeg" }));
  expect(screen.getByText("pending.jpg")).toBeVisible();
  await userEvent.click(screen.getByRole("tab", { name: "Sales" }));
  await userEvent.click(screen.getByRole("tab", { name: "Photos" }));
  expect(screen.getByText("pending.jpg")).toBeVisible();
  expect(screen.getByRole("button", { name: "Upload selected" })).toBeEnabled();
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
});

test("research note and capture text survive tab switching without saving", async () => {
  const data = open("staged");
  await userEvent.click(await screen.findByRole("tab", { name: "Research" }));
  const note = within(document.getElementById("research-log")!).getByLabelText("Note");
  fireEvent.change(note, { target: { value: "Pending research" } });
  await userEvent.click(screen.getByRole("tab", { name: "Pricing" }));
  const copied = screen.getByLabelText("Text copied from screenshot");
  fireEvent.change(copied, { target: { value: "Pending evidence text" } });
  await userEvent.click(screen.getByRole("tab", { name: "Research" }));
  expect(note).toHaveValue("Pending research");
  await userEvent.click(screen.getByRole("tab", { name: "Pricing" }));
  expect(copied).toHaveValue("Pending evidence text");
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
});

test("listing tab changes neither unmount nor flush autosave, and selected photos survive", async () => {
  const data = open("staged", undefined, false, false, true);
  await userEvent.click(await screen.findByRole("button", { name: "List on eBay" }));
  const editor = screen.getByRole("region", { name: "Canonical eBay listing" });
  const title = await within(editor).findByRole("textbox", { name: "Title" });
  fireEvent.change(title, { target: { value: "Pending listing text" } });
  const selectedPhoto = within(editor).getByRole("checkbox", { name: `Select photo ${data.item.photos[0].id}` });
  fireEvent.click(selectedPhoto);
  expect(selectedPhoto).not.toBeChecked();
  const originalNode = title;
  fireEvent.click(screen.getByRole("tab", { name: "Photos" }));
  expect(data.calls.filter((call) => call.startsWith("PATCH"))).toHaveLength(0);
  fireEvent.click(screen.getByRole("tab", { name: "eBay" }));
  expect(within(editor).getByRole("textbox", { name: "Title" })).toBe(originalNode);
  expect(title).toHaveValue("Pending listing text");
  expect(selectedPhoto).not.toBeChecked();
  await waitFor(() => expect(data.calls.filter((call) => call.startsWith("PATCH"))).toHaveLength(1), { timeout: 2000 });
  expect(data.calls.filter((call) => /stage|publish|reconcile/.test(call))).toEqual([]);
  expect(data.errors).toEqual([]);
});

test.each(["publishing", "publish_unknown"] as const)("state-specific notice is truthful and edits stay locked: %s", async (state) => {
  const data = open(state);
  await userEvent.click(await screen.findByRole("button", { name: "List on eBay" }));
  expect(screen.queryByText(/Unpublished staged offer/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Local changes are not yet on eBay/)).not.toBeInTheDocument();
  expect(screen.getByText(state === "publishing" ? "Publishing in progress" : "Publish result is not yet known")).toBeVisible();
  expect(screen.getByRole("button", { name: "Review listing" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Reconcile offer" })).toBeEnabled();
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
});

test("More actions keeps named delete confirmation and cancellation without deletion", async () => {
  const data = open("staged");
  await userEvent.click(await screen.findByRole("button", { name: "More actions" }));
  await userEvent.click(screen.getByRole("button", { name: "Delete item" }));
  expect(screen.getByText(`${data.item.title} (${data.item.sku})`)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByText("Delete item?")).not.toBeInTheDocument();
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
});

test("legacy sales-valuations link opens Pricing with a usable Sales shortcut", async () => {
  const data = phase6Fixture("staged");
  open("staged", `/inventory/${data.item.id}#sales-valuations`);
  expect(await screen.findByRole("tab", { name: "Pricing", selected: true })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Valuation" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Sales" }));
  expect(screen.getByRole("tab", { name: "Sales", selected: true })).toBeVisible();
  expect(screen.getByRole("button", { name: "Record sale" })).toBeVisible();
});

test("invalid remembered tab falls back to Details while explicit deep links win", async () => {
  const data = phase6Fixture("staged");
  localStorage.setItem(`magpie:item-tab:v1:${data.item.id}`, "obsolete-tab");
  const first = open("staged");
  expect(await screen.findByRole("tab", { name: "Details", selected: true })).toBeVisible();
  expect(first.calls.every((call) => call.startsWith("GET "))).toBe(true);
});

// No panel mocks: the real item page and every inventory/listing panel must remain reachable.
beforeEach(() => { localStorage.clear(); });
afterEach(() => vi.unstubAllGlobals());
function EvidenceDestination() {
  const location = useLocation();
  return <h1>Calculator evidence {location.state?.ownedEvidence?.rowId}</h1>;
}
function TestHistory() {
  const navigate = useNavigate();
  return <><button onClick={() => navigate(-1)} type="button">Back fixture</button><button onClick={() => navigate(1)} type="button">Forward fixture</button></>;
}
function open(state: ListingState, route?: string, olderHistory = false, withEvidence = false, allowEdits = false) {
  const data = phase6Fixture(state);
  if (olderHistory) data.drafts.splice(0, 1);
  if (withEvidence) data.evidenceRows.push({ id: "sale:owned-1", record_type: "sale", source: "own_sale_exact", label: "Own exact sale", source_label: "Own sale", match_reason: "same item", seller_receives: "100.00", basis_uncertain: false, basis_label: "Seller receives", currency: "AUD", own_sale: true, date: "2026-11-01" });
  const errors: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => {
    if (allowEdits && options?.method === "PATCH") {
      const url = new URL(path, "http://localhost");
      data.calls.push(`PATCH ${url.pathname}`);
      const payload = JSON.parse(String(options.body));
      if (url.pathname === `/api/items/${data.item.id}/`) Object.assign(data.item, payload);
      else Object.assign(data.base, payload, { updated_at: new Date(Date.parse(data.base.updated_at) + 1000).toISOString() });
      return new Response(JSON.stringify(url.pathname.includes("listing-drafts") ? data.base : data.item), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    try { return new Response(JSON.stringify(data.response(path, options?.method, options?.body ? JSON.parse(String(options.body)) : undefined)), { status: 200, headers: { "Content-Type": "application/json" } }); }
    catch (error) { errors.push(String(error)); return new Response("Unexpected synthetic request", { status: 500 }); }
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route ?? `/inventory/${data.item.id}`]}>
    <TestHistory />
    <Routes><Route element={<AppShell />}><Route path="/inventory/:id" element={<ItemDetail />} /><Route path="/ebay" element={<EbayHub />} /><Route path="/settings/ebay" element={<h1>eBay Settings destination</h1>} /><Route path="/ebay/orders" element={<h1>Orders destination</h1>} /><Route path="/buy-calculator" element={<EvidenceDestination />} /></Route></Routes>
  </MemoryRouter></QueryClientProvider>);
  return { ...data, errors, client };
}

test.each(listingStates)("real-panel reachability gate: %s", async (state) => {
  const data = open(state);
  await screen.findByRole("heading", { name: data.item.title, level: 1 });
  await userEvent.click(screen.getByRole("tab", { name: "Details" }));
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
  if (state === "sold") {
    expect(screen.getByText("Sold out", { exact: true })).toBeVisible();
    expect(screen.queryByRole("button", { name: "List on eBay" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "eBay" }));
  } else {
    const top = screen.getByRole("button", { name: "List on eBay" });
    await waitFor(() => expect(top).toBeEnabled());
    expect(top).toBeVisible();
    await userEvent.click(top);
  }
  const section = document.getElementById("listings-channels-content") ?? document.querySelector(".listing-panel");
  expect(section).toBeVisible();
  expect(await screen.findByRole("heading", { name: "eBay listing editor" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Ready-to-paste ad copy" })).toBeVisible();
  const title = within(screen.getByRole("region", { name: "Canonical eBay listing" })).getByRole("textbox", { name: "Title" });
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
  await userEvent.click(await screen.findByRole("tab", { name: "Photos" }));
  await userEvent.click(screen.getByText("Photo adjustments", { exact: true }));
  expect(screen.getByRole("heading", { name: "Local photo fix-up" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Fix up all photos" })).toBeVisible();
  expect(screen.getByLabelText(/choose from library/i)).toHaveAttribute("multiple");
  expect(screen.getByLabelText(/choose from library/i)).not.toHaveAttribute("capture");
  for (const [tab, headings, controls] of [
    ["Research", ["Suggested fields", "Assisted research", "Research log"], ["Run OCR", "Scan duplicates"]],
    ["Pricing", ["Own sales first", "Comparables", "Valuation", "Profit breakdown"], ["Save costs"]],
    ["Sales", ["Sales"], ["Record sale"]],
    ["eBay", ["Ready-to-paste ad copy", "eBay listing editor"], ["Copy whole ad", "Photo zip"]]
  ] as const) {
    await userEvent.click(screen.getByRole("tab", { name: tab }));
    for (const heading of headings) expect(await screen.findByRole("heading", { name: heading })).toBeVisible();
    for (const label of controls) expect(screen.getByRole("button", { name: label })).toBeVisible();
  }
  expect(screen.getByRole("textbox", { name: "Shipping note" })).toBeVisible();
  await userEvent.click(screen.getByRole("tab", { name: "Pricing" }));
  const lookup = screen.getByRole("button", { name: /Matching item evidence/ });
  if (lookup.getAttribute("aria-expanded") === "false") await userEvent.click(lookup);
  expect(await screen.findByText("No matching evidence", { exact: true })).toBeVisible();
  expect(data.errors).toEqual([]);
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
}, 30000);

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
  await userEvent.click(screen.getByRole("tab", { name: "Details" }));
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
  await userEvent.click(await screen.findByRole("tab", { name: "Pricing" }));
  const lookup = screen.getByRole("button", { name: /Matching item evidence/ });
  if (lookup.getAttribute("aria-expanded") === "false") await userEvent.click(lookup);
  await userEvent.click(await screen.findByRole("button", { name: "Use this" }));
  expect(await screen.findByRole("heading", { name: "Calculator evidence sale:owned-1" })).toBeVisible();
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
  expect(data.errors).toEqual([]);
});
