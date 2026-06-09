import { apiRequest } from "./client";
import type { PaginatedResponse, StorageLocation } from "../types";

export function listLocations() {
  return apiRequest<PaginatedResponse<StorageLocation>>("/api/locations/?ordering=label");
}
