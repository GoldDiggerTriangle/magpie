import { describe, expect, test, vi } from "vitest";

import { getCategorySchema } from "./categories";
import { createComparable } from "./comparables";
import { getResearchLinks } from "./research";
import { createValuationReport, getReportProfit } from "./valuation";

function mockFetch(data: unknown = {}) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(data), {
    status: 200,
    headers: { "content-type": "application/json" }
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("Sprint 2 API modules", () => {
  test("createComparable posts to comparables endpoint", async () => {
    const fetchMock = mockFetch({ id: "comp-1" });

    await createComparable({
      item: "item-1",
      kind: "sold",
      source: "Manual",
      title: "Comp",
      price: "10.00",
      shipping: null,
      currency: "AUD",
      condition: "",
      url: "",
      observed_on: null,
      notes: ""
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/comparables/", expect.objectContaining({
      method: "POST",
      body: expect.stringContaining("\"kind\":\"sold\"")
    }));
  });

  test("research links and profit endpoints use the item/report routes", async () => {
    const fetchMock = mockFetch({ links: [] });

    await getResearchLinks("item-1");
    await getReportProfit("report-1", "12.50");

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/items/item-1/research-links/", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/valuation-reports/report-1/profit/?price=12.50", expect.any(Object));
  });

  test("getCategorySchema uses the category schema route", async () => {
    const fetchMock = mockFetch({ profile_key: "coins", fields: [] });

    await getCategorySchema("cat-1");

    expect(fetchMock).toHaveBeenCalledWith("/api/categories/cat-1/schema/", expect.any(Object));
  });

  test("createValuationReport posts through the item route", async () => {
    const fetchMock = mockFetch({ id: "report-1" });

    await createValuationReport("item-1", {
      strategy: "comp_based",
      comp_links: [{ comparable: "comp-1", included: true, exclude_reason: "" }]
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/items/item-1/valuation-reports/", expect.objectContaining({
      method: "POST",
      body: expect.stringContaining("\"strategy\":\"comp_based\"")
    }));
  });
});
