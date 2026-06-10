import { describe, expect, test, vi } from "vitest";

import { getMetalSpot } from "./valuation";


function mockFetch(data: unknown = {}) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(data), {
    status: 200,
    headers: { "content-type": "application/json" }
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}


describe("Sprint 3 API modules", () => {
  test("getMetalSpot uses the metals spot endpoint with refresh", async () => {
    const fetchMock = mockFetch({ metal: "gold" });

    await getMetalSpot("gold", "AUD", true);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/metals/spot/?metal=gold&currency=AUD&refresh=true",
      expect.any(Object)
    );
  });
});
