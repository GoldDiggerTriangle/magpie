import { apiRequest } from "./client";
import type { CategorySchema, PaginatedResponse, ProductCategory, UUID } from "../types";

export function listCategories() {
  return apiRequest<PaginatedResponse<ProductCategory>>("/api/categories/?ordering=name");
}

export function getCategorySchema(categoryId: UUID) {
  return apiRequest<CategorySchema>(`/api/categories/${categoryId}/schema/`);
}
