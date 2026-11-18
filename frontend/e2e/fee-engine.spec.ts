import { test, expect } from "@playwright/test";
import health from "../src/fixtures/ebayHealth.json" with { type: "json" };
import parity from "../src/fixtures/sprint25FeeParity.json" with { type: "json" };
import { calculateOrderLocal } from "../src/features/profit/feeMath";
for (const width of [390, 1440]) test(`Fee engine ${width}px: human rates, review and unknown sample`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
  const forbidden: string[] = [], writes: string[] = [];
  let configured = false;
  await page.route("**/*", async (route) => {
    const r = route.request(), u = new URL(r.url());
    if (u.origin !== "http://127.0.0.1:4179") { forbidden.push(u.origin); return route.abort(); }
    if (!u.pathname.startsWith("/api/")) return route.continue();
    if (u.pathname === "/api/ebay/connection-health/") return route.fulfill({ json: health });
    if (u.pathname === "/api/fee-engine/calculate/" && r.method() === "POST") {
      const order = r.postDataJSON();
      return route.fulfill({ json: configured ? calculateOrderLocal({ ...order, lines: order.lines.map((l: object) => ({ ...l, tier: "tier4" })) }, parity.period, parity.rates) : { state: "schedule unknown", label: "schedule unknown", fee_total: null, lines: {} } });
    }
    if (r.method() !== "GET") { writes.push(u.pathname); return route.abort(); }
    if (u.pathname === "/api/fee-engine/") return route.fulfill({ json: { current: configured ? { id: "fixture", number: 1, label: "Synthetic browser fixture - not saved", source_note: "Isolated browser fixture", source_url: "", periods: [{ ...parity.period, plan: "pro_basic", effective_from: "2026-01-01", effective_to: null, gst_treatment: "inclusive", rates: [parity.rates.tier4] }] } : null, today: "2026-11-18", state: configured ? "configured" : "schedule unknown", gst_note: "Regan is not registered for GST. Enter GST-inclusive fees exactly as eBay shows them.", legacy: [{ id: "old", name: "Unverified legacy fixture", label: "Legacy / unverified - history only" }], versions: [], categories: { source: "Fixture", categories: {} } } });
    forbidden.push(u.pathname); return route.abort();
  });
  await page.goto("/e2e/fee-engine.html");
  await page.getByRole("button", { name: "Enter plan periods and rates" }).click();
  await page.getByLabel("Version label").fill("Synthetic review only - not saved"); await page.getByLabel("Source / provenance").fill("Isolated browser fixture");
  await page.getByRole("button", { name: "Add period" }).click();
  await expect(page.getByLabel("Fixed fee per order")).toHaveValue("");
  await page.getByLabel("Effective from").fill("2026-01-01"); await page.getByLabel("Fixed fee per order").fill("0.33"); await page.getByLabel("International fee %").fill("1.1"); await page.getByLabel("Period source / date confirmation").fill("Fixture only");
  await page.getByRole("button", { name: "Add tier" }).click(); await page.getByLabel("FVF % up to threshold").fill("13.09"); await page.getByLabel("Per-item threshold").fill("4000"); await page.getByLabel("FVF % above threshold").fill("2.75");
  await page.getByRole("button", { name: "Review new version" }).click();
  await expect(page.getByRole("region", { name: "Review fee calendar" })).toBeVisible();
  const bounds = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth, overflow: [...document.querySelectorAll("body *")].filter((n) => n instanceof HTMLElement && n.checkVisibility() && n.getBoundingClientRect().right > innerWidth + 1).map((n) => n.tagName) }));
  expect(bounds.scroll).toBe(bounds.client); expect(bounds.overflow).toEqual([]);
  await page.screenshot({ path: info.outputPath(`fee-engine-review-${width}.png`), fullPage: true });
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.getByText("Check a what-if profit figure", { exact: true }).click();
  async function sample() {
    await page.getByLabel("Sale date", { exact: true }).fill("2026-02-01");
    await page.getByLabel("Seller-receives item price").fill("100");
    await page.getByLabel("All-in direct costs").fill("60");
    await page.getByRole("button", { name: "Calculate what-if" }).click();
  }
  await sample(); await expect(page.getByText("What-if profit: Unknown")).toBeVisible();
  await page.screenshot({ path: info.outputPath(`fee-engine-unknown-${width}.png`), fullPage: true });
  configured = true; await page.reload();
  await page.getByText("Check a what-if profit figure", { exact: true }).click();
  await sample(); await expect(page.getByText("Fees: $13.42", { exact: true })).toBeVisible();
  await expect(page.getByText("What-if profit: $26.58")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath(`fee-engine-sample-${width}.png`), fullPage: true });
  expect(writes).toEqual([]); expect(forbidden).toEqual([]);
});
