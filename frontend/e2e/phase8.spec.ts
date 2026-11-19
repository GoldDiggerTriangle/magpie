import { expect, test, type Page } from "@playwright/test";
import health from "../src/fixtures/ebayHealth.json" with { type: "json" };

async function fits(page: Page) {
  const sizes = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth,
    overflow: [...document.querySelectorAll("body *")].filter((n) => n instanceof HTMLElement && n.checkVisibility() && n.getBoundingClientRect().right > innerWidth + 1).map((n) => n.tagName) }));
  expect(sizes.scroll).toBe(sizes.client); expect(sizes.overflow).toEqual([]);
}

for (const width of [390, 1440]) test(`Phase 8 ${width}px explicit reduction, unresolved outcome and legacy no-write state`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
  const calls: string[] = [], forbidden: string[] = [];
  let unknown = false;
  page.on("pageerror", (error) => forbidden.push(error.message));
  await page.route("**/*", async (route) => {
    const r = route.request(), u = new URL(r.url());
    if (u.origin !== "http://127.0.0.1:4179") { forbidden.push(u.origin); return route.abort(); }
    if (!u.pathname.startsWith("/api/")) return route.continue();
    calls.push(`${r.method()} ${u.pathname}`);
    if (u.pathname === "/api/ebay/connection-health/") return route.fulfill({ json: health });
    if (u.pathname === "/api/items/legacy/ebay-quantity/") return route.fulfill({ json: { item_id: "legacy", sku: "GOLD-00002", state: "allocation_not_recorded", label: "Allocation not recorded", urgent: false, can_write: false } });
    const state = { item_id: "owned", sku: "OWN-00001", state: unknown ? "unknown" : "update_required", label: unknown ? "Check quantity result; do not retry" : "Update eBay: 5 -> 3",
      urgent: true, can_write: !unknown, allocation_id: "allocation", allocated: 5, target: 3, remaining: 3, inventory_available: 5, offer_available: 5,
      pending_units: 0, unlinked_orders: 0, stock_revision: 4, stock_fingerprint: "synthetic-stock", allocation_revision: 1, attempt_id: unknown ? "attempt" : null };
    if (u.pathname === "/api/items/owned/ebay-quantity/") return route.fulfill({ json: state });
    if (u.pathname === "/api/ebay/allocations/allocation/update/" && r.method() === "POST") {
      expect(r.postDataJSON()).toEqual({ quantity: 3, stock_revision: 4, stock_fingerprint: "synthetic-stock", allocation_revision: 1 });
      unknown = true; return route.fulfill({ json: { ...state, state: "unknown", label: "Check quantity result; do not retry", can_write: false, attempt_id: "attempt" } });
    }
    forbidden.push(`${r.method()} ${u.pathname}`); return route.abort();
  });
  await page.goto("/e2e/phase8.html");
  await expect(page.getByRole("heading", { name: "Update eBay: 5 -> 3" })).toBeVisible();
    await expect(page.getByText("eBay listing quantity was not recorded")).toBeVisible();
  expect(calls.every((c) => c.startsWith("GET "))).toBe(true);
  await fits(page); await page.screenshot({ path: info.outputPath(`phase8-quantity-warning-${width}.png`) });
  const update = page.getByRole("button", { name: "Update quantity on eBay" });
  await expect(update).toBeDisabled();
  await page.getByRole("checkbox", { name: "Confirm this exact quantity change" }).check();
  await expect(update).toBeEnabled();
  await fits(page); await page.screenshot({ path: info.outputPath(`phase8-quantity-review-${width}.png`) });
  await update.click();
  await expect(page.getByRole("button", { name: "Reconcile quantity result" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Update quantity on eBay" })).toHaveCount(0);
  await fits(page); await page.screenshot({ path: info.outputPath(`phase8-quantity-unknown-${width}.png`) });
  expect(calls.filter((c) => c.startsWith("POST"))).toEqual(["POST /api/ebay/allocations/allocation/update/"]);
  expect(forbidden).toEqual([]);
});
