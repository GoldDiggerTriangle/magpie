import { expect, test, type Page } from "@playwright/test";
import { phase6Fixture } from "./phase6.fixture";

async function open(page: Page, state: "draft" | "unlisted" = "draft") {
  await page.addInitScript(() => {
    const viewport = Object.assign(new EventTarget(), { height: 844, width: innerWidth, scale: 1, offsetTop: 0, offsetLeft: 0 });
    Object.defineProperty(window, "visualViewport", { configurable: true, value: viewport });
    (window as unknown as { s27Viewport: (v: object) => void }).s27Viewport = (v) => {
      Object.assign(viewport, v); viewport.dispatchEvent(new Event("resize")); viewport.dispatchEvent(new Event("scroll"));
    };
  });
  const fixture = phase6Fixture(state);
  const forbidden: string[] = [];
  page.on("pageerror", e => forbidden.push(e.message));
  await page.route("**/*", async route => {
    const req = route.request(), url = new URL(req.url());
    if (url.origin !== "http://127.0.0.1:4179") { forbidden.push(url.origin); return route.abort(); }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    if (req.method() === "POST" && url.pathname.endsWith("/listing-drafts/")) return route.fulfill({ status: 409, json: { code: "sold_out" } });
    try { return route.fulfill({ json: fixture.response(url.href, req.method()) }); }
    catch (e) { forbidden.push(String(e)); return route.abort(); }
  });
  await page.goto("/e2e/phase6.html");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  return { fixture, forbidden };
}
async function viewport(page: Page, values: object) {
  await page.evaluate(v => (window as unknown as { s27Viewport: (v: object) => void }).s27Viewport(v), values);
}
async function focus(field: ReturnType<Page["locator"]>) { await field.evaluate(el => (el as HTMLElement).focus({ preventScroll: true })); }
async function aboveKeyboard(page: Page, button: ReturnType<Page["locator"]>) {
  await button.evaluate(el => window.scrollBy(0, el.getBoundingClientRect().bottom - (visualViewport!.offsetTop + visualViewport!.height) + 24));
  // At layout scroll limits Safari pans the visual viewport independently of the document.
  const pan = await button.evaluate(el => Math.max(0, el.getBoundingClientRect().bottom + 24 - 450));
  expect(pan).toBeLessThanOrEqual(844 - 450);
  await viewport(page, { offsetTop: pan });
  const box = await button.boundingBox();
  expect(box!.y - pan).toBeGreaterThanOrEqual(0); expect(box!.y + box!.height - pan).toBeLessThanOrEqual(450);
  expect(await page.evaluate(() => document.documentElement.scrollWidth === document.documentElement.clientWidth)).toBe(true);
}

for (const width of [320, 390]) {
  test(`keyboard focus/drop/restore is conservative without a layout jump at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 }); const data = await open(page);
    const nav = page.locator(".mobile-bottom-nav"); const title = page.getByRole("textbox", { name: "Title", exact: true });
    await focus(title); await expect(nav).toBeVisible();
    await viewport(page, { height: 770 }); await expect(nav).toBeVisible();
    const before = await page.evaluate(() => ({ scroll: scrollY, height: document.documentElement.scrollHeight }));
    await viewport(page, { height: 450 }); await expect(nav).toBeHidden();
    expect(await page.evaluate(() => ({ scroll: scrollY, height: document.documentElement.scrollHeight }))).toEqual(before);
    await page.screenshot({ path: info.outputPath(`keyboard-hidden-${width}.png`) });
    await viewport(page, { height: 844 }); await expect(nav).toBeVisible(); await expect(title).toBeFocused();
    await page.screenshot({ path: info.outputPath(`keyboard-restored-${width}.png`) });
    await focus(page.getByRole("combobox", { name: "Status", exact: true })); await viewport(page, { height: 450 }); await expect(nav).toBeVisible();
    await viewport(page, { height: 844 }); await title.evaluate(el => (el as HTMLInputElement).readOnly = true); await focus(title);
    await viewport(page, { height: 450 }); await expect(nav).toBeVisible();
    await viewport(page, { height: 844 }); await title.evaluate(el => (el as HTMLInputElement).readOnly = false); await focus(title);
    await viewport(page, { height: 450, scale: 2 }); await expect(nav).toBeVisible();
    await viewport(page, { height: 844, scale: 1 }); await viewport(page, { height: 450 }); await expect(nav).toBeHidden();
    await page.evaluate(() => window.dispatchEvent(new Event("orientationchange"))); await expect(nav).toBeVisible();
    await page.screenshot({ path: info.outputPath(`conservative-${width}.png`) });
    expect(data.fixture.calls.every(x => x.startsWith("GET "))).toBe(true); expect(data.forbidden).toEqual([]);
  });

  test(`Details, comparable and listing Save use the visible keyboard edge at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 }); const data = await open(page);
    const nav = page.locator(".mobile-bottom-nav");
    await focus(page.getByRole("textbox", { name: "Title", exact: true })); await viewport(page, { height: 450 }); await expect(nav).toBeHidden();
    await aboveKeyboard(page, page.locator("#core-details-panel").getByRole("button", { name: "Save", exact: true }));
    await page.screenshot({ path: info.outputPath(`details-save-${width}.png`) });
    await page.getByRole("tab", { name: "Pricing", exact: true }).click();
    const add = page.getByRole("button", { name: "Add comparable", exact: true });
    const form = page.locator("form").filter({ has: add });
    await focus(form.getByRole("textbox", { name: "Notes", exact: true })); await expect(nav).toBeHidden();
    await aboveKeyboard(page, add); await page.screenshot({ path: info.outputPath(`comparable-${width}.png`) });
    await viewport(page, { height: 844, offsetTop: 0 }); await page.getByRole("button", { name: "List on eBay", exact: true }).click();
    const editor = page.locator(".listing-editor"); await expect(editor).toBeVisible();
    await editor.evaluate(el => el.scrollIntoView({ block: "start" }));
    await focus(editor.getByRole("textbox", { name: "Title", exact: true })); await viewport(page, { height: 450, offsetTop: 20 });
    await expect(nav).toBeHidden();
    const bar = page.locator(".listing-save-bar"); await expect(bar).toBeVisible();
    await expect.poll(async () => { const box = await bar.boundingBox(); return Math.round(box!.y + box!.height); }).toBe(470);
    expect((await bar.boundingBox())!.y).toBeGreaterThanOrEqual(20);
    const title = editor.getByRole("textbox", { name: "Title", exact: true });
    await title.evaluate(el => {
      const bar = document.querySelector(".listing-save-bar")!.getBoundingClientRect();
      window.scrollBy(0, Math.max(0, el.getBoundingClientRect().bottom - bar.top + 16));
    });
    await expect.poll(async () => (await title.boundingBox())!.y + (await title.boundingBox())!.height).toBeLessThanOrEqual((await bar.boundingBox())!.y - 8);
    await page.screenshot({ path: info.outputPath(`listing-save-${width}.png`) });
    await page.evaluate(() => Object.defineProperty(window, "innerHeight", { configurable: true, value: 450 }));
    await viewport(page, { height: 450, offsetTop: 20 });
    await expect.poll(async () => { const box = await bar.boundingBox(); return Math.round(box!.y + box!.height); }).toBe(470);
    await page.evaluate(() => Object.defineProperty(window, "innerHeight", { configurable: true, value: 844 }));
    await viewport(page, { height: 844, offsetTop: 0 }); await expect(nav).toBeVisible();
    const barBox = await bar.boundingBox(), navBox = await nav.boundingBox();
    expect(barBox!.y + barBox!.height).toBeLessThanOrEqual(navBox!.y + 1);
    expect(data.fixture.calls.every(x => x.startsWith("GET "))).toBe(true); expect(data.forbidden).toEqual([]);
  });
}

test("all draft entry errors show sold-out refusal and desktop nav is unaffected", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 844 }); const data = await open(page, "unlisted");
  await focus(page.getByRole("textbox", { name: "Title", exact: true })); await viewport(page, { height: 450 });
  expect(await page.evaluate(() => document.documentElement.dataset.mobileKeyboard)).toBeUndefined();
  await page.getByRole("button", { name: "List on eBay", exact: true }).click();
  await expect(page.getByText("Sold out \u2014 nothing to list.", { exact: true })).toBeVisible();
  expect(data.forbidden).toEqual([]);
});
