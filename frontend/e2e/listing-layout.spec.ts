import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { readFileSync } from "node:fs";

const fixture = JSON.parse(readFileSync(new URL("../src/fixtures/listingEditor.json", import.meta.url), "utf8"));

const titles = { spaced: "Australian gold nugget specimen with original surface marks retained for review. ".repeat(2).slice(0, 80), unbroken: "N".repeat(80) };

async function isolatedListing(page: Page, state: "preview" | "staged" | "archived", title?: string) {
  const draft = structuredClone(fixture.draft);
  if (state !== "staged") delete (draft.channel_data as Record<string, unknown>).offer_id;
  draft.status = state === "archived" ? "archived" : state === "staged" ? "staged" : "draft";
  if (title) draft.title = title;
  const forbidden: string[] = [];
  const context = structuredClone(fixture.editor);
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== "http://127.0.0.1:4179") { forbidden.push(url.origin); return route.abort(); }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const json = (body: unknown) => route.fulfill({ json: body });
    if (url.pathname === `/api/items/${fixture.item.id}/listing-drafts/` && request.method() === "GET") return json({ results: [draft] });
    if (url.pathname === "/api/listing-boilerplates/" && request.method() === "GET") return json({ results: [] });
    if (url.pathname === `/api/listing-drafts/${draft.id}/editor/` && request.method() === "GET") return json(context);
    if (url.pathname === `/api/listing-drafts/${draft.id}/readiness/` && request.method() === "GET") return json([]);
    if (url.pathname === `/api/listing-drafts/${draft.id}/` && request.method() === "PATCH") {
      const { editor_save: _save, expected_updated_at: _revision, price_choice: _price, ...fields } = request.postDataJSON();
      Object.assign(draft, fields, { updated_at: new Date().toISOString() });
      return json(draft);
    }
    if (url.pathname === `/api/listing-drafts/${draft.id}/preview/` && request.method() === "POST") return json({
      id: "isolated-review", draft_revision: draft.updated_at, expires_at: "2099-01-01T00:00:00Z", mode: "full", offer_id: state === "staged" ? draft.channel_data.offer_id : "",
      sku: fixture.item.sku, price: draft.price, sources: context.sources, mapping: draft.channel_data,
      listing: { title: draft.title, description_html: draft.description_html, listing_format: draft.listing_format, quantity: draft.quantity, currency: draft.currency },
      specifics: draft.item_specifics, photos: draft.photo_ids.map((id: string) => ({ id, sha256: "isolated-own-photo", derivative: "" })), metadata: context.metadata, checks: [], publish_checks: [],
      fees: [{ type: "InsertionFee", currency: "AUD", value: "0.06" }], can_stage: true, can_publish: state === "staged",
    });
    forbidden.push(`${request.method()} ${url.pathname}`);
    return route.abort();
  });
  await page.goto("/e2e/listing-layout.html");
  await expect(page.getByRole("textbox", { name: "Title", exact: true })).toHaveValue(draft.title);
  return forbidden;
}

async function fitsPhone(page: Page, info: TestInfo, label: string) {
  await page.evaluate(() => window.scrollTo({ left: 0 }));
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    overflowing: Array.from(document.querySelectorAll("body *")).filter((el) => {
      const box = el.getBoundingClientRect();
      return box.width > 0 && (box.right > innerWidth + 1 || box.left < -1);
    }).slice(0, 10).map((el) => ({ tag: el.tagName, class: el.className, width: el.getBoundingClientRect().width })),
  }));
  await info.attach(`${label}-dimensions`, { body: JSON.stringify(dimensions), contentType: "application/json" });
  expect(dimensions.scrollWidth, JSON.stringify(dimensions)).toBe(dimensions.clientWidth);
  expect(dimensions.overflowing, JSON.stringify(dimensions)).toEqual([]);
  await page.screenshot({ path: info.outputPath(`${label}-390.png`), fullPage: true });
  const target = label.endsWith("-review") ? page.locator(".listing-review h4").first()
    : label.endsWith("-archived") ? page.locator(".listing-draft-row .listing-title").first()
    : page.getByRole("textbox", { name: "Title", exact: true });
  await target.evaluate((el) => window.scrollTo({ left: 0, top: window.scrollY + el.getBoundingClientRect().top - 120 }));
  await page.screenshot({ path: info.outputPath(`${label}-viewport-390.png`) });
}

for (const [kind, title] of Object.entries(titles)) {
  test(`80-character ${kind} title fits editor, preview and staged review at 390px`, async ({ page }, info) => {
    expect(title).toHaveLength(80);
    for (const state of ["preview", "staged"] as const) {
      const forbidden = await isolatedListing(page, state);
      const input = page.getByRole("textbox", { name: "Title", exact: true });
      await input.fill(title);
      await expect(page.getByText("80/80", { exact: true })).toBeVisible();
      await expect(page.getByText("Saved", { exact: true })).toBeVisible();
      await expect(page.locator(".listing-draft-row .listing-title")).toHaveText(title);
      await fitsPhone(page, info, `${kind}-${state}-editor`);
      for (const control of await page.locator(".listing-editor input:not([type=checkbox]), .listing-editor select, .listing-editor textarea").all()) {
        if (await control.isVisible()) expect(await control.evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(16);
      }
      const archive = await page.getByRole("button", { name: "Archive", exact: true }).boundingBox();
      const counter = await page.getByText("80/80", { exact: true }).boundingBox();
      expect(archive!.x + archive!.width).toBeLessThanOrEqual(390);
      expect(counter!.x + counter!.width).toBeLessThanOrEqual(390);
      await page.getByRole("button", { name: "Review listing", exact: true }).click();
      await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
      await fitsPhone(page, info, `${kind}-${state}-review`);
      for (const control of await page.locator(".listing-review input, .listing-review select, .listing-review textarea").all()) {
        if (await control.isVisible()) expect(await control.evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(16);
      }
      for (const displayed of await page.locator(".listing-title").all()) {
        expect(await displayed.evaluate((el) => getComputedStyle(el).overflowWrap)).toBe("anywhere");
        expect(await displayed.evaluate((el) => getComputedStyle(el).whiteSpace)).toBe("normal");
      }
      expect(forbidden).toEqual([]);
      await page.unrouteAll();
    }
  });
  test(`archived ${kind} title wraps in its history row at 390px`, async ({ page }, info) => {
    const forbidden = await isolatedListing(page, "archived", title);
    await expect(page.getByRole("button", { name: "Archive", exact: true })).toBeDisabled();
    await fitsPhone(page, info, `${kind}-archived`);
    const row = page.locator("button").filter({ hasText: title }).first();
    await expect(row).toBeVisible();
    expect(await row.locator(".listing-title").evaluate((el) => getComputedStyle(el).overflowWrap)).toBe("anywhere");
    expect(await row.locator(".listing-title").evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
    expect(forbidden).toEqual([]);
  });
}
