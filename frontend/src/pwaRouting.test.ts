import { describe, expect, test, vi } from "vitest";

import {
  PWA_NAVIGATION_FALLBACK_DENYLIST,
  unregisterServiceWorkersForAdminRecovery
} from "./pwaRouting";

function denied(path: string) {
  return PWA_NAVIGATION_FALLBACK_DENYLIST.some((pattern) => pattern.test(path));
}

describe("PWA navigation fallback routing", () => {
  test("does not let the service worker swallow Django admin routes", () => {
    expect(denied("/admin/")).toBe(true);
    expect(denied("/admin/login/?next=%2F")).toBe(true);
    expect(denied("/admin")).toBe(true);
  });

  test("keeps backend and asset routes out of the SPA fallback", () => {
    expect(denied("/api/health/")).toBe(true);
    expect(denied("/media/example.jpg")).toBe(true);
    expect(denied("/static/admin/css/base.css")).toBe(true);
    expect(denied("/inventory/deep-link")).toBe(false);
  });

  test("admin recovery unregisters stale service workers before reloading Django admin", async () => {
    const unregister = vi.fn().mockResolvedValue(true);
    const serviceWorker = {
      getRegistrations: vi.fn().mockResolvedValue([{ unregister }, { unregister }])
    };

    await expect(unregisterServiceWorkersForAdminRecovery(serviceWorker)).resolves.toBe(2);
    expect(serviceWorker.getRegistrations).toHaveBeenCalledTimes(1);
    expect(unregister).toHaveBeenCalledTimes(2);
  });
});
