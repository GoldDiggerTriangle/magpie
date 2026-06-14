import { describe, expect, test, vi } from "vitest";

import { correctSaleRecord, createItemSale, listItemSales, listSales } from "./sales";

function mockFetch(data: unknown = {}) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(data), {
    status: 200,
    headers: { "content-type": "application/json" }
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("Sprint 10 sales API module", () => {
  test("listSales uses the global sales endpoint", async () => {
    const fetchMock = mockFetch({ count: 0, next: null, previous: null, results: [] });

    await listSales();

    expect(fetchMock).toHaveBeenCalledWith("/api/sales/", expect.any(Object));
  });

  test("listItemSales uses the item-scoped endpoint", async () => {
    const fetchMock = mockFetch({ count: 0, next: null, previous: null, results: [] });

    await listItemSales("item-1");

    expect(fetchMock).toHaveBeenCalledWith("/api/items/item-1/sales/", expect.any(Object));
  });

  test("createItemSale posts manual sale payload", async () => {
    const fetchMock = mockFetch({ id: "sale-1" });

    await createItemSale("item-1", {
      sale_date: "2026-06-14",
      quantity: 2,
      sale_price: "80.00",
      channel: "manual",
      actual_fees_total: "8.00",
      actual_shipping_cost: "5.00",
      cost_basis_override: null,
      listing_draft: null,
      notes: "counter sale"
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/items/item-1/sales/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          sale_date: "2026-06-14",
          quantity: 2,
          sale_price: "80.00",
          channel: "manual",
          actual_fees_total: "8.00",
          actual_shipping_cost: "5.00",
          cost_basis_override: null,
          listing_draft: null,
          notes: "counter sale"
        })
      })
    );
  });

  test("correctSaleRecord posts to the correction endpoint", async () => {
    const fetchMock = mockFetch({ id: "sale-2", corrected_from: "sale-1" });

    await correctSaleRecord("sale-1", {
      sale_date: "2026-06-14",
      quantity: 3,
      sale_price: "120.00",
      channel: "manual"
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sales/sale-1/correct/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          sale_date: "2026-06-14",
          quantity: 3,
          sale_price: "120.00",
          channel: "manual"
        })
      })
    );
  });
});
