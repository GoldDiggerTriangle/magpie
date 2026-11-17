import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import fixture from "../fixtures/ebayHealth.json";
import type { EbayHealth, EbayDiagnostic } from "../api/ebayHealth";
import { EbayConnectionBanner, EbayConnectionHealth, EbayDiagnostics } from "./EbayConnectionHealth";

const mocks = vi.hoisted(() => ({ get: vi.fn(), check: vi.fn() }));
vi.mock("../api/ebayHealth", () => ({ getEbayHealth: (...args: unknown[]) => mocks.get(...args), checkEbayConnection: (...args: unknown[]) => mocks.check(...args) }));
let data: EbayHealth;
beforeEach(() => { vi.clearAllMocks(); data = structuredClone(fixture) as EbayHealth; mocks.get.mockImplementation(async () => structuredClone(data)); });
function show(component = <EbayConnectionHealth />) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return { client, ...render(<QueryClientProvider client={client}>{component}</QueryClientProvider>) };
}
const failure = (kind = "permission"): EbayDiagnostic => ({ operation: "inventory.publish", time: "2026-11-17T03:00:00Z", http_status: 403,
  issues: [{ kind, domain: "OAuth", category: "REQUEST", severity: "error", error_id: 1100, field: null, message: "Permission denied for inventory.publish - cause not confirmed." }] });

test("loads saved metadata only, labels scopes honestly and every unchecked API", async () => {
  show(); await screen.findByText("Last checked: Not yet checked");
  expect(mocks.check).not.toHaveBeenCalled();
  expect(screen.getByText("Requested / required scopes (not proof of grant)")).toBeVisible();
  for (const name of ["Inventory", "Account", "Fulfilment", "Finances", "Media/EPS", "Taxonomy - application token"]) expect(screen.getByRole("heading", { name })).toBeVisible();
  expect(screen.getByText(/Expired access is renewed automatically/)).toBeVisible();
});

test("manual check requires a click, updates current results and respects the cooldown", async () => {
  const finished = structuredClone(data);
  finished.checks.seller = { started_at: "2026-11-17T03:00:00Z", completed_at: "2026-11-17T03:01:00Z", next_check_at: "2099-01-01T00:00:00Z" };
  mocks.check.mockResolvedValue({ throttled: false, health: finished });
  show(); await userEvent.click(await screen.findByRole("button", { name: "Check connection" }));
  expect(mocks.check).toHaveBeenCalledOnce();
  await waitFor(() => expect(screen.getByRole("button", { name: "Check connection" })).toBeDisabled());
  expect(screen.getByText(/Next check available/)).toBeVisible();
});

test("expired access alone has no reconnect banner; unrelated success does not hide a failure", async () => {
  const result = show(<EbayConnectionBanner />);
  await waitFor(() => expect(mocks.get).toHaveBeenCalledOnce());
  expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  data.alerts = [failure()];
  data.operations = [{ operation: "taxonomy.tree", api: "Taxonomy", principal: "application", last_success: { time: "2026-11-17T03:02:00Z", http_status: 200, count: 1 }, current_failure: null, warnings: null }];
  result.client.setQueryData(["ebay-connection-health"], data);
  expect(await screen.findByText(/cause not confirmed/, { selector: "p" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Check eBay connection in Settings" })).toHaveAttribute("href", "/settings/ebay");
});

test("seller disconnected, impending expiry, outage and confirmed reconnect are distinct", async () => {
  data.connected = false;
  const result = show(<EbayConnectionBanner />);
  expect(await screen.findByText(/eBay is disconnected/)).toBeVisible();
  data.connected = true; data.refresh.expiring_soon = true;
  result.client.setQueryData(["ebay-connection-health"], structuredClone(data));
  expect(await screen.findByText(/Seller authorisation expires soon/)).toBeVisible();
  data.refresh.expiring_soon = false; data.alerts = [{ ...failure("outage"), issues: [{ ...failure().issues[0], kind: "outage", message: "eBay service failure; local inventory remains available." }] }];
  result.client.setQueryData(["ebay-connection-health"], structuredClone(data));
  expect(await screen.findByText(/eBay service failure/, { selector: "p" })).toBeVisible();
  expect(screen.queryByRole("link", { name: "Reconnect eBay" })).not.toBeInTheDocument();
  data.alerts[0].issues[0] = { ...data.alerts[0].issues[0], kind: "reconnect", message: "Seller authorisation is unusable. Reconnect eBay." };
  result.client.setQueryData(["ebay-connection-health"], structuredClone(data));
  expect(await screen.findByRole("link", { name: "Reconnect eBay" })).toBeVisible();
});

test("diagnostics preserve multi-error details and validation fix focuses via caller without retry", async () => {
  const value = failure(); value.issues.push({ ...value.issues[0], kind: "validation", field: "price", error_id: 25003, message: "eBay rejected price." });
  const onField = vi.fn(); render(<EbayDiagnostics value={value} onField={onField} />);
  await userEvent.click(screen.getByRole("button", { name: "Go to price" })); expect(onField).toHaveBeenCalledWith("price");
  await userEvent.click(screen.getByText("Sanitised diagnostics"));
  expect(screen.getByText(/inventory.publish.*HTTP/)).toBeVisible();
  expect(screen.getByText(/eBay ID 25003/)).toBeVisible();
  expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
});

test("hub summary is read-only and does not pretend unchecked APIs succeeded", async () => {
  show(<EbayConnectionHealth compact />);
  expect(await screen.findByText(/Unchecked APIs are not proven healthy/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Check connection" })).not.toBeInTheDocument();
  expect(mocks.check).not.toHaveBeenCalled();
});
