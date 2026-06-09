import { apiRequest } from "./client";
import type { PaginatedResponse, ProductCategory } from "../types";

export function listCategories() {
  return apiRequest<PaginatedResponse<ProductCategory>>("/api/categories/?ordering=name");
}
