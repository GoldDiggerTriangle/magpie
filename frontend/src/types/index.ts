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

export interface ListingSpecific {
  name: string;
  value: string;
}

export interface ListingCheck {
  key: string;
  level: "pass" | "warn" | "fail";
  message: string;
}

export interface ListingReadinessSummary {
  fail_count: number;
  warn_count: number;
  pass_count: number;
}

export interface ListingBoilerplate {
  id: UUID;
  channel: string;
  name: string;
  is_active: boolean;
  body_html: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface ListingDraft {
  id: UUID;
  item: UUID;
  status: "draft" | "ready" | "exported";
  channel: string;
  channel_data: Record<string, unknown>;
  title: string;
  subtitle: string;
  description_html: string;
  listing_format: "fixed" | "auction";
  price: string | null;
  currency: string;
  quantity: number;
  est_shipping_note: string;
  item_specifics: ListingSpecific[];
  photo_ids: UUID[];
  include_sku_footer: boolean;
  boilerplate: UUID | null;
  title_edited: boolean;
  description_edited: boolean;
  generated_meta: Record<string, unknown>;
  exported_at: string | null;
  readiness_summary: ListingReadinessSummary;
  created_at: string;
  updated_at: string;
}

export interface ListingDraftPayload {
  status?: ListingDraft["status"];
  channel?: string;
  channel_data?: Record<string, unknown>;
  title?: string;
  subtitle?: string;
  description_html?: string;
  listing_format?: ListingDraft["listing_format"];
  price?: string | null;
  currency?: string;
  quantity?: number;
  est_shipping_note?: string;
  item_specifics?: ListingSpecific[];
  photo_ids?: UUID[];
  include_sku_footer?: boolean;
  boilerplate?: UUID | null;
}

export interface EbayPolicyCounts {
  payment: number;
  fulfillment: number;
  return: number;
}

export interface EbaySnapshotStatus {
  opted_in: boolean | null;
  policy_counts: EbayPolicyCounts;
  fetched_at: string | null;
}

export interface EbayStatus {
  configured: boolean;
  environment: "" | "sandbox" | "production";
  connected: boolean;
  ebay_username: string;
  scopes: string[];
  access_token_expires_at: string | null;
  refresh_token_expires_at: string | null;
  last_refresh_error: string;
  snapshot: EbaySnapshotStatus;
}

export interface EbayConnectionSummary {
  environment: "sandbox" | "production";
  ebay_user_id: string;
  ebay_username: string;
  scopes: string[];
  access_token_expires_at: string | null;
  refresh_token_expires_at: string | null;
}

export interface AuditLogEntry {
  id: UUID;
  actor: string;
  action: string;
  target_type: string;
  target_id: string;
  payload: Record<string, unknown>;
  created_at: string;
}
