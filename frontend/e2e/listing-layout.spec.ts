import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { readFileSync } from "node:fs";

const fixture = JSON.parse(readFileSync(new URL("../src/fixtures/listingEditor.json", import.meta.url), "utf8"));
const healthFixture = JSON.parse(readFileSync(new URL("../src/fixtures/ebayHealth.json", import.meta.url), "utf8"));

const titles = { spaced: "Australian gold nugget specimen with original surface marks retained for review. ".repeat(2).slice(0, 80), unbroken: "N".repeat(80) };

async function isolatedListing(page: Page, state: "preview" | "staged" | "archived" | "published", title?: string) {
  const draft = structuredClone(fixture.draft);
  if (state !== "staged") delete (draft.channel_data as Record<string, unknown>).offer_id;
  draft.status = state === "preview" ? "draft" : state;
  if (title) draft.title = title;
  const forbidden: string[] = [];
  const context = structuredClone(fixture.editor);
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== "http://127.0.0.1:4179") { forbidden.push(url.origin); return route.abort(); }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const json = (body: unknown) => route.fulfill({ json: body });
    if (url.pathname === "/api/ebay/connection-health/" && request.method() === "GET") return json(healthFixture);
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
      fees: [{ type: "ListingFee", currency: "AUD", value: "0.06" }, { type: "InsertionFee", currency: "AUD", value: "0.06" }], can_stage: true, can_publish: state === "staged",
    });
    forbidden.push(`${request.method()} ${url.pathname}`);
    return route.abort();
  });
  await page.goto("/e2e/listing-layout.html");
  await expect(page.getByRole("textbox", { name: "Title", exact: true })).toHaveValue(draft.title);
  return forbidden;
}

for (const { width, fontSize } of [390, 320].flatMap((width) => [16, 20].map((fontSize) => ({ width, fontSize })))) {
  for (const state of ["preview", "published"] as const) {
    test(`Save bar fits ${state === "published" ? "read-only history" : "Saved"} at ${width}px with ${fontSize}px root text`, async ({ page }, info) => {
      await page.setViewportSize({ width, height: 844 });
      const forbidden = await isolatedListing(page, state, titles.unbroken);
      await page.addStyleTag({ content: `html { font-size: ${fontSize}px; }` });
      await page.getByRole("textbox", { name: "Title", exact: true }).scrollIntoViewIfNeeded();
      const bar = page.locator(".listing-save-bar");
      await expect(bar).toBeVisible();
      await expect(bar.getByRole("status")).toHaveText(state === "published" ? "Read-only history" : "Saved");
      const save = bar.getByRole("button", { name: "Save", exact: true });
      if (state === "published") await expect(save).toBeDisabled();
      else await expect(save).toBeEnabled();
      await expect.poll(() => bar.evaluate((element) => element.parentElement!.getBoundingClientRect().height >= element.getBoundingClientRect().height)).toBe(true);
      const layout = await bar.evaluate((element) => {
        const box = (node: Element) => {
          const { left, right, top, bottom } = node.getBoundingClientRect();
          return { left, right, top, bottom };
        };
        const status = element.querySelector('[role="status"]')!;
        const button = element.querySelector("button")!;
        const textRects = (node: Element) => {
          const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
          const rects: { left: number; right: number; top: number; bottom: number }[] = [];
          while (walker.nextNode()) {
            if (!walker.currentNode.textContent?.trim()) continue;
            const range = document.createRange();
            range.selectNodeContents(walker.currentNode);
            rects.push(...Array.from(range.getClientRects()).filter((rect) => rect.width > 0).map(({ left, right, top, bottom }) => ({ left, right, top, bottom })));
          }
          return rects;
        };
        return { bar: box(element), status: box(status), button: box(button), icon: box(button.querySelector("svg")!),
          buttonText: textRects(button), statusText: textRects(status), nav: box(document.querySelector(".mobile-bottom-nav")!),
          clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth };
      });
      await info.attach("save-bar-layout", { body: JSON.stringify(layout), contentType: "application/json" });
      await page.screenshot({ path: info.outputPath(`save-bar-${state}-${width}-${fontSize}.png`) });
      expect(new Set(layout.buttonText.map((rect) => Math.round(rect.top))).size, JSON.stringify(layout)).toBe(1);
      for (const rect of [...layout.buttonText, layout.icon]) {
        expect(rect.left).toBeGreaterThanOrEqual(layout.button.left);
        expect(rect.right).toBeLessThanOrEqual(layout.button.right);
        expect(rect.top).toBeGreaterThanOrEqual(layout.button.top);
        expect(rect.bottom).toBeLessThanOrEqual(layout.button.bottom);
      }
      for (const rect of layout.statusText) {
        expect(rect.left).toBeGreaterThanOrEqual(layout.status.left - 1);
        expect(rect.right).toBeLessThanOrEqual(layout.status.right + 1);
        expect(rect.bottom).toBeLessThanOrEqual(layout.status.bottom + 1);
      }
      expect(layout.status.right <= layout.button.left || layout.status.bottom <= layout.button.top).toBe(true);
      expect(layout.bar.left).toBeGreaterThanOrEqual(0);
      expect(layout.bar.right).toBeLessThanOrEqual(width);
      expect(layout.bar.bottom).toBeLessThanOrEqual(layout.nav.top + 1);
      expect(layout.scrollWidth).toBe(layout.clientWidth);
      await page.locator(".listing-save-slot").scrollIntoViewIfNeeded();
      await expect(bar).toBeVisible();
      const lastField = page.locator(".listing-editor fieldset").first();
      await expect.poll(async () => {
        const field = await lastField.boundingBox();
        const fixed = await bar.boundingBox();
        return Boolean(field && fixed && field.y + field.height <= fixed.y + 1);
      }).toBe(true);
      expect(forbidden).toEqual([]);
    });
  }
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
      await expect(page.getByText("AUD listing fee total: $0.06", { exact: true })).toBeVisible();
      await expect(page.getByLabel("Listing fee breakdown")).toContainText("Insertion Fee: $0.06");
      await expect(page.getByText("AUD listing fee total: $0.12", { exact: true })).toHaveCount(0);
      await fitsPhone(page, info, `${kind}-${state}-review`);
      if (kind === "spaced" && state === "staged") await page.getByRole("heading", { name: "eBay listing fee estimate" }).locator("..").screenshot({ path: info.outputPath("fee-total-390.png") });
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
