import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { phase6Fixture, listingStates, type ListingState } from "./phase6.fixture";

test("deep-link focus waits for the real editor and selects its tab before focusing", async ({ page }) => {
  const fixture = phase6Fixture("staged");
  const data = await isolated(page, "staged", `/inventory/${fixture.item.id}?draft=${fixture.base.id}#listing-${fixture.base.id}-price`);
  await expect(page.getByRole("tab", { name: "eBay" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("textbox", { name: "Price", exact: true })).toBeFocused();
  await page.getByRole("tab", { name: "Pricing", exact: true }).click();
  await page.evaluate(() => scrollTo(0, 1000));
  const bar = await page.locator(".item-tabs-shell").boundingBox();
  expect(bar!.y).toBeLessThanOrEqual(1);
  expect(data.calls.every(x => x.startsWith("GET "))).toBe(true);
  expect(data.forbidden).toEqual([]);
});

test("Arrange uses the existing local photo endpoints and saved order resumes", async ({ page }) => {
  const data = await isolated(page, "staged", undefined, true);
  await page.getByRole("tab", { name: "Photos", exact: true }).click();
  await page.getByRole("button", { name: "Arrange", exact: true }).click();
  await page.getByRole("button", { name: "Move photo 1 later" }).click();
  await expect(page.locator(".photo-open img").first()).toHaveAttribute("alt", "Photo 1: back");
  await page.getByRole("button", { name: "Set photo 1 as main" }).click();
  await expect(page.locator(".photo-tile").first().getByText("Main", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Delete photo 1" }).click();
  await expect(page.getByText("Delete photo?", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.reload();
  await expect(page.getByRole("tab", { name: "Photos", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".photo-open img").first()).toHaveAttribute("alt", "Photo 1: back");
  expect(data.calls.filter(x => !x.startsWith("GET "))).toEqual([
    `POST /api/items/${data.item.id}/photos/reorder/`, `PATCH /api/photos/${data.item.photos[0].id}/`
  ]);
  expect(data.forbidden).toEqual([]);
});

const ownImage = readFileSync(new URL("../../docs/evidence/sprint26/phase0/gold-live--default.png", import.meta.url));
async function isolated(page: Page, state: ListingState, entry?: string, photoWrites = false) {
  const data = phase6Fixture(state, "N".repeat(80));
  for (const photo of data.item.photos) Object.assign(photo, { thumb_url: "/audit-photo.png", processed_url: "/audit-photo.png", original_url: "/audit-photo.png" });
  const forbidden: string[] = [];
  page.on("pageerror", e => forbidden.push(e.message));
  await page.route("**/*", async route => {
    const req = route.request(), url = new URL(req.url());
    if (url.origin !== "http://127.0.0.1:4179") { forbidden.push(url.origin); return route.abort(); }
    if (url.pathname === "/audit-photo.png") return route.fulfill({ body: ownImage, contentType: "image/png" });
    if (!url.pathname.startsWith("/api/")) return route.continue();
    if (photoWrites && req.method() === "POST" && url.pathname.endsWith("/photos/reorder/")) {
      data.calls.push(`POST ${url.pathname}`);
      const order = req.postDataJSON().order as string[];
      data.item.photos.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id)).forEach((p, index) => p.order_index = index);
      return route.fulfill({ json: data.item.photos });
    }
    if (photoWrites && req.method() === "PATCH" && url.pathname.startsWith("/api/photos/")) {
      data.calls.push(`PATCH ${url.pathname}`);
      const id = url.pathname.split("/")[3];
      data.item.photos.forEach(p => p.is_main = p.id === id);
      return route.fulfill({ json: data.item.photos.find(p => p.id === id) });
    }
    try { return route.fulfill({ json: data.response(url.href, req.method(), req.postData() ? req.postDataJSON() : undefined) }); }
    catch (e) { forbidden.push(String(e)); return route.abort(); }
  });
  await page.goto(`/e2e/phase6.html${entry ? "?entry=" + encodeURIComponent(entry) : ""}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  return { ...data, forbidden };
}
async function fit(page: Page) {
  const d = await page.evaluate(() => ({
    width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth,
    overflow: [...document.querySelectorAll("body *")].filter(el => {
      if (!(el instanceof HTMLElement) || !el.checkVisibility() || el.closest(".item-tabs")) return false;
      const r = el.getBoundingClientRect(); return r.width > 0 && (r.right > innerWidth + 1 || r.left < -1);
    }).slice(0, 8).map(e => ({ tag: e.tagName, class: e.className }))
  }));
  expect(d.scroll, JSON.stringify(d)).toBe(d.width);
  expect(d.overflow, JSON.stringify(d)).toEqual([]);
}
for (const width of [320, 390]) for (const large of [false, true]) {
  test(`Sprint 26 all tabs, photo Arrange, preview/review and keyboard Save fit ${width}px ${large ? "larger" : "normal"} text`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 });
    const data = await isolated(page, "staged");
    if (large) await page.addStyleTag({ content: "html { font-size: 20px !important; }" });
    await expect(page.getByRole("tab", { name: "Details" })).toHaveAttribute("aria-selected", "true");
    const strip = page.getByRole("tablist");
    const initial = await strip.evaluate(el => ({ client: el.clientWidth, scroll: el.scrollWidth }));
    expect(initial.scroll).toBeGreaterThan(initial.client);
    await expect(page.getByRole("button", { name: "More item tabs" })).toBeVisible();
    for (const tab of ["Details", "Photos", "Research", "Pricing", "Sales", "eBay"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      await expect(page.getByRole("tabpanel", { name: tab, exact: true })).toBeVisible();
      await fit(page);
      await page.screenshot({ path: info.outputPath(`tabs-${tab}-${width}-${large}.png`) });
    }
    await page.getByRole("tab", { name: "Photos", exact: true }).click();
    const columns = await page.locator(".photo-grid").evaluate(el => getComputedStyle(el).gridTemplateColumns.split(" ").length);
    expect(columns).toBe(3);
    await expect(page.getByTitle("Set main")).toHaveCount(0);
    await page.getByRole("button", { name: "View photo 1 full size" }).click();
    await expect(page.getByRole("dialog", { name: "Full size photo" })).toBeVisible();
    await expect(page.getByAltText("Full size own photo")).toBeVisible();
    await page.getByRole("button", { name: "Close full size photo" }).click();
    await page.getByRole("button", { name: "Arrange", exact: true }).click();
    await expect(page.getByTitle("Set main")).toHaveCount(2);
    await expect(page.getByRole("button", { name: "Move photo 1 earlier" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Move photo 2 later" })).toBeDisabled();
    await fit(page);
    await page.screenshot({ path: info.outputPath(`arrange-${width}-${large}.png`) });
    await page.getByRole("tab", { name: "eBay", exact: true }).click();
    await page.getByRole("button", { name: "Review listing", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Staged listing review" })).toBeVisible();
    await fit(page);
    await page.getByRole("button", { name: "Close listing preview" }).click();
    await page.getByRole("button", { name: "Quick publish preview" }).click();
    await expect(page.getByRole("button", { name: "Post live to eBay" })).toBeVisible();
    await fit(page);
    await page.getByRole("button", { name: "Close listing preview" }).click();
    await page.setViewportSize({ width, height: 480 });
    await page.getByRole("textbox", { name: "Title", exact: true }).focus();
    await page.locator(".listing-save-bar button").scrollIntoViewIfNeeded();
    const save = await page.locator(".listing-save-bar button").boundingBox();
    const navigation = page.locator(".mobile-bottom-nav");
    if (await navigation.isVisible()) {
      const nav = await navigation.boundingBox();
      expect(save!.y + save!.height).toBeLessThanOrEqual(nav!.y + 1);
    } else {
      // Sprint 27 replaces the nav offset with the actual visible edge while the keyboard is open.
      expect(await page.evaluate(() => document.documentElement.dataset.mobileKeyboard)).toBe("open");
      const bottom = await page.evaluate(() => visualViewport!.offsetTop + visualViewport!.height);
      expect(save!.y + save!.height).toBeLessThanOrEqual(bottom + 1);
    }
    await fit(page);
    expect(data.forbidden).toEqual([]);
    expect(data.calls.filter(x => !x.startsWith("GET "))).toEqual([
      `POST /api/listing-drafts/${data.base.id}/preview/`, `POST /api/listing-drafts/${data.base.id}/preview/`
    ]);
  });
}
test("all listing states retain header destinations and no writes from tab navigation", async ({ page }) => {
  for (const state of listingStates) {
    const data = await isolated(page, state);
    if (state === "sold") {
      await expect(page.getByText("Sold out", { exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "List on eBay" })).toHaveCount(0);
      await expect(page.getByRole("alert").filter({ hasText: "Sold out but still listed" })).toBeVisible();
    } else await expect(page.getByRole("button", { name: "List on eBay" })).toBeVisible();
    for (const tab of ["Photos", "Research", "Pricing", "eBay", "Sales", "Details"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      await expect(page.getByRole("tabpanel", { name: tab, exact: true })).toBeVisible();
    }
    expect(data.calls.every(x => x.startsWith("GET "))).toBe(true);
    expect(data.forbidden).toEqual([]);
  }
});
