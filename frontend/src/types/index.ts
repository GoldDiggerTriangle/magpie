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

export interface FieldSpec {
  name: string;
  label: string;
  type: "str" | "int" | "decimal" | "choice" | "object" | "list[object]";
  required: false;
  choices: string[];
  min: string | number | null;
  max: string | number | null;
  help_text: string;
  item_shape?: Record<string, FieldSpec>;
  default?: string;
  exclusive_min?: boolean;
}

export interface CategorySchema {
  profile_key: string;
  fields: FieldSpec[];
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

export interface CurrentValuationSummary {
  id: UUID;
  strategy: string;
  suggested_price: string | null;
  fast_sale_price: string | null;
  patient_price: string | null;
  min_acceptable_price: string | null;
  confidence_score: number | null;
  confidence_reason: string;
}

export interface InventoryItemDetail extends InventoryItemList {
  location: UUID | null;
  acquisition: UUID | null;
  acquisition_cost: string | null;
  refurb_cost: string | null;
  inbound_shipping_cost: string | null;
  est_outbound_shipping: string | null;
  est_packaging_cost: string | null;
  min_price: string | null;
  target_price: string | null;
  notes: string;
  attributes: Record<string, unknown>;
  owner: number | null;
  photos: PhotoAsset[];
  comps_count: number;
  current_valuation: CurrentValuationSummary | null;
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
  refurb_cost?: string | null;
  inbound_shipping_cost?: string | null;
  est_outbound_shipping?: string | null;
  est_packaging_cost?: string | null;
  estimated_value: string | null;
  notes: string;
  attributes?: Record<string, unknown>;
}

export type ComparableKind = "active" | "sold" | "dealer" | "catalogue" | "manual_estimate" | "auction_result";

export interface Comparable {
  id: UUID;
  item: UUID;
  kind: ComparableKind;
  source: string;
  title: string;
  price: string | null;
  shipping: string | null;
  currency: string;
  condition: string;
  url: string;
  observed_on: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export type ComparablePayload = Omit<Comparable, "id" | "created_at" | "updated_at">;

export interface ResearchLink {
  type?: "link" | "checklist";
  label: string;
  url: string | null;
  note?: string;
  source?: string;
}

export interface ResearchRecordLink {
  label: string;
  url: string;
}

export interface ResearchRecord {
  id: UUID;
  item: UUID;
  source: string;
  content: string;
  links: ResearchRecordLink[];
  created_at: string;
  updated_at: string;
}

export type ResearchRecordPayload = Omit<ResearchRecord, "id" | "created_at" | "updated_at">;

export interface FeeSchedule {
  id: UUID;
  name: string;
  effective_from: string;
  is_active: boolean;
  final_value_pct: string;
  per_order_fee: string;
  promoted_pct: string;
  gst_pct: string;
  default_packaging_cost: string;
  default_outbound_shipping: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface ValuationComparable {
  id?: UUID;
  comparable: UUID;
  comparable_summary?: Comparable;
  included: boolean;
  exclude_reason: string;
  created_at?: string;
  updated_at?: string;
}

export interface ProfitBreakdown {
  label?: string;
  sale_price: string;
  final_value_fee: string;
  per_order_fee: string;
  promoted_fee: string;
  gst_on_fees: string;
  outbound_shipping: string;
  packaging: string;
  true_cost: string;
  total_deductions: string;
  net_profit: string;
  margin_pct: string;
}

export interface ValuationReport {
  id: UUID;
  item: UUID;
  strategy: "comp_based" | "commodity_manual" | "commodity_live";
  is_current: boolean;
  estimate_low: string | null;
  estimate_median: string | null;
  estimate_high: string | null;
  suggested_price: string | null;
  fast_sale_price: string | null;
  patient_price: string | null;
  min_acceptable_price: string | null;
  currency: string;
  confidence_score: number | null;
  confidence_reason: string;
  is_overridden: boolean;
  override_reason: string;
  inputs: Record<string, unknown>;
  fee_schedule: UUID | null;
  notes: string;
  comp_links: ValuationComparable[];
  profit_projection: ProfitBreakdown[];
  created_at: string;
  updated_at: string;
}

export interface ValuationReportPayload {
  strategy: ValuationReport["strategy"];
  is_current?: boolean;
  estimate_low?: string | null;
  estimate_median?: string | null;
  estimate_high?: string | null;
  suggested_price?: string | null;
  fast_sale_price?: string | null;
  patient_price?: string | null;
  min_acceptable_price?: string | null;
  currency?: string;
  confidence_score?: number | null;
  confidence_reason?: string;
  is_overridden?: boolean;
  override_reason?: string;
  inputs?: Record<string, unknown>;
  fee_schedule?: UUID | null;
  notes?: string;
  comp_links?: ValuationComparable[];
}

export interface MetalSpotQuote {
  metal: string;
  currency: string;
  price_per_gram: string;
  provider_price: string;
  provider_units: string;
  source: string;
  as_of: string;
  fetched_at: string;
  cache_hit: boolean;
}
