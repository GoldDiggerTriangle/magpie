import { apiRequest } from "./client";
import type { FeeSchedule, PaginatedResponse } from "../types";

export function listFeeSchedules() {
  return apiRequest<PaginatedResponse<FeeSchedule>>("/api/fee-schedules/");
}

