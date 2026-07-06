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
  suggestions?: string[];
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

export type PhotoFixupStatus = "none" | "pending_review" | "approved" | "rejected";
export type PhotoDerivativeStatus = "pending_review" | "approved" | "rejected";
export type PhotoDerivativeSource = "local_fixup" | "local_tweak";

export interface PhotoDerivative {
  id: UUID;
  photo: UUID;
  status: PhotoDerivativeStatus;
  source: PhotoDerivativeSource;
  fixed_path: string;
  thumb_path: string;
  source_path: string;
  fixed_url: string | null;
  thumb_url: string | null;
  source_url: string | null;
  width: number | null;
  height: number | null;
  bytes_fixed: number | null;
  pipeline_version: string;
  operations: Array<Record<string, unknown>>;
  parameters: Record<string, unknown>;
  background_mode: string;
  condition_note: string;
  created_at: string;
  updated_at: string;
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
  fixup_status: PhotoFixupStatus;
  active_derivative: UUID | null;
  active_derivative_detail: PhotoDerivative | null;
  pending_derivative: PhotoDerivative | null;
  derivatives: PhotoDerivative[];
}

export interface InventoryItemList {
  id: UUID;
  sku: string;
  title: string;
  status: string;
  condition: string;
  category: UUID | null;
  category_name: string | null;
  lot: UUID | null;
  source: UUID | null;
  source_name: string | null;
  disposition: "for_sale" | "scrapped";
  scrapped_at: string | null;
  quantity_total: number;
  quantity_sold: number;
  quantity_remaining: number;
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
  effective_source: Pick<Source, "id" | "name" | "type"> | null;
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

export type DashboardKpiId =
  | "realised_profit"
  | "gross_revenue"
  | "net_proceeds"
  | "items_sold"
  | "sell_through"
  | "avg_realised_margin"
  | "avg_time_to_sale"
  | "inventory_cost_basis"
  | "estimated_inventory_value"
  | "aged_inventory_count"
  | "unresolved_ebay_staging_count"
  | "cost_basis_unknown_sales_count";

export type DashboardKpiFormat = "currency" | "integer" | "percent" | "days";

export interface DashboardAvailableTile {
  id: DashboardKpiId;
  label: string;
  format: DashboardKpiFormat;
  description: string;
}

export interface DashboardPreference {
  kpi_tiles: DashboardKpiId[];
  schema_version: number;
  available_tiles: DashboardAvailableTile[];
  updated_at: string | null;
}

export interface DashboardKpiTile {
  id: DashboardKpiId;
  label: string;
  format: DashboardKpiFormat;
  value: string;
  secondary: string;
  excluded_count: number;
  description: string;
}

export interface AnalyticsFilters {
  range: string;
  start: string | null;
  end: string | null;
  category: UUID[];
  channel: string;
  unknown: string;
}

export interface AnalyticsSummary {
  currency: string;
  filters: AnalyticsFilters;
  tiles: Record<DashboardKpiId, DashboardKpiTile>;
  action_counts: {
    unresolved_ebay_staging: number;
    cost_basis_unknown_sales: number;
    listing_opportunities: number;
    take_down_checklists?: number;
  };
  sample: {
    sales: number;
    known_profit_sales: number;
    linked_sales: number;
  };
}

export interface AnalyticsPnlPoint {
  month: string;
  realised_profit: string;
  net_proceeds: string;
  gross_revenue: string;
  quantity: number;
  unknown_cost_sales: number;
}

export interface AnalyticsPnl {
  currency: string;
  series: AnalyticsPnlPoint[];
  small_sample: boolean;
  empty: boolean;
}

export interface AnalyticsCategoryRow {
  category_id: UUID;
  category: string;
  gross_revenue: string;
  realised_profit: string;
  margin: string;
  sell_through: string;
  items_sold: number;
  available_units: number;
  unknown_cost_sales: number;
}

export interface AnalyticsByCategory {
  currency: string;
  categories: AnalyticsCategoryRow[];
  empty: boolean;
  small_sample: boolean;
}

export interface EstimateVsActualPoint {
  sale_id: UUID;
  item_id: UUID;
  sku: string;
  title: string;
  sale_date: string;
  estimated: string;
  actual: string;
  delta_pct: string;
}

export interface AnalyticsEstimateVsActual {
  currency: string;
  points: EstimateVsActualPoint[];
  accuracy: {
    sample_size: number;
    within_20_pct: string;
    median_abs_pct_error: string | null;
    small_sample: boolean;
    empty: boolean;
  };
  fees: {
    sample_size: number;
    estimated_fees_total: string;
    actual_fees_total: string;
    delta: string;
  };
}

export interface AgingBucket {
  id: string;
  label: string;
  count: number;
  quantity_remaining: number;
  cost_basis: string;
  estimated_value: string;
}

export interface AnalyticsAging {
  currency: string;
  buckets: AgingBucket[];
  empty: boolean;
}

export interface ListingOpportunity {
  item_id: UUID;
  sku: string;
  title: string;
  category: string;
  quantity_remaining: number;
  estimated_value: string;
  cost_basis: string;
  estimated_margin: string | null;
  status: string;
}

export interface AnalyticsListingOpportunities {
  currency: string;
  items: ListingOpportunity[];
  empty: boolean;
}

export type SuggestionSource = "ocr" | "duplicate" | "ai" | "later_ai";
export type SuggestionConfidenceBand = "high" | "medium" | "low" | "candidate";
export type SuggestionStatus = "pending" | "approved" | "edited" | "rejected";

export interface FieldSuggestion {
  id: UUID;
  item: UUID;
  item_sku: string;
  item_title: string;
  photo: UUID | null;
  photo_thumb_url: string | null;
  field: string;
  proposed_value: unknown;
  source: SuggestionSource;
  confidence_band: SuggestionConfidenceBand;
  evidence: string;
  status: SuggestionStatus;
  resolved_value: unknown;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SoldSearchLink {
  id: string;
  label: string;
  query: string;
  url: string;
}

export interface PricingSourceLink {
  id: string;
  label: string;
  source_tag: string;
  query: string;
  url: string;
  note: string;
  primary: boolean;
}

export interface PricingEvidenceRow {
  id: string;
  record_type: "sale" | "comparable";
  own_sale: boolean;
  match_scope: "exact" | "similar";
  match_reason: string;
  date: string | null;
  title: string;
  sku: string;
  source_tag: string;
  source_label: string;
  condition: string;
  grade: string;
  sale_format: string;
  price: string | null;
  price_basis: PriceBasis;
  canonical_price: string | null;
  basis_uncertain: boolean;
  basis_label: string;
  currency: string;
  quantity: number;
  url: string;
  notes: string;
}

export interface PricingGridCell {
  key: string;
  label: string;
  low: string | null;
  median: string | null;
  high: string | null;
  count: number;
  basis_uncertain_count: number;
  own_sale_count: number;
  thin: boolean;
}

export interface PricingEvidence {
  item: UUID;
  currency: string;
  source_links: PricingSourceLink[];
  headline: PricingEvidenceRow[];
  own_sales: PricingEvidenceRow[];
  comparables: PricingEvidenceRow[];
  grids: {
    condition_grade: PricingGridCell[];
    sale_format: PricingGridCell[];
    recency: PricingGridCell[];
    source: PricingGridCell[];
  };
  summary: {
    evidence_count: number;
    priced_count: number;
    precise_priced_count: number;
    basis_uncertain_count: number;
    own_sale_count: number;
    comparable_count: number;
    exact_count: number;
    similar_count: number;
    thin: boolean;
    empty: boolean;
  };
  empty_state: {
    title: string;
    detail: string;
  };
}

export interface OcrRunResult {
  available: boolean;
  detail: string;
  suggestions: FieldSuggestion[];
}

export interface AIStatus {
  configured: boolean;
  provider: string;
  model_id: string;
  monthly_budget_cap_usd: string;
  monthly_usage_usd: string;
  budget_remaining_usd: string;
  enabled: boolean;
  disabled_reason: string;
}

export interface AICredentialPayload {
  provider?: string;
  model_id?: string;
  monthly_budget_cap_usd?: string;
  api_key: string;
}

export interface AIResearchCall {
  id: UUID;
  item: UUID | null;
  phase: "identify" | "price_assist";
  status: "success" | "failed" | "blocked";
  provider: string;
  model_id: string;
  image_count: number;
  exif_stripped: boolean;
  suggestions_created: number;
  search_terms_created: number;
  reference_links_created: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: string;
  request_metadata: Record<string, unknown>;
  response_metadata: Record<string, unknown>;
  error: string;
  created_at: string;
  updated_at: string;
}

export interface AIResearchSearchTerm {
  id: UUID;
  item: UUID;
  phrase: string;
  source_basis: string;
  created_by_call: UUID | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AIReferenceLink {
  id: UUID;
  item: UUID;
  label: string;
  url: string;
  source_basis: string;
  created_by_call: UUID | null;
  created_at: string;
  updated_at: string;
}

export interface AIResearchRunResult {
  call: AIResearchCall;
  suggestions: FieldSuggestion[];
  search_terms: AIResearchSearchTerm[];
  reference_links: AIReferenceLink[];
}

export interface AIReferencesResult {
  search_terms: AIResearchSearchTerm[];
  reference_links: AIReferenceLink[];
}

export interface ItemFormPayload {
  title: string;
  category: UUID | null;
  condition: string;
  status?: string;
  quantity_total?: number;
  location: UUID | null;
  lot?: UUID | null;
  source?: UUID | null;
  disposition?: "for_sale" | "scrapped";
  scrapped_at?: string | null;
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
export type PriceBasis = "buyer_visible" | "seller_receives" | "unknown";
export type SellerMode = "free_selling" | "pro_starter" | "pro_other" | "legacy_manual";
export type RoiBasis = "all_in_cash" | "buy_price";

export interface Comparable {
  id: UUID;
  item: UUID | null;
  descriptor_category?: UUID | null;
  descriptor_terms?: string[];
  descriptor_attributes?: Record<string, unknown>;
  kind: ComparableKind;
  source: string;
  title: string;
  price: string | null;
  price_basis: PriceBasis;
  shipping: string | null;
  currency: string;
  condition: string;
  grade: string;
  sale_format: "unknown" | "auction" | "fixed_price" | "dealer" | "other";
  source_tag: string;
  match_scope: "exact" | "similar";
  match_reason: string;
  url: string;
  observed_on: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface ComparablePayload {
  item?: UUID | null;
  descriptor_category?: UUID | null;
  descriptor_terms?: string[];
  descriptor_attributes?: Record<string, unknown>;
  kind: ComparableKind;
  source: string;
  title: string;
  price: string | null;
  price_basis?: PriceBasis;
  shipping: string | null;
  currency: string;
  condition: string;
  grade?: string;
  sale_format?: Comparable["sale_format"];
  source_tag?: string;
  match_scope?: Comparable["match_scope"];
  match_reason?: string;
  url: string;
  observed_on: string | null;
  notes: string;
}

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
  seller_mode: SellerMode;
  price_basis: PriceBasis;
  buyer_protection_fee_enabled: boolean;
  international_delivery_pct: string;
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
  status: "draft" | "ready" | "exported" | "staged" | "published" | "publish_failed";
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

export type ChannelListingChannel = "ebay" | "facebook_marketplace" | "gumtree" | "in_person" | "other";

export interface ChannelListingTakeDownState {
  state: "take_down_required" | "sold_out_clear" | "partial_quantity" | "available";
  message: string;
  quantity_sold: number;
  quantity_remaining: number;
  quantity_total: number;
}

export interface ChannelListing {
  id: UUID;
  item: UUID;
  item_sku: string;
  item_title: string;
  channel: ChannelListingChannel;
  channel_label: string;
  listed_at: string;
  ended_at: string | null;
  active: boolean;
  days_listed: number;
  url: string;
  note: string;
  source_listing_draft: UUID | null;
  take_down_state: ChannelListingTakeDownState | null;
  created_at: string;
  updated_at: string;
}

export interface ChannelListingPayload {
  item: UUID;
  channel: ChannelListingChannel;
  listed_at?: string;
  ended_at?: string | null;
  url?: string;
  note?: string;
}

export interface ChannelListingItemState extends ChannelListingTakeDownState {
  item: UUID;
  sku: string;
  title: string;
  active_listings: ChannelListing[];
}

export interface ChannelListingBoardGroup {
  channel: ChannelListingChannel;
  channel_label: string;
  count: number;
  listings: ChannelListing[];
}

export interface ChannelListingBoard {
  groups: ChannelListingBoardGroup[];
  take_down_checklist: ChannelListingItemState[];
  partial_quantity: ChannelListingItemState[];
  empty: boolean;
}

export interface ChannelListingSeedResult {
  seeded: number;
  existing: number;
  skipped_ambiguous: number;
  skipped_missing_date: number;
}

export interface CopyPack {
  item: UUID;
  channel: "ebay" | "facebook_marketplace" | "gumtree" | "generic";
  channel_label: string;
  sections: {
    title: string;
    description: string;
    price_line: string;
    postage_pickup_line: string;
  };
  whole_ad: string;
  price_source: {
    basis: "human_picked_evidence" | "item_asking_or_listed_price" | "missing";
    label: string;
    hint: string;
  };
  rendered_at: string;
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
  requires_reconsent: boolean;
  missing_scopes: string[];
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

export interface EbayCategorySuggestion {
  category_id: string;
  category_tree_id: string;
  category_name: string;
  name: string;
  category_path?: string[];
  is_leaf: boolean | null;
  child_count?: number | null;
  validation_error?: string;
}

export interface EbayCategorySuggestionsResponse {
  supported: boolean;
  suggestions: EbayCategorySuggestion[];
  detail?: string;
}

export interface EbayCategoryAspect {
  name: string;
  required: boolean;
  type: string;
  values?: string[];
}

export interface EbayCategoryAspectsResponse {
  category_id: string;
  fetched_at: string;
  aspects: EbayCategoryAspect[];
}

export interface EbayAspectCheck {
  satisfied_required: string[];
  missing_required: string[];
  optional_known: string[];
  unmapped_specifics: string[];
  aspects: EbayCategoryAspect[];
  fetched_at: string | null;
}

export interface MerchantLocation {
  id: UUID;
  environment: "sandbox" | "production";
  merchant_location_key: string;
  name: string;
  country: string;
  postal_code: string;
  city: string;
  state: string;
  created_on_ebay: boolean;
  fetched_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MerchantLocationStatus {
  configured: boolean;
  location: MerchantLocation | null;
}

export interface MerchantLocationPayload {
  merchant_location_key: string;
  name: string;
  country: string;
  postal_code?: string;
  city?: string;
  state?: string;
}

export interface StagedOfferReview {
  offer_id: string;
  sku: string;
  title: string;
  category_id: string;
  category_name: string;
  condition: string;
  price: string;
  currency: string;
  quantity: number;
  format: string;
  payment_policy_id: string;
  fulfillment_policy_id: string;
  return_policy_id: string;
  merchant_location_key: string;
  photo_count: number;
  aspect_warnings: string[];
}

export interface SaleRecord {
  id: UUID;
  item: UUID | null;
  item_sku: string;
  item_title: string;
  sale_date: string;
  quantity: number;
  sale_price: string;
  channel: "ebay_au" | "manual" | "other";
  is_external: boolean;
  cost_basis_unknown: boolean;
  actual_fees_total: string;
  actual_fee_breakdown: Record<string, unknown>;
  fee_status: "authoritative" | "estimated_or_unmapped";
  actual_shipping_cost: string;
  net_proceeds: string;
  allocated_cost_basis: string | null;
  realised_profit: string | null;
  cost_basis_override: string | null;
  listing_draft: UUID | null;
  valuation_snapshot: Record<string, unknown>;
  estimated_fee_snapshot: Record<string, unknown>;
  provenance: "manual" | "ebay_sync";
  ebay_order_id: string | null;
  ebay_line_item_id: string | null;
  ebay_transaction_id: string | null;
  channel_data: Record<string, unknown>;
  corrected_from: UUID | null;
  is_superseded: boolean;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface ProfitSettings {
  seller_mode: SellerMode;
  pro_other_final_value_pct: string;
  manual_final_value_pct: string;
  manual_fixed_fee: string;
  default_flat_profit_target: string;
  default_roi_pct: string;
  default_roi_basis: RoiBasis;
  maybe_band_pct: string;
  schema_version: number;
  updated_at: string | null;
}

export interface BuyEvidenceOption {
  id: string;
  label: string;
  source: "own_sale_exact" | "own_sale_similar" | "approved_comp" | "what_if";
  confidence_label: string;
  match_scope: "exact" | "similar";
  match_reason: string;
  price: string | null;
  price_basis: PriceBasis;
  seller_receives: string | null;
  basis_uncertain: boolean;
  date: string | null;
}

export interface BuyCalculatorEvidence {
  settings: ProfitSettings;
  item: UUID | null;
  evidence: BuyEvidenceOption[];
  suggested: {
    price: string;
    price_basis: PriceBasis;
    source: BuyEvidenceOption["source"];
    confidence_label: string;
    sample_size: number;
  } | null;
  empty: boolean;
  price_basis_options: Array<{ id: PriceBasis; label: string }>;
}

export interface DescriptorEvidenceRow {
  id: string;
  record_type: "sale" | "comparable";
  source: BuyEvidenceOption["source"];
  source_label: string;
  label: string;
  rank: number;
  match_scope: "exact" | "similar";
  match_reason: string;
  price: string | null;
  price_basis: PriceBasis;
  seller_receives: string | null;
  basis_uncertain: boolean;
  basis_label: string;
  currency: string;
  date: string | null;
  url: string;
  item: UUID | null;
  item_sku: string;
  own_sale: boolean;
}

export interface DescriptorEvidenceLookup {
  lookup: {
    category: UUID | null;
    category_label: string;
    terms: string[];
    attributes: Record<string, unknown>;
    transient: boolean;
  };
  rows: DescriptorEvidenceRow[];
  stats: {
    basis: PriceBasis;
    low: string | null;
    median: string | null;
    high: string | null;
    count: number;
    unknown_basis_count: number;
    newest_date: string | null;
    newest_age_days: number | null;
  };
  strength: {
    label: "STRONG" | "THIN";
    known_basis_count: number;
    newest_age_days: number | null;
    tooltip: string;
  };
  empty: boolean;
  empty_state: {
    title: string;
    detail: string;
  };
}

export interface DescriptorCapturePayload {
  item?: UUID | null;
  category?: UUID | null;
  terms: string;
  attributes?: Record<string, unknown>;
  price: string;
  price_basis: PriceBasis;
  source: string;
  source_tag: string;
  title?: string;
  shipping?: string | null;
  currency?: string;
  condition?: string;
  grade?: string;
  sale_format?: Comparable["sale_format"];
  match_scope?: Comparable["match_scope"];
  match_reason?: string;
  url?: string;
  observed_on?: string | null;
  notes?: string;
}

export interface DescriptorCaptureResult {
  comparable: Comparable;
  lookup: DescriptorEvidenceLookup;
}

export interface BoughtItPayload {
  agreed_price: string;
  expected_sell_price?: string;
  price_basis?: PriceBasis;
  category?: UUID | null;
  terms?: string;
  attributes?: Record<string, unknown>;
  condition?: string;
  quantity_total?: number;
  postage?: string;
  packaging?: string;
  refurb?: string;
}

export interface BuyCalculationPayload {
  expected_sell_price: string;
  price_basis: PriceBasis;
  seller_mode?: SellerMode;
  target_type: "roi" | "flat";
  flat_profit_target: string;
  roi_pct: string;
  roi_basis: RoiBasis;
  postage: string;
  packaging: string;
  refurb: string;
  asking_price?: string;
  evidence_source: BuyEvidenceOption["source"];
  confidence_label: string;
  auction_mode?: boolean;
  lot_mode?: boolean;
}

export interface BuyCalculationResult {
  max_buy: string;
  headline: "Max Buy Price" | "Max Bid" | "Max Lot Buy";
  verdict: "BUY" | "MAYBE" | "PASS" | "NO ASKING PRICE";
  expected_profit_at_asking: string | null;
  roi_at_asking: string | null;
  net_proceeds_before_buy: string;
  seller_fees: string;
  non_buy_costs: string;
  evidence_source: BuyEvidenceOption["source"];
  confidence_label: string;
  roi_basis: RoiBasis;
}

export interface ProfitSummary {
  sale_count: number;
  known_profit_sale_count: number;
  unknown_cost_sale_count: number;
  revenue: string;
  fees: string;
  total_costs: string;
  realised_profit: string;
  loss_sale_count: number;
}

export interface ProfitLedgerRow {
  sale_id: UUID;
  item_id: UUID | null;
  item_sku: string;
  title: string;
  category: string;
  category_id: UUID | null;
  channel: SaleRecord["channel"] | "scrapped";
  provenance: SaleRecord["provenance"] | "scrapped";
  lot_id: UUID | null;
  lot_label: string | null;
  source_id: UUID | null;
  source_name: string;
  source_type: string;
  seller_mode: SellerMode | "not_applicable";
  seller_mode_basis: string;
  quantity: number;
  sold_date: string;
  acquired_date: string | null;
  acquisition_date_basis: string;
  listed_date: string | null;
  listed_date_basis: string;
  revenue: string;
  price_basis: PriceBasis;
  fees: string;
  fee_provenance: "actual_recorded" | "schedule_derived";
  fee_breakdown: Record<string, unknown>;
  cost_components: {
    acquisition: string;
    refurb: string;
    inbound_shipping: string;
    packaging: string;
    postage_label: string;
    other_direct: string;
  };
  cost_state: "known" | "unknown";
  cost_warning: string;
  total_costs: string | null;
  realised_profit: string | null;
  is_loss: boolean;
  all_in_roi: string | null;
  days_held: number | null;
  days_held_basis: string;
  profit_per_day: string | null;
  annualised_all_in_roi: string | null;
  velocity_state: "known" | "unknown_date" | "unknown_cost";
  detail_url: string;
}

export interface ProfitAggregateRow extends ProfitSummary {
  label: string;
}

export interface CashLockItem {
  item_id: UUID;
  sku: string;
  title: string;
  category: string;
  quantity_remaining: number;
  cash_locked: string | null;
  cost_state: "known" | "unknown_cost";
  warnings: string[];
  listed_date: string | null;
  listed_age_days: number | null;
  listed_date_basis: string;
  nudge: string;
  hint: string;
  detail_url: string;
}

export interface CashLockBucket {
  id: "unlisted" | "listed_fresh" | "listed_stale";
  label: string;
  cash_locked: string;
  item_count: number;
  quantity_remaining: number;
  unknown_cost_item_count: number;
  items: CashLockItem[];
}

export interface BuyMoreGroup {
  category: string;
  channel: SaleRecord["channel"] | "scrapped";
  source_name: string;
  n: number;
  median_profit: string;
  median_profit_per_day: string;
  median_days_held: number | null;
  newest_sale_date: string;
  status: "ranked" | "insufficient_data" | "loss_making";
  label: string;
  recommended: boolean;
}

export interface FinancialYearOption {
  id: string;
  label: string;
  start_year: number;
  end_year: number;
  start: string;
  end: string;
}

export interface ProfitLedger {
  currency: string;
  not_tax_advice_label: string;
  formula_tooltips: {
    profit: string;
    profit_per_day: string;
    ranking: string;
  };
  settings: {
    stale_days: number;
    ranking_threshold: number;
  };
  summary: ProfitSummary;
  ledger: ProfitLedgerRow[];
  aggregates: {
    by_category: ProfitAggregateRow[];
    by_channel: ProfitAggregateRow[];
    by_source: ProfitAggregateRow[];
  };
  velocity: {
    median_profit_per_day: string | null;
    sample_size: number;
    unknown_date_count: number;
    unknown_cost_count: number;
    thin: boolean;
    tooltip: string;
  };
  cash_lock: {
    stale_days: number;
    buckets: CashLockBucket[];
    total_known_cash_locked: string;
    unknown_cost_item_count: number;
    warning: string;
  };
  buy_more: {
    threshold: number;
    tooltip: string;
    groups: BuyMoreGroup[];
    ranked: BuyMoreGroup[];
    empty: boolean;
  };
  financial_years: {
    options: FinancialYearOption[];
    selected: FinancialYearOption;
    summary: ProfitSummary;
  };
}

export interface Source {
  id: UUID;
  name: string;
  type: "market" | "estate" | "auction" | "op_shop" | "online" | "private" | "other";
  created_at: string;
  updated_at: string;
}

export interface LotMember {
  id: UUID;
  sku: string;
  title: string;
  category: string;
  state: "unsold" | "sold" | "scrapped";
  locked: boolean;
  quantity_sold: number;
  acquisition_cost: string | null;
  estimated_value: string | null;
  scrapped_at: string | null;
  detail_url: string;
}

export interface LotSummary {
  id: UUID;
  label: string;
  purchase_date: string;
  total_cost: string;
  source: Pick<Source, "id" | "name" | "type"> | null;
  note: string;
  allocated: string;
  unallocated: string;
  is_partially_allocated: boolean;
  is_over_allocated: boolean;
  warning: string;
  tally_label: string;
  members: LotMember[];
  proportional_available: boolean;
  pnl: {
    total_cost: string;
    allocated: string;
    unallocated: string;
    realised_revenue: string;
    realised_profit: string;
    remaining_cost_basis: string;
    recovered_label: string;
    is_loss: boolean;
    is_part_allocated: boolean;
  };
  created_at?: string;
  updated_at?: string;
}

export interface SaleRecordPayload {
  item?: UUID;
  sale_date: string;
  quantity: number;
  sale_price: string;
  channel: SaleRecord["channel"];
  actual_fees_total?: string | null;
  actual_fee_breakdown?: Record<string, unknown>;
  actual_shipping_cost?: string | null;
  cost_basis_override?: string | null;
  listing_draft?: UUID | null;
  notes?: string;
}

export interface EbayOrderSyncResult {
  environment: "sandbox" | "production";
  start: string;
  end: string;
  counts: {
    created: number;
    staged: number;
    duplicate_flagged: number;
    skipped: number;
    fee_authoritative: number;
    fee_estimated_or_unmapped: number;
  };
}

export interface EbayOrderStaging {
  id: UUID;
  environment: "sandbox" | "production";
  ebay_order_id: string;
  ebay_line_item_id: string;
  sku: string;
  quantity: number;
  line_price: string;
  sale_date: string;
  actual_fee: string | null;
  fee_status: "authoritative" | "estimated_or_unmapped";
  buyer_region: string;
  status: "pending" | "resolved" | "dismissed";
  resolved_sale: UUID | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface EbayOrderDuplicateCandidate {
  id: UUID;
  environment: "sandbox" | "production";
  ebay_order_id: string;
  ebay_line_item_id: string;
  sku: string;
  item: UUID;
  item_sku: string;
  item_title: string;
  manual_sale_id: UUID;
  quantity: number;
  line_price: string;
  sale_date: string;
  status: "pending" | "linked" | "dismissed";
  notes: string;
  created_at: string;
  updated_at: string;
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
