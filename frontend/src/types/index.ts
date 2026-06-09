export type UUID = string;

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ProductCategory {
  id: UUID;
  name: string;
  slug: string;
  parent: UUID | null;
  sku_prefix: string;
  profile_key: string;
  description: string;
}

export interface StorageLocation {
  id: UUID;
  label: string;
  type: string;
  parent: UUID | null;
  notes: string;
}

export interface AcquisitionRecord {
  id: UUID;
  source: string;
  acquired_on: string | null;
  total_cost: string | null;
  currency: string;
  travel_notes: string;
  notes: string;
}

export interface PhotoAsset {
  id: UUID;
  item: UUID;
  role: string;
  is_main: boolean;
  order_index: number;
  original_path: string;
  processed_path: string;
  thumb_path: string;
  original_url: string | null;
  processed_url: string | null;
  thumb_url: string | null;
  width: number | null;
  height: number | null;
  bytes_original: number | null;
  exif_stripped: boolean;
  quality_score: number | null;
}

export interface InventoryItemList {
  id: UUID;
  sku: string;
  title: string;
  status: string;
  condition: string;
  category: UUID | null;
  category_name: string | null;
  estimated_value: string | null;
  currency: string;
  main_thumb_url: string | null;
  created_at: string;
}

export interface InventoryItemDetail extends InventoryItemList {
  location: UUID | null;
  acquisition: UUID | null;
  acquisition_cost: string | null;
  min_price: string | null;
  target_price: string | null;
  notes: string;
  attributes: Record<string, unknown>;
  owner: number | null;
  photos: PhotoAsset[];
  updated_at: string;
}

export interface DashboardSummary {
  total_items: number;
  total_estimated_value: string;
  currency: string;
  by_status: Record<string, number>;
  missing_photos: number;
  high_value_unlisted: number;
}

export interface ItemFormPayload {
  title: string;
  category: UUID | null;
  condition: string;
  status?: string;
  location: UUID | null;
  acquisition_cost: string | null;
  estimated_value: string | null;
  notes: string;
  attributes?: Record<string, unknown>;
}
