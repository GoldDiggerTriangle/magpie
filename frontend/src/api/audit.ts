import { apiRequest } from "./client";
import type { AuditLogEntry, PaginatedResponse } from "../types";

export function listAuditLogs(filters: { actionPrefix?: string; targetType?: string } = {}) {
  const params = new URLSearchParams();
  if (filters.actionPrefix) {
    params.set("action_prefix", filters.actionPrefix);
  }
  if (filters.targetType) {
    params.set("target_type", filters.targetType);
  }
  const query = params.toString();
  return apiRequest<PaginatedResponse<AuditLogEntry>>(`/api/audit-log/${query ? `?${query}` : ""}`);
}
