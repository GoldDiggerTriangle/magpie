import { apiRequest } from "./client";

export interface EbayDiagnostic {
  operation: string; time: string; http_status: number | null;
  issues: { kind: string; error_id: number | null; domain: string; category: string; field: string | null; severity: "error" | "warning"; message: string }[];
}
export interface EbayHealth {
  environment: string; marketplace: string; connected: boolean; account: string | null;
  access: { state: string; expires_at: string | null };
  refresh: { state: string; expires_at: string | null; expiring_soon: boolean };
  application_access: { state: string; expires_at: string | null };
  scopes: { required: string[]; requested: string[]; application_required: string[]; grant_status: string };
  snapshots: Record<string, string | null>;
  checks: Record<"seller" | "application", { started_at: string | null; completed_at: string | null; next_check_at: string | null }>;
  operations: { operation: string; api: string; principal: string; last_success: { time: string; http_status: number; count: number | null } | null; current_failure: EbayDiagnostic | null; warnings: EbayDiagnostic | null }[];
  alerts: EbayDiagnostic[]; legacy_refresh_failure_unverified: boolean; media_probe: string; as_of: string;
}
export const getEbayHealth = () => apiRequest<EbayHealth>("/api/ebay/connection-health/");
export const checkEbayConnection = () => apiRequest<{ throttled: boolean; health: EbayHealth }>("/api/ebay/check-connection/", { method: "POST", body: {} });
