import { expect, test, type Page } from "@playwright/test";
import { phase6Fixture } from "./phase6.fixture";
import * as data from "./sprint28.data";

const phase = process.env.SPRINT28_PHASE || "after";
async function open(page: Page, entry = "/", large = false, options: { failStats?: boolean; alerts?: boolean } = {}) {
  const item = phase6Fixture("unlisted"); const calls: string[] = [], errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.route("**/*", async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== "http://127.0.0.1:4179") { errors.push(url.origin); return route.abort(); }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    if (request.method() !== "GET") { errors.push(request.method() + url.pathname); return route.abort(); }
    calls.push(url.pathname + url.search);
    const extra = [data.tile("stock_on_hand", "Stock on hand", "integer", "10", "9 known-cost units; 1 unit with unknown cost."), data.tile("ebay_listings", "eBay listings", "integer", "1", "Marked active in Magpie; not live-verified.")];
    const homeSummary = { ...data.summary, tiles: { ...data.summary.tiles, ...Object.fromEntries(extra.map(t=>[t.id,t])) }, alerts: options.alerts ? [{id:"publish",count:1,label:"Publish results need checking",href:"/ebay#publish-results"}] : [] };
    if (url.searchParams.get("range") === "this_month") {
      homeSummary.tiles.realised_profit = { ...data.summary.tiles.realised_profit!, label:"Profit this month", state:"known" };
      homeSummary.tiles.items_sold = { ...data.summary.tiles.items_sold!, label:"Units sold this month" };
    }
    const analytics: Record<string, unknown> = { summary: phase === "before" ? data.summary : homeSummary, pnl: data.pnl, "by-category": data.byCategory, "estimate-vs-actual": data.estimate, aging: data.aging, "listing-opportunities": data.opportunities };
    if (url.pathname === "/api/dashboard/preferences/") return route.fulfill({ json: phase === "before" ? data.preference : { ...data.preference, kpi_tiles:["realised_profit","items_sold","stock_on_hand","ebay_listings"], available_tiles:[...data.availableTiles,...extra] } });
    if (url.pathname.startsWith("/api/analytics/")) return route.fulfill(options.failStats ? {status:503,json:{detail:"Synthetic unavailable stats"}} : { json: analytics[url.pathname.split("/")[3]] });
    if (url.pathname === "/api/profit/ledger/") return route.fulfill({ json: data.sampleLedger });
    if (url.pathname === "/api/items/") return route.fulfill({ json: { count: 1, next: null, previous: null, results: [item.item] } });
    if (["/api/ebay/order-staging/", "/api/ebay/order-duplicates/"].includes(url.pathname)) return route.fulfill({ json: { count: 0, next: null, previous: null, results: [] } });
    if (url.pathname === "/api/ebay/status/") return route.fulfill({ json: { configured: false, connected: false, environment: "sandbox", snapshot: null, order_sync: null } });
    try { return route.fulfill({ json: item.response(url.href) }); }
    catch(e) { errors.push(String(e)); return route.abort(); }
  });
  await page.goto(`/e2e/sprint28.html?entry=${encodeURIComponent(entry)}`);
  if (large) await page.addStyleTag({ content: "html { font-size: 20px !important; }" });
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  if (entry === "/" || entry === "/dashboard") await expect(options.failStats ? page.getByText("Quick stats are unavailable.") : page.locator(".kpi-grid")).toBeVisible();
  if (entry.startsWith("/profit")) await expect(page.getByText("Loss-making test sale", { exact: true })).toBeVisible();
  return { calls, errors };
}

for (const width of [320, 390]) for (const large of [false, true]) {
  test(`${phase} Home and Profit geometry ${width}px ${large ? "large" : "normal"}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 }); const rows = [];
    for (const entry of ["/", "/profit"]) {
      const proof = await open(page, entry, large);
      const sizes = await page.evaluate(() => ({ height: document.documentElement.scrollHeight, width: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }));
      await page.screenshot({ path: info.outputPath(`${phase}-${entry === "/" ? "home" : "profit"}-${width}-${large ? "large" : "normal"}.png`), fullPage: true });
      rows.push({ entry, ...sizes, calls: proof.calls });
      if (phase === "after") expect(sizes.scrollWidth).toBe(sizes.width);
      expect(proof.errors).toEqual([]);
    }
    await info.attach("page-measurements", { body: JSON.stringify({ phase, width, large, rows }, null, 2), contentType: "application/json" });
  });
}

for (const width of [320, 390]) test(`${phase} task paths ${width}px`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 844 }); const rows = [];
  for (const task of ["Add item", "Find an item", "Record a sale", "eBay orders", "profit figures"]) {
    const proof = await open(page); let taps = 0;
    await page.evaluate(() => { let previous = scrollY; (window as unknown as { taskScroll: number }).taskScroll = 0; window.addEventListener("scroll", () => { (window as unknown as { taskScroll: number }).taskScroll += Math.abs(scrollY - previous); previous = scrollY; }, { passive: true }); });
    const tap = async (target: ReturnType<Page["getByRole"]>) => { await target.click(); taps++; };
    const nav = page.locator(".mobile-bottom-nav");
    if (task === "Add item") await tap(phase === "before" ? nav.getByRole("link", { name: "Add", exact: true }) : page.getByRole("link", { name: "Add item", exact: true }));
    if (task === "Find an item") { await tap(phase === "before" ? nav.getByRole("link", { name: "Items", exact: true }) : page.getByRole("link", { name: "Find an item", exact: true })); await page.getByPlaceholder("Search").click(); taps++; }
    if (task === "profit figures") await tap(nav.getByRole("link", { name: "Profit", exact: true }));
    if (task === "Record a sale") {
      await tap(phase === "before" ? nav.getByRole("link", { name: "Items", exact: true }) : page.getByRole("link", { name: "Record a sale", exact: true }));
      await tap(page.getByRole("link", { name: /TEST-EDITOR/ }).first());
      if (phase === "before") { await page.getByRole("tab", { name: "Sales", exact: true }).evaluate(el => el.scrollIntoView({ inline: "center", block: "nearest" })); await tap(page.getByRole("tab", { name: "Sales", exact: true })); }
      await expect(page.getByRole("button", { name: "Record sale", exact: true })).toBeAttached();
    }
    if (task === "eBay orders") {
      await tap(phase === "before" ? nav.getByRole("link", { name: "eBay", exact: true }) : page.getByRole("link", { name: "eBay orders", exact: true }));
      if (phase === "before") await tap(page.getByRole("link", { name: "Open eBay orders", exact: true }));
    }
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
    rows.push({ task, taps, destination: await page.getByTestId("destination").textContent(), scroll: await page.evaluate(() => (window as unknown as { taskScroll: number }).taskScroll) });
    expect(proof.errors).toEqual([]); expect(proof.calls.every(call => call.startsWith("/api/"))).toBe(true);
  }
  await info.attach("task-measurements", { body: JSON.stringify({ phase, width, rows }, null, 2), contentType: "application/json" });
});

if (phase === "after") {
  test("Home has no chart requests; quick tasks survive stats failure and Back returns to Home", async ({page}) => {
    const proof = await open(page,"/",false,{failStats:true});
    const actions = page.getByRole("region",{name:"Quick actions"});
    for (const name of ["Add item","Find an item","eBay hub","Buy calculator","Record a sale","eBay orders"]) {
      const link = actions.getByRole("link",{name,exact:true}); const box=await link.boundingBox(); expect(box!.height).toBeGreaterThanOrEqual(44);
    }
    await actions.getByRole("link",{name:"Record a sale",exact:true}).click();
    await expect(page.getByRole("heading",{name:"Record a sale: choose an item"})).toBeVisible();
    await page.getByRole("link",{name:/TEST-EDITOR/}).click();
    await expect(page.getByRole("tab",{name:"Sales",exact:true})).toHaveAttribute("aria-selected","true");
    await page.evaluate(()=>(window as unknown as {s28Back:()=>void}).s28Back());
    await expect(page.getByRole("heading",{name:"Record a sale: choose an item"})).toBeVisible();
    await page.evaluate(()=>(window as unknown as {s28Back:()=>void}).s28Back());
    await expect(page.getByRole("heading",{name:"Home",exact:true})).toBeVisible();
    expect(proof.calls.some(p=>/analytics\/(pnl|by-category|estimate-vs-actual|aging|listing-opportunities)/.test(p))).toBe(false);
    expect(proof.errors).toEqual([]);
  });
  test("old dashboard anchors redirect with filters; every chart and accountant export remain", async ({page}) => {
    const proof=await open(page,"/dashboard?range=6m#estimate-vs-actual");
    await expect(page.getByTestId("destination")).toHaveText("/profit?chart_range=6m#estimate-vs-actual");
    await expect(page.getByRole("heading",{name:"Charts & trends"})).toBeVisible();
    for(const name of ["Realised P&L over time","Estimate vs actual","Revenue / net proceeds","Margin by category","Sell-through & time-to-sale","Aging inventory","What's worth listing next"]) await expect(page.getByRole("heading",{name,exact:true})).toBeAttached();
    const csv=page.getByRole("link",{name:/Download CSV/}); const before=await csv.getAttribute("href");
    await page.getByRole("group",{name:"Chart filters"}).getByRole("combobox",{name:"Range",exact:true}).selectOption("this_month");
    await expect(page.getByTestId("destination")).toContainText("chart_range=this_month");
    expect(await csv.getAttribute("href")).toBe(before);
    expect(proof.errors).toEqual([]);
  });
  test("monthly tile and listing-priority shortcut reach their matching figures", async ({page}) => {
    await open(page);
    await page.locator(".kpi-grid").getByRole("link").first().click();
    await expect(page.getByTestId("destination")).toHaveText("/profit?range=this_month#profit-summary");
    await expect(page.getByLabel("Profit period")).toHaveValue("this_month");
    await open(page);
    await page.getByRole("link",{name:"What to list next",exact:true}).click();
    await expect(page.getByRole("heading",{name:"What's worth listing next",exact:true})).toBeInViewport();
  });
  test("urgent strip routes to the existing queue, never reconciles on opening", async ({page}) => {
    const proof=await open(page,"/",false,{alerts:true});
    await page.getByRole("region",{name:"Needs attention"}).getByRole("link").click();
    await expect(page.getByTestId("destination")).toHaveText("/ebay#publish-results");
    await expect(page.getByRole("region",{name:"Check publish result",exact:true})).toBeInViewport();
    await expect(page.getByRole("region",{name:"Check publish result",exact:true})).toBeFocused();
    expect(proof.errors).toEqual([]);
  });
}
