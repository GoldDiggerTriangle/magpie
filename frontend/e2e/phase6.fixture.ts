import editorFixture from "../src/fixtures/listingEditor.json" with { type: "json" };
import healthFixture from "../src/fixtures/ebayHealth.json" with { type: "json" };

export const listingStates = ["unlisted", "drafted", "staged", "publishing", "publish_unknown", "failed", "published", "published-plus-active", "archived-history", "sold", "partially-sold"] as const;
export type ListingState = typeof listingStates[number];
const page = (results: unknown[] = []) => ({ count: results.length, next: null, previous: null, results });

// Entirely synthetic API records shared by the real-panel CI and browser gates.
export function phase6Fixture(state: ListingState = "staged", title = editorFixture.item.title) {
  const item = { ...structuredClone(editorFixture.item), title, current_valuation: null, location: null, acquisition: null,
    acquisition_cost: null, refurb_cost: null, inbound_shipping_cost: null, est_outbound_shipping: null,
    est_packaging_cost: null, estimated_value: null, min_price: null, lot: null, source: null,
    effective_source: null, disposition: "for_sale", scrapped_at: null, comps_count: 0,
    created_at: "2026-11-13T07:00:00Z", updated_at: "2026-11-13T07:00:00Z", owner: null,
    photos: editorFixture.item.photos.map((photo) => ({ ...photo, derivatives: [], fixup_status: "none", original_url: null, processed_url: null })) };
  if (state === "sold") Object.assign(item, { status: "sold", quantity_sold: 1, quantity_remaining: 0 });
  if (state === "partially-sold") Object.assign(item, { status: "partially_sold", quantity_total: 2, quantity_sold: 1 });
  const base = { ...structuredClone(editorFixture.draft), title };
  const published = { ...structuredClone(base), id: "published-history", status: "published", title: "Earlier published title", channel_data: { ...base.channel_data, listing_id: "test-listing" } };
  let drafts = [base];
  if (["unlisted", "drafted"].includes(state)) { base.status = "draft"; delete (base.channel_data as Record<string, unknown>).offer_id; }
  if (state === "unlisted") drafts = [];
  if (["publishing", "publish_unknown"].includes(state)) base.status = state;
  if (state === "failed") base.status = "publish_failed";
  if (state === "published") drafts = [published];
  // Deliberately history-first to prove the UI does not assume first == active.
  if (state === "published-plus-active") drafts = [published, base];
  if (state === "archived-history") { base.status = "archived"; delete (base.channel_data as Record<string, unknown>).offer_id; }
  const editor = structuredClone(editorFixture.editor);
  const calls: string[] = [];
  const evidenceRows: Record<string, unknown>[] = [];
  const category = { id: item.category, name: "Gold", slug: "gold", profile_key: "gold", sku_prefix: "GOLD", parent: null };
  const channel = { id: "channel-row", item: item.id, channel: "ebay", channel_label: "eBay", active: true, listed_at: item.created_at, ended_at: null };
  const hub = {
    as_of: "2026-11-17T00:00:00Z", provenance: "Owned local records; not a live eBay check",
    drafts: drafts.map((row) => ({ id: row.id, item_id: item.id, sku: item.sku, title: row.title, status: row.status, updated_at: row.updated_at,
      offer_id: row.channel_data.offer_id || "", listing_id: (row.channel_data as Record<string, unknown>).listing_id || "", publish_started_at: null, has_publish_error: state === "failed" })),
    listings: [{ id: "live-row", item_id: item.id, sku: item.sku, title, draft_id: published.id, listing_id: "test-listing", url: "", listed_at: item.created_at }],
    connection: { connected: true, configured: true, environment: "sandbox", requires_reconsent: false, access_token_expires_at: null, has_refresh_error: false, policies_fetched_at: "2026-01-01T00:00:00Z" },
    orders: { pending: 0, duplicates: 0, last_synced_at: null },
  };
  function response(path: string, method = "GET", body?: Record<string, unknown>): unknown {
    const url = new URL(path, "http://127.0.0.1:4179");
    const p = url.pathname;
    calls.push(`${method} ${p}`);
    if (p === `/api/items/${item.id}/listing-drafts/`) {
      if (method === "POST") { drafts = [base]; return base; }
      return page(drafts);
    }
    if (method === "POST" && p.endsWith("/preview/")) {
      const row = drafts.find((r) => p.includes(r.id)) ?? base;
      return { id: "review-isolated", mode: body?.mode || "full", draft_revision: row.updated_at, expires_at: "2099-01-01T00:00:00Z",
        sku: item.sku, offer_id: row.channel_data.offer_id || "", price: row.price, sources: editor.sources, mapping: row.channel_data,
        listing: { title: row.title, description_html: row.description_html, listing_format: row.listing_format, quantity: row.quantity, currency: row.currency },
        specifics: row.item_specifics, photos: row.photo_ids.map((id) => ({ id, sha256: "owned-fixture", derivative: "" })), metadata: editor.metadata,
        checks: [], publish_checks: [], fees: [{ type: "ListingFee", currency: "AUD", value: "0.06" }], can_stage: true, can_publish: Boolean(row.channel_data.offer_id) };
    }
    if (method === "POST" && p.endsWith("/reconcile/")) return drafts.find((row) => p.includes(row.id));
    if (method !== "GET") throw new Error(`Unexpected write in reachability gate: ${method} ${p}`);
    if (p === "/api/ebay/connection-health/") return healthFixture;
    if (p === "/api/ebay/hub/") return hub;
    if (p.endsWith("/ebay-quantity/")) return { item_id: item.id, sku: item.sku, state: "allocation_not_recorded", label: "Allocation not recorded", can_write: false, urgent: false };
    if (p === `/api/items/${item.id}/`) return item;
    if (p === "/api/categories/") return page([category]);
    if (p.endsWith("/schema/")) return { profile_key: "gold", fields: [{ name: "metal", label: "Metal", type: "text" }] };
    if (p === "/api/ai/status/") return { configured: true, enabled: false, provider: "fake", model_id: "offline-test", monthly_budget_cap_usd: "5", monthly_usage_usd: "0.001", disabled_reason: "Offline test; AI cannot run" };
    if (p.endsWith("/ai/references/")) return { search_terms: [], reference_links: [] };
    if (p.endsWith("/sold-searches/") || p.endsWith("/research-links/")) return { links: [] };
    if (p.endsWith("/pricing-evidence/")) return { currency: "AUD", source_links: [], headline: [], summary: { empty: true }, empty_state: { title: "No pricing evidence", detail: "Thin local records" }, grids: { condition_grade: [], sale_format: [], recency: [], source: [] } };
    if (p === "/api/evidence/lookup/") return { rows: evidenceRows, empty: !evidenceRows.length, empty_state: { title: "No matching evidence", detail: "No known-basis rows" } };
    if (p.endsWith("/copy-pack/")) return { sections: { title, description: "Own specimen. Marks retained.", price_line: "[price not set]", postage_pickup_line: "[postage not set]" }, price_source: { label: "Not selected", hint: "Human price required" }, whole_ad: title };
    if (p.endsWith("/editor/")) return editor;
    if (p === `/api/listing-drafts/${published.id}/`) return published;
    if (p === `/api/listing-drafts/${base.id}/`) return base;
    if (p.endsWith("/readiness/")) return [];
    if (p === "/api/channel-listings/") return page([channel]);
    const lists = ["locations", "lots", "sources", "field-suggestions", "comparables", "research-records", "fee-schedules", "listing-boilerplates"];
    if (lists.some((name) => p === `/api/${name}/`) || p.endsWith("/sales/") || p.endsWith("/valuation-reports/")) return page();
    throw new Error(`Missing synthetic API response: ${method} ${p}`);
  }
  return { item, base, published, drafts, hub, calls, response, evidenceRows };
}
