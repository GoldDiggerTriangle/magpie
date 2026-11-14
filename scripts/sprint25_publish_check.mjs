// All browser API calls are intercepted. No live database or eBay access.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
process.chdir(path.join(root, "frontend"));
const require = createRequire(path.join(root, "frontend/package.json"));
const vite = await import(pathToFileURL(require.resolve("vite")));
const createServer = vite.createServer || vite.default.createServer;
const { chromium } = await import(pathToFileURL(process.env.MAGPIE_PLAYWRIGHT_MODULE || "D:/Magpie/scratch/phase3-browser/node_modules/playwright-core/index.mjs"));
const fixture = JSON.parse(fs.readFileSync(path.join(root, "frontend/src/fixtures/listingEditor.json"), "utf8"));
let draft = structuredClone(fixture.draft);
let verified = false;
let mode = "full";
const review = () => ({
  id: verified ? "review-verified" : "review-drift", mode, draft_revision: draft.updated_at,
  expires_at: "2099-01-01T00:00:00Z", offer_id: draft.channel_data.offer_id, sku: fixture.item.sku,
  listing: Object.fromEntries(["title", "description_html", "listing_format", "quantity", "currency"].map((key) => [key, draft[key]])),
  price: draft.price, mapping: draft.channel_data, sources: { ...fixture.editor.sources, price: "Human asking price" },
  specifics: draft.item_specifics, photos: draft.photo_ids.map((id) => ({ id, sha256: "isolated-owned-photo", derivative: "", url: `/media/${id}.png` })),
  metadata: fixture.editor.metadata, fees: [{ type: "InsertionFee", currency: "AUD", value: "0.06" }],
  checks: [], publish_checks: verified ? [] : [{ key: "staged_drift", field: "title", message: "Local content differs from the staged offer. Explicitly update, then review again." }],
  can_stage: mode === "full", can_publish: verified
});
const output = path.join(root, "docs/evidence/sprint25/phase5-publish");
const ownPhotoPath = process.env.MAGPIE_PROOF_OWN_PHOTO;
const ownPhoto = ownPhotoPath ? fs.readFileSync(ownPhotoPath) : null;
fs.mkdirSync(output, { recursive: true });
const virtual = "virtual:publish-proof.tsx";
const server = await createServer({ root: path.join(root, "frontend"), server: { host: "127.0.0.1", port: 5178, strictPort: true, proxy: {} }, plugins: [{
  name: "isolated-publish-proof", enforce: "pre",
  configResolved(config) { config.server.proxy = undefined; },
  resolveId(id) { return id === virtual ? "\0"+virtual : undefined; },
  load(id) { return id === "\0"+virtual ? `
    import React,{useState,useEffect} from 'react'; import {createRoot} from 'react-dom/client';
    import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
    import {MemoryRouter,Routes,Route} from 'react-router-dom';
    import {AppShell} from '/src/components/AppShell.tsx';
    import {ListingWorkflow} from '/src/components/ListingWorkflow.tsx';
    import {getWorkflowDraft} from '/src/api/listingWorkflow.ts';
    import fixture from '/src/fixtures/listingEditor.json'; import '/src/styles/index.css';
    function Proof(){const [draft,setDraft]=useState(null); const mode=new URLSearchParams(location.search).get('mode')||'full'; useEffect(()=>{getWorkflowDraft(fixture.draft.id).then(setDraft)},[]); if(!draft)return React.createElement('p',null,'Loading own draft');
      return React.createElement('main',{style:{maxWidth:1100,margin:'auto',padding:16}},React.createElement('h1',{style:{fontSize:24,marginBottom:16}},'Isolated listing review'),React.createElement(ListingWorkflow,{draft,item:fixture.item,mode,onUpdated:setDraft}));}
    createRoot(document.getElementById('root')).render(React.createElement(QueryClientProvider,{client:new QueryClient({defaultOptions:{queries:{retry:false}}})},React.createElement(MemoryRouter,null,React.createElement(Routes,null,React.createElement(Route,{element:React.createElement(AppShell)},React.createElement(Route,{path:'*',element:React.createElement(Proof)}))))));
  ` : undefined; },
  configureServer(vite) { vite.middlewares.use(async (req,res,next) => {
    if (!req.url?.startsWith("/__publish_proof/")) return next();
    res.setHeader("Content-Type", "text/html");
    res.end(await vite.transformIndexHtml(req.url, '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body><div id="root"></div><script type="module" src="/@id/virtual:publish-proof.tsx"></script></body></html>'));
  }); }
}] });
let browser;
const calls = [], unexpected = [], errors = [];
try {
  await server.listen();
  browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/*", async (route) => {
    const req = route.request(), url = new URL(req.url());
    if (url.hostname !== "127.0.0.1") { unexpected.push("nonlocal request"); return route.abort(); }
    if (url.pathname.startsWith("/media/")) return route.fulfill({ contentType: ownPhoto ? "image/jpeg" : "image/png", body: ownPhoto || Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==", "base64") });
    if (!url.pathname.startsWith("/api/")) return route.continue();
    calls.push(req.method()+" "+url.pathname);
    if (req.method() === "GET" && url.pathname === `/api/listing-drafts/${draft.id}/`) return route.fulfill({ json: draft });
    if (url.pathname.endsWith("/preview/")) { mode = req.postDataJSON().mode; return route.fulfill({ json: review() }); }
    if (url.pathname.endsWith("/stage/")) {
      assert.equal(req.postDataJSON().review_id, "review-drift"); verified = true;
      draft.updated_at = "2026-11-15T01:00:00Z";
      return route.fulfill({ json: draft });
    }
    if (url.pathname.endsWith("/publish/")) {
      assert.equal(req.postDataJSON().review_id, "review-verified");
      assert.equal(req.postDataJSON().mode, "quick");
      assert.equal(req.postDataJSON().confirm_sku, "");
      draft.status = "published"; draft.channel_data.listing_id = "isolated-test-listing";
      return route.fulfill({ json: draft });
    }
    unexpected.push(req.method()+" "+url.pathname); return route.abort();
  });
  await page.goto("http://127.0.0.1:5178/__publish_proof/");
  await page.getByRole("button", { name: "Review listing", exact: true }).click();
  await page.getByText("Local content differs from the staged offer.", { exact: false }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Confirm publish to eBay" }).isDisabled(), true);
  const fit = async () => {
    const measured = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth,
      buttons: [...document.querySelectorAll('.listing-review button')].filter((e) => e.getClientRects().length).every((e) => e.getBoundingClientRect().height >= 44) }));
    assert.ok(measured.scroll <= measured.width && measured.buttons, JSON.stringify(measured)); return measured;
  };
  const phone = await fit();
  await page.getByText("Before publishing", { exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(output, "phone-drift-blocked.png") });
  await page.getByRole("button", { name: "Update staged offer" }).click();
  await page.getByLabel(`Type ${fixture.item.sku} to confirm`).waitFor();
  await page.screenshot({ path: path.join(output, "phone-staged-review-confirm.png"), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  const desktop = await fit();
  await page.screenshot({ path: path.join(output, "desktop-staged-review.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("http://127.0.0.1:5178/__publish_proof/?mode=quick");
  await page.getByRole("button", { name: "Preview eBay listing" }).click();
  const post = page.getByRole("button", { name: "Post live to eBay" });
  await post.waitFor(); await post.scrollIntoViewIfNeeded();
  assert.equal(await post.isEnabled(), true);
  assert.equal(await page.getByRole("textbox").count(), 0);
  await fit(); await page.screenshot({ path: path.join(output, "phone-quick-preview.png") });
  await post.click(); await page.getByRole("link", { name: "Open live listing" }).waitFor();
  assert.equal(calls.filter((c) => c.endsWith("/publish/")).length, 1);
  assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  console.log(JSON.stringify({ phone, desktop, mocked_update: true, mocked_quick_publish: true, unexpected_requests: 0, live_database_access: false, real_ebay_calls: 0 }));
} finally { await browser?.close(); await server.close(); }
