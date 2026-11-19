export const itemTabs = ["Details", "Photos", "Research", "Pricing", "eBay", "Sales"] as const;
export type ItemTab = typeof itemTabs[number];
export const tabAnchors: Record<ItemTab, string> = {
  Details: "core-details", Photos: "photos", Research: "ai-research",
  Pricing: "sales-valuations", eBay: "listings-channels", Sales: "item-sales"
};
export function tabForAnchor(anchor: string): ItemTab | undefined {
  const id = anchor.replace(/^#/, "");
  if (/^(listing-|quick-ebay-|listings-channels|ebay-quantity|take-down)/.test(id)) return "eBay";
  if (id === "photos" || id.startsWith("photo-")) return "Photos";
  if (id === "core-details" || id === "category-specifics") return "Details";
  if (id === "ai-research" || id === "ai-review" || id === "research-log") return "Research";
  if (id === "pricing-evidence" || id === "sales-valuations") return "Pricing";
  if (id === "item-sales") return "Sales";
}
export function rememberedItemTab(itemId: string): ItemTab {
  try {
    const value = localStorage.getItem(`magpie:item-tab:v1:${itemId}`);
    return itemTabs.includes(value as ItemTab) ? value as ItemTab : "Details";
  } catch { return "Details"; }
}
let focusRequest = 0;
export function focusItemField(id: string) {
  const request = ++focusRequest;
  window.dispatchEvent(new CustomEvent("magpie:reveal-item-field", { detail: { id } }));
  const locate = (attempt = 0) => {
    if (request !== focusRequest) return;
    const target = document.getElementById(id);
    if (!target) {
      if (attempt < 80) window.setTimeout(() => locate(attempt + 1), 25);
      return;
    }
    if (target.closest("[hidden]")) return;
    for (let parent = target?.parentElement; parent; parent = parent.parentElement) {
      if (parent instanceof HTMLDetailsElement) parent.open = true;
    }
    target?.scrollIntoView?.({ block: "start" });
    const field = target?.matches("input,select,textarea,button,a") ? target : target?.querySelector("input,select,textarea,button,a");
    ((field ?? target) as HTMLElement | null)?.focus({ preventScroll: true });
  };
  window.setTimeout(() => locate(), 0);
}
