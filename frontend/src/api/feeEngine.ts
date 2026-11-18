import { apiRequest } from "./client";

export interface TierRate { tier: string; fvf_pct: string; threshold: string; above_pct: string }
export interface PlanPeriod { plan: string; effective_from: string; effective_to: string | null; per_order_fee: string; international_pct: string; gst_treatment: string; source_note: string; rates: TierRate[]; mapping?: { categories: Record<string, { tier: string; roots: string[] }> } }
export interface FeeVersion { id: string; number: number; label: string; source_url: string; source_note: string; periods: PlanPeriod[] }
export interface FeeCalendar { current: FeeVersion | null; today: string; state: string; gst_note: string; legacy: Array<{ id: string; name: string; label: string }>; versions: FeeVersion[]; categories: { source: string; categories: Record<string, { tier: string; roots: string[] }> } }
export interface FeeOrder { sale_date: string; destination_country: string; order_id?: string; postage?: string; handling?: string; marketplace_tax?: string; other_fee_base?: string; seller_discount?: string; buyer_incentives?: string; promoted_fee?: string; extra_charges?: Array<{ label: string; amount: string; source: string }>; lines: Array<{ key: string; quantity: number; item_total: string; category_slug: string; ebay_category_id?: string; ebay_path?: string[] }> }
export interface FeeResult { state: string; label: string; fee_total: string | null; gst_added?: string; version_id?: string | null; category_conflicts?: string[]; lines: Record<string, { state: string; revenue: string; fee_base: string; fee_total: string | null; components: Record<string, string> }> }
export const getFeeCalendar = () => apiRequest<FeeCalendar>("/api/fee-engine/");
export const saveFeeCalendar = (body: Omit<FeeVersion, "id" | "number"> & { previous_id: string | null }) => apiRequest<FeeVersion>("/api/fee-engine/", { method: "POST", body });
export const calculateOrderFees = (body: FeeOrder) => apiRequest<FeeResult>("/api/fee-engine/calculate/", { method: "POST", body });
export const adjustSaleFee = (saleId: string, body: { amount: string; reason: string; provenance: string }) => apiRequest(`/api/fee-engine/sales/${saleId}/adjustments/`, { method: "POST", body });
