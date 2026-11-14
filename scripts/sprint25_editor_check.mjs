// Isolated browser proof: every API request is intercepted; no live DB or eBay.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
process.chdir(path.join(root, "frontend"));
const require = createRequire(path.join(root, "frontend/package.json"));
const viteApi = await import(pathToFileURL(require.resolve("vite")));
const createServer = viteApi.createServer || viteApi.default.createServer;
const { chromium } = await import(pathToFileURL(process.env.MAGPIE_PLAYWRIGHT_MODULE || "D:/Magpie/scratch/phase3-browser/node_modules/playwright-core/index.mjs"));
const fixture = JSON.parse(fs.readFileSync(path.join(root, "frontend/src/fixtures/listingEditor.json"), "utf8"));
const output = path.join(root, "docs/evidence/sprint25/phase3-fixes");
fs.mkdirSync(output, { recursive: true });
const virtual = "virtual:phase3-editor.tsx";
const html = '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body><div id="root"></div><script type="module" src="/@id/virtual:phase3-editor.tsx"></script></body></html>';
const server = await createServer({
  root: path.join(root, "frontend"),
  server: { host: "127.0.0.1", port: 5177, strictPort: true, proxy: {} },
  plugins: [{ name: "isolated-listing-editor", enforce: "pre",
    configResolved(config) { config.server.proxy = undefined; },
    resolveId(id) { return id === virtual ? "\0" + virtual : undefined; },
    load(id) { return id === "\0" + virtual ? `
      import React from 'react'; import {createRoot} from 'react-dom/client';
      import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
      import {ListingPanel} from '/src/components/ListingPanel.tsx';
      import {AppShell} from '/src/components/AppShell.tsx';
      import {MemoryRouter,Routes,Route} from 'react-router-dom';
      import fixture from '/src/fixtures/listingEditor.json'; import '/src/styles/index.css';
      const content=React.createElement('div',{style:{maxWidth:1200,margin:'auto',padding:16}},React.createElement('h1',{style:{fontSize:24,marginBottom:16}},'Isolated listing editor check'),React.createElement(ListingPanel,{item:fixture.item}));
      createRoot(document.getElementById('root')).render(React.createElement(QueryClientProvider,{client:new QueryClient({defaultOptions:{queries:{retry:false}}})},React.createElement(MemoryRouter,{initialEntries:['/__editor_check/']},React.createElement(Routes,null,React.createElement(Route,{element:React.createElement(AppShell)},React.createElement(Route,{path:'/__editor_check/',element:content}))))));
    ` : undefined; },
    configureServer(vite) { vite.middlewares.use(async (req, res, next) => {
      if (req.url?.split("?")[0] !== "/__editor_check/") return next();
      res.setHeader("Content-Type", "text/html");
      res.end(await vite.transformIndexHtml("/__editor_check/", html));
    }); }
  }]
});
let browser;
const errors = [];
try {
  assert.equal(server.config.server.proxy, undefined);
  await server.listen();
  const origin = "http://127.0.0.1:5177";
  browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  const calls = [], unexpected = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  await page.route("**/*", async (route) => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== origin) { unexpected.push("Non-local browser request"); return route.abort(); }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const key = `${request.method()} ${url.pathname}`;
    calls.push(key);
    let body;
    if (/\/items\/[^/]+\/listing-drafts\/$/.test(url.pathname) && request.method() === "GET") body = { results: [fixture.draft] };
    else if (url.pathname === "/api/listing-boilerplates/") body = { results: [] };
    else if (url.pathname.endsWith("/editor/")) body = fixture.editor;
    else if (url.pathname.endsWith("/category-children/")) {
      const id = url.searchParams.get("category_id");
      const nodes = { "281": { category_id: "281", category_name: "Jewellery & Watches", is_leaf: false }, "10210": { category_id: "10210", category_name: "Gold", is_leaf: false }, "139965": { category_id: "139965", category_name: "Nugget", is_leaf: true } };
      body = { category: nodes[id], children: [id === "281" ? nodes["10210"] : nodes["139965"]], fetched_at: "2026-11-14T00:00:00Z", provenance: "Isolated Taxonomy branch fixture", marketplace: "EBAY_AU" };
    }
    else if (url.pathname === "/api/ebay/status/") body = { connected: true, environment: "production" };
    else if (url.pathname.includes("merchant-location")) body = { location: null };
    else if (request.method() === "PATCH" && url.pathname === `/api/listing-drafts/${fixture.draft.id}/`) {
      const { expected_updated_at, editor_save, price_choice, ...fields } = request.postDataJSON();
      assert.equal(editor_save, true);
      assert.equal(expected_updated_at, fixture.draft.updated_at);
      for (const [field, value] of Object.entries(fields)) {
        if (JSON.stringify(value) !== JSON.stringify(fixture.draft[field])) fixture.editor.sources[field] = "Human edit in listing editor";
      }
      fixture.draft = { ...fixture.draft, ...fields, updated_at: new Date().toISOString() };
      fixture.editor.staged_local_changes = true;
      body = fixture.draft;
    } else { unexpected.push(key); return route.fulfill({ status: 500, json: { detail: "Unexpected isolated request" } }); }
    return route.fulfill({ json: body });
  });
  await page.goto(origin + "/__editor_check/");
  await page.getByLabel("Title", { exact: true }).waitFor();
  await page.getByText("Not used by this category", { exact: true }).waitFor();
  const checkFit = async () => {
    const measured = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth,
      fields: [...document.querySelectorAll(".listing-editor input,.listing-editor select,.listing-editor textarea")].every((node) => node.getBoundingClientRect().right <= innerWidth + 1),
      buttons: [...document.querySelectorAll(".listing-editor button")].filter((node) => node.getClientRects().length).every((node) => node.getBoundingClientRect().height >= 43),
      save_bottom: document.querySelector('.listing-save-bar').getBoundingClientRect().bottom,
      nav_top: document.querySelector('.mobile-bottom-nav').getBoundingClientRect().top }));
    assert.ok(measured.scroll <= measured.width, JSON.stringify(measured));
    assert.ok(measured.fields && measured.buttons, JSON.stringify(measured));
    if (measured.width === 390) assert.ok(measured.save_bottom <= measured.nav_top + 1, JSON.stringify(measured));
    return measured;
  };
  const phone = await checkFit();
  await page.locator(".listing-metadata").screenshot({ path: path.join(output, "phone-metadata.png") });
  await page.getByRole('button', { name: 'Browse categories' }).click();
  await page.getByLabel('Browse from category ID').fill('281');
  await page.getByRole('button', { name: 'Open branch', exact: true }).click();
  await page.getByRole('button', { name: 'Open Gold', exact: true }).click();
  await page.getByRole('button', { name: 'Select Nugget', exact: true }).waitFor();
  await page.getByRole('region', { name: 'Browse eBay categories' }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(output, 'phone-category-browse.png') });
  await page.getByRole('button', { name: 'Select Nugget', exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill("Full human title survives save and resume");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByText("Saved", { exact: true }).waitFor();
  assert.equal(fixture.draft.title, "Full human title survives save and resume");
  await page.getByLabel("Title", { exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(output, "phone-title-price.png") });
  await page.getByText('Photos', { exact: true }).scrollIntoViewIfNeeded();
  await checkFit();
  await page.screenshot({ path: path.join(output, 'phone-photos-save.png') });
  await page.reload();
  assert.equal(await page.getByLabel("Title", { exact: true }).inputValue(), "Full human title survives save and resume");
  await checkFit();
  await page.setViewportSize({ width: 1440, height: 1000 });
  const desktop = await checkFit();
  await page.screenshot({ path: path.join(output, "desktop-editor.png") });
  assert.deepEqual(unexpected, []);
  assert.deepEqual(errors, []);
  assert.ok(!calls.some((value) => /stage|publish|withdraw|aspects-check|staged-review/.test(value)));
  console.log(JSON.stringify({ phone, desktop, local_save_and_resume: true, unexpected_requests: unexpected.length, page_errors: errors.length, api_requests: calls.length, live_database_access: false }));
} catch (error) {
  console.error(JSON.stringify({ browser_errors: errors }));
  throw error;
} finally {
  await browser?.close();
  await server.close();
}
