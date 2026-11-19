export function plainDate(value: string | null | undefined, withTime = false) {
  if (!value) return "Not recorded";
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? value + "T12:00:00" : value);
  if (!Number.isFinite(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en-AU", { day: "numeric", month: "short", year: "numeric",
    ...(withTime ? { hour: "numeric", minute: "2-digit", hour12: true } : {}) }).format(date);
}
export function draftStateLabel(status: string) {
  return ({ draft: "Draft", staged: "Staged", publishing: "Publishing", publish_unknown: "Check publish result",
    publish_failed: "Publish failed", published: "Published", archived: "Archived",
    ready: "Ready", exported: "Exported", reviewed: "Reviewed" } as Record<string, string>)[status] ?? status.replace(/_/g, " ");
}
export function sourceLabel(source?: string) {
  if (!source || source === "Saved draft; source not recorded") return "Source unknown";
  return source.replace(/Human edit in listing editor/g, "You entered this")
    .replace(/Human selection in listing editor/g, "You chose this")
    .replace(/Human asking price/g, "Your asking price")
    .replace(/Human-picked owned evidence/g, "Evidence you chose")
    .replace(/Allowlisted item fields/g, "Allowed item details")
    .replace(/eBay copy-pack template/g, "eBay listing text template")
    .replace(/Saved draft/g, "Saved with this draft");
}

export function listingFieldLabel(field: string) {
  return ({ category_id: "eBay category", condition_id: "condition", merchant_location_key: "listing location",
    payment_policy_id: "payment policy", fulfillment_policy_id: "postage policy", return_policy_id: "return policy",
    listing_duration: "duration", listing_format: "format", description_html: "description", est_shipping_note: "shipping note", photo_ids: "photos" } as Record<string, string>)[field] ?? field.replace(/_/g, " ");
}
