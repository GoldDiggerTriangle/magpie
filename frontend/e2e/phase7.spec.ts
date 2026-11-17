import { expect, test, type Page } from "@playwright/test";
import fixture from "../src/fixtures/ebayHealth.json" with { type: "json" };
import type { EbayHealth } from "../src/api/ebayHealth";

async function setup(page: Page) {
  let state = structuredClone(fixture) as EbayHealth;
  const calls: string[] = [], forbidden: string[] = [];
  page.on("pageerror", (error) => forbidden.push(error.message));
  await page.route("**/*", async (route) => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== "http://127.0.0.1:4179") { forbidden.push(url.origin); return route.abort(); }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    calls.push(`${request.method()} ${url.pathname}`);
    if (url.pathname === "/api/ebay/connection-health/" && request.method() === "GET") return route.fulfill({ json: state });
    if (url.pathname === "/api/ebay/check-connection/" && request.method() === "POST") {
      state.checks.seller = { started_at: "2026-11-17T03:00:00Z", completed_at: "2026-11-17T03:01:00Z", next_check_at: "2099-01-01T00:00:00Z" };
      const failure = { operation: "inventory.items", time: "2026-11-17T03:00:00Z", http_status: 403, issues: [{ severity: "error" as const, kind: "permission", domain: "OAuth", category: "REQUEST", field: null, error_id: 1100, message: "eBay permission denied for inventory.items - cause not confirmed." }] };
      state.alerts = [failure];
      state.operations = [{ operation: "inventory.items", api: "Inventory", principal: "seller", last_success: null, current_failure: failure, warnings: null }];
      return route.fulfill({ json: { health: state, throttled: false } });
    }
    forbidden.push(`${request.method()} ${url.pathname}`); return route.abort();
  });
  await page.goto("/e2e/phase7.html");
  return { calls, forbidden };
}

async function fits(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(await page.evaluate(() => document.documentElement.clientWidth));
  expect(await page.evaluate(() => [...document.querySelectorAll("body *")].filter((node) => node instanceof HTMLElement && node.checkVisibility() && node.getBoundingClientRect().right > innerWidth + 1).map((node) => node.tagName))).toEqual([]);
}

test("Phase 7 390px: saved health is not yet checked; explicit check and failure banner fit without blocking inventory", async ({ page }, info) => {
  const data = await setup(page);
  await expect(page.getByText("Last checked: Not yet checked")).toBeVisible();
  await fits(page);
  expect(data.calls).toEqual(["GET /api/ebay/connection-health/"]);
  await page.screenshot({ path: info.outputPath("phase7-health-not-checked-390.png") });
  await page.getByRole("button", { name: "Check connection", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "eBay connection notice" })).toBeVisible();
  await page.evaluate(() => scrollTo(0, 0));
  await fits(page);
  await page.screenshot({ path: info.outputPath("phase7-permission-banner-390.png") });
  await page.getByRole("region", { name: "eBay connection health" }).getByRole("heading", { name: "Inventory", exact: true }).scrollIntoViewIfNeeded();
  await fits(page);
  await page.screenshot({ path: info.outputPath("phase7-operation-failure-390.png") });
  await page.getByRole("textbox", { name: "Local item note" }).fill("Local work remains usable");
  await expect(page.getByRole("textbox", { name: "Local item note" })).toHaveValue("Local work remains usable");
  expect(data.calls.filter((call) => call.startsWith("POST"))).toEqual(["POST /api/ebay/check-connection/"]);
  expect(data.forbidden).toEqual([]);
});

test("Phase 7 desktop health is readable, read-only on load and separates application-token checks", async ({ page }, info) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const data = await setup(page);
  await expect(page.getByText("Last checked: Not yet checked")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Taxonomy - application token" })).toBeAttached();
  await fits(page);
  await page.screenshot({ path: info.outputPath("phase7-health-desktop.png") });
  expect(data.calls).toEqual(["GET /api/ebay/connection-health/"]); expect(data.forbidden).toEqual([]);
});
