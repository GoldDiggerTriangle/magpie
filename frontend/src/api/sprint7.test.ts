import { describe, expect, test, vi } from "vitest";

import {
  createMerchantLocation,
  getEbayCategoryAspects,
  getEbayCategorySuggestions,
  getMerchantLocation
} from "./ebay";
import {
  getListingAspectCheck,
  getStagedOfferReview,
  publishListingDraft,
  stageListingDraft,
  withdrawListingDraft
} from "./listing";

function mockFetch(data: unknown = {}) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(data), {
    status: 200,
    headers: { "content-type": "application/json" }
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("Sprint 7 listing publish API module", () => {
  test("listing draft publish endpoints use the locked Sprint 7 paths", async () => {
    const fetchMock = mockFetch({ id: "draft-1" });

    await getListingAspectCheck("draft-1");
    await stageListingDraft("draft-1", { override_missing_aspects: true, override_reason: "manual check" });
    await getStagedOfferReview("draft-1");
    await publishListingDraft("draft-1", "SKU-1");
    await withdrawListingDraft("draft-1");

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/listing-drafts/draft-1/aspects-check/", expect.objectContaining({ method: "GET" }));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/listing-drafts/draft-1/stage/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ override_missing_aspects: true, override_reason: "manual check" })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/listing-drafts/draft-1/staged-review/", expect.objectContaining({ method: "GET" }));
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/listing-drafts/draft-1/publish/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ confirm_sku: "SKU-1" })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(5, "/api/listing-drafts/draft-1/withdraw/", expect.objectContaining({ method: "POST" }));
  });

  test("eBay publish-support endpoints use Magpie API paths only", async () => {
    const fetchMock = mockFetch({ configured: false });

    await getEbayCategorySuggestions("stamp");
    await getEbayCategoryAspects("260");
    await getMerchantLocation();
    await createMerchantLocation({
      merchant_location_key: "first-flight-location",
      name: "First Flight",
      country: "AU",
      postal_code: "2000"
    });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/ebay/category-suggestions/?q=stamp", expect.objectContaining({ method: "GET" }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/ebay/category-aspects/?category_id=260", expect.objectContaining({ method: "GET" }));
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/ebay/merchant-location/", expect.objectContaining({ method: "GET" }));
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/ebay/merchant-location/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          merchant_location_key: "first-flight-location",
          name: "First Flight",
          country: "AU",
          postal_code: "2000"
        })
      })
    );
  });
});
