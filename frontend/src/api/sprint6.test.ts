import { describe, expect, test, vi } from "vitest";

import { listAuditLogs } from "./audit";
import {
  completeEbayConnect,
  disconnectEbay,
  getEbayStatus,
  refreshEbayPolicies,
  startEbayConnect
} from "./ebay";


function mockFetch(data: unknown = {}) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(data), {
    status: 200,
    headers: { "content-type": "application/json" }
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}


describe("Sprint 6 eBay and audit API modules", () => {
  test("eBay endpoints use the locked Sprint 6 paths", async () => {
    const fetchMock = mockFetch({ connected: false });

    await getEbayStatus();
    await startEbayConnect();
    await completeEbayConnect({ pasted_url: "https://example.test?code=abc&state=xyz" });
    await refreshEbayPolicies();
    await disconnectEbay();

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/ebay/status/", expect.objectContaining({ method: "GET" }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/ebay/connect/start/", expect.objectContaining({ method: "POST" }));
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/ebay/connect/complete/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ pasted_url: "https://example.test?code=abc&state=xyz" })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(4, "/api/ebay/refresh-policies/", expect.objectContaining({ method: "POST" }));
    expect(fetchMock).toHaveBeenNthCalledWith(5, "/api/ebay/disconnect/", expect.objectContaining({ method: "POST" }));
  });

  test("audit endpoint sends action prefix and target type filters", async () => {
    const fetchMock = mockFetch({ count: 0, next: null, previous: null, results: [] });

    await listAuditLogs({ actionPrefix: "ebay.", targetType: "ebay_credential" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/audit-log/?action_prefix=ebay.&target_type=ebay_credential",
      expect.objectContaining({ method: "GET" })
    );
  });
});
