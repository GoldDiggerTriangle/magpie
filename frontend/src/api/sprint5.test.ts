import { describe, expect, test, vi } from "vitest";

import {
  downloadListingZip,
  generateListingDraft,
  listItemListingDrafts
} from "./listing";


function mockFetch(data: unknown = {}) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(data), {
    status: 200,
    headers: { "content-type": "application/json" }
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}


describe("Sprint 5 listing API module", () => {
  test("listItemListingDrafts uses the item-scoped endpoint", async () => {
    const fetchMock = mockFetch({ count: 0, next: null, previous: null, results: [] });

    await listItemListingDrafts("item-1");

    expect(fetchMock).toHaveBeenCalledWith("/api/items/item-1/listing-drafts/", expect.any(Object));
  });

  test("generateListingDraft posts fields and confirm_overwrite", async () => {
    const fetchMock = mockFetch({ id: "draft-1" });

    await generateListingDraft("draft-1", ["title", "description"], true);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/listing-drafts/draft-1/generate/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ fields: ["title", "description"], confirm_overwrite: true })
      })
    );
  });

  test("downloadListingZip uses the export endpoint", async () => {
    const fetchMock = vi.fn(async () => new Response("zip", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const blob = await downloadListingZip("draft-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/listing-drafts/draft-1/export/",
      expect.objectContaining({ credentials: "include" })
    );
    expect(blob.size).toBe(3);
    expect(await blob.text()).toBe("zip");
  });
});
