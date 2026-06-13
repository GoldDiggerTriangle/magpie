import { ApiError, apiRequest } from "./client";

beforeEach(() => {
  Object.defineProperty(document, "cookie", {
    writable: true,
    value: "csrftoken=abc123"
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ ok: true }),
      text: async () => ""
    }))
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("apiRequest builds JSON requests with CSRF", async () => {
  await apiRequest("/api/items/", {
    method: "POST",
    body: { title: "Stamp" }
  });

  expect(fetch).toHaveBeenCalledWith(
    "/api/items/",
    expect.objectContaining({
      method: "POST",
      credentials: "include",
      headers: expect.objectContaining({
        "Content-Type": "application/json",
        "X-CSRFToken": "abc123"
      }),
      body: JSON.stringify({ title: "Stamp" })
    })
  );
});

test("apiRequest builds multipart requests without forcing content type", async () => {
  const form = new FormData();
  form.set("image", new Blob(["image"]), "image.jpg");

  await apiRequest("/api/items/1/photos/", {
    method: "POST",
    multipart: form
  });

  expect(fetch).toHaveBeenCalledWith(
    "/api/items/1/photos/",
    expect.objectContaining({
      method: "POST",
      credentials: "include",
      headers: expect.not.objectContaining({ "Content-Type": expect.any(String) }),
      body: form
    })
  );
});

test("ApiError does not dump raw HTML error pages", () => {
  const error = new ApiError(404, "<!DOCTYPE html><html><body>Django 404 route dump</body></html>");

  expect(error.message).toBe("API request failed with status 404. The server returned an HTML error page.");
  expect(error.message).not.toContain("<html>");
});

test("ApiError uses JSON detail when available", () => {
  const error = new ApiError(503, { detail: "eBay taxonomy endpoint unavailable." });

  expect(error.message).toBe("eBay taxonomy endpoint unavailable.");
});
