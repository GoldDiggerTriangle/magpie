import { expect, test, type Page } from "@playwright/test";
import { phase6Fixture, type ListingState } from "./phase6.fixture";

async function isolate(page: Page, state: ListingState, title: string, entry?: string) {
  const data = phase6Fixture(state, title);
  const forbidden: string[] = [];
  page.on("pageerror", (error) => forbidden.push(error.message));
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== "http://127.0.0.1:4179") { forbidden.push(url.origin); return route.abort(); }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    try { return route.fulfill({ json: data.response(request.url(), request.method(), request.postData() ? request.postDataJSON() : undefined) }); }
    catch (error) { forbidden.push(String(error)); return route.abort(); }
  });
  await page.goto(`/e2e/phase6.html${entry ? `?entry=${encodeURIComponent(entry)}` : ""}`);
  return { ...data, forbidden };
}

async function fits(page: Page) {
  const dimensions = await page.evaluate(() => ({
    client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth,
    overflow: [...document.querySelectorAll("body *")].filter((el) => {
      if (!(el instanceof HTMLElement) || !el.checkVisibility() || el.closest(".item-tabs")) return false;
      const rect = el.getBoundingClientRect(); return rect.width > 0 && (rect.right > innerWidth + 1 || rect.left < -1);
    }).slice(0, 8).map((el) => ({ tag: el.tagName, class: el.className })),
  }));
  expect(dimensions.scroll, JSON.stringify(dimensions)).toBe(dimensions.client);
  expect(dimensions.overflow, JSON.stringify(dimensions)).toEqual([]);
}

for (const [kind, title] of Object.entries({ spaced: "Australian gold nugget with original surface marks and natural shape for review. ".repeat(2).slice(0, 80), unbroken: "N".repeat(80) })) {
  test(`Phase 6 ${kind} 80-character title: item, editor, preview, staged review and hub fit 390px`, async ({ page }, info) => {
    const data = await isolate(page, "staged", title);
    await expect(page.getByRole("heading", { name: title, level: 1 })).toBeVisible();
    await page.getByRole("tab", { name: "Details", exact: true }).click();
    await expect(page.getByRole("button", { name: "List on eBay", exact: true })).toBeVisible();
    await fits(page);
    await page.screenshot({ path: info.outputPath(`phase6-item-${kind}-390.png`) });
    await page.getByRole("button", { name: "List on eBay", exact: true }).click();
    await expect(page.getByRole("textbox", { name: "Title", exact: true })).toHaveValue(title);
    await expect(page.getByText("80/80", { exact: true })).toBeVisible();
    await fits(page);
    await page.getByRole("button", { name: "Quick publish preview", exact: true }).click();
    await expect(page.getByRole("button", { name: "Post live to eBay", exact: true })).toBeVisible();
    await fits(page);
    await page.getByRole("button", { name: "Close listing preview" }).click();
    await page.getByRole("button", { name: "Review listing", exact: true }).click();
    await expect(page.getByRole("button", { name: "Update staged offer", exact: true })).toBeVisible();
    await fits(page);
    await page.locator(".listing-review").scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath(`phase6-review-${kind}-390.png`) });
    await page.getByRole("link", { name: "eBay", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Live listings", exact: true })).toBeVisible();
    await fits(page);
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: info.outputPath(`phase6-hub-${kind}-390.png`) });
    await page.getByRole("region", { name: "Live listings", exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath(`phase6-hub-live-${kind}-390.png`) });
    expect(data.forbidden).toEqual([]);
    expect(data.calls.filter((call) => !call.startsWith("GET "))).toEqual([
      `POST /api/listing-drafts/${data.base.id}/preview/`, `POST /api/listing-drafts/${data.base.id}/preview/`,
    ]);
  });
}

test("Inherited Phase 6 desktop destinations remain usable through tabs and eBay navigation", async ({ page }, info) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const data = await isolate(page, "published", "Synthetic own gold specimen");
  await expect(page.getByRole("button", { name: "List on eBay", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "View on eBay", exact: true })).toHaveAttribute("href", "https://www.ebay.com.au/itm/test-listing");
  await expect(page.getByRole("tablist", { name: "Item tabs" })).toBeVisible();
  await page.screenshot({ path: info.outputPath("phase6-item-desktop.png") });
  await page.getByRole("link", { name: "eBay", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Live listings", exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath("phase6-hub-desktop.png") });
  expect(data.forbidden).toEqual([]);
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
});

test("Phase 6 published phone item keeps the top action and separate live link outside collapsed sections", async ({ page }, info) => {
  const data = await isolate(page, "published", "Synthetic own gold specimen");
  await page.getByRole("tab", { name: "Details" }).click();
  await expect(page.getByRole("button", { name: "List on eBay", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "View on eBay", exact: true })).toBeVisible();
  await fits(page);
  await page.screenshot({ path: info.outputPath("phase6-published-item-390.png") });
  await page.getByRole("button", { name: "List on eBay", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Title", exact: true })).toBeDisabled();
  expect(data.calls.every((call) => call.startsWith("GET "))).toBe(true);
  expect(data.forbidden).toEqual([]);
});
