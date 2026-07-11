import { useEffect, useMemo, useState } from "react";

import { unregisterServiceWorkersForAdminRecovery } from "../pwaRouting";

export function AdminRouteRecovery() {
  const target = useMemo(() => currentHref(), []);
  const [status, setStatus] = useState("Preparing Django admin login...");

  useEffect(() => {
    let cancelled = false;

    async function recover() {
      try {
        const count = await unregisterServiceWorkersForAdminRecovery(
          typeof navigator !== "undefined" ? navigator.serviceWorker : undefined
        );
        if (cancelled) return;
        setStatus(
          count > 0
            ? "Removed stale app cache. Opening Django admin..."
            : "Opening Django admin..."
        );
      } catch {
        if (cancelled) return;
        setStatus("Opening Django admin...");
      }

      if (!cancelled && typeof window !== "undefined") {
        window.location.replace(target);
      }
    }

    void recover();
    return () => {
      cancelled = true;
    };
  }, [target]);

  return (
    <main className="mx-auto max-w-xl p-6 safe-page-top">
      <section className="rounded border border-blue-700 bg-blue-50 p-6 text-slate-950">
        <p className="text-lg font-semibold">Opening Django admin</p>
        <p className="mt-2 text-sm leading-6 text-slate-800">{status}</p>
        <a className="btn-secondary mt-4 inline-flex" href={target}>
          Continue to admin login
        </a>
      </section>
    </main>
  );
}

function currentHref() {
  if (typeof window === "undefined") return "/admin/login/";
  return `${window.location.pathname || "/admin/login/"}${window.location.search || ""}`;
}
