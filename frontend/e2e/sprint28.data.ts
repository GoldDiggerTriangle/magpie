import type { AnalyticsAging, AnalyticsByCategory, AnalyticsEstimateVsActual, AnalyticsListingOpportunities, AnalyticsPnl, AnalyticsSummary, DashboardPreference, PaginatedResponse, ProductCategory, ProfitLedger } from "../src/types";

export const availableTiles = [
  { id: "realised_profit", label: "Realised profit", format: "currency", description: "Known-cost sales only." },
  { id: "net_proceeds", label: "Net proceeds", format: "currency", description: "Revenue less fees and shipping." },
  { id: "sell_through", label: "Sell-through", format: "percent", description: "Sold divided by sold plus available." },
  { id: "items_sold", label: "Items sold", format: "integer", description: "Quantity sold." },
  { id: "avg_realised_margin", label: "Avg margin", format: "percent", description: "Known-cost margin." },
  { id: "gross_revenue", label: "Revenue", format: "currency", description: "Gross revenue." }
] satisfies DashboardPreference["available_tiles"];

export const preference: DashboardPreference = {
  kpi_tiles: ["realised_profit", "net_proceeds", "sell_through", "items_sold", "avg_realised_margin"],
  schema_version: 1,
  available_tiles: availableTiles,
  updated_at: null
};

export const categories: PaginatedResponse<ProductCategory> = {
  count: 1,
  next: null,
  previous: null,
  results: [{
    id: "cat-1",
    name: "Stamps",
    slug: "stamps",
    parent: null,
    sku_prefix: "STM",
    profile_key: "",
    description: ""
  }]
};

export const summary: AnalyticsSummary = {
  currency: "AUD",
  filters: { range: "12m", start: null, end: null, category: [], channel: "all", unknown: "honest" },
  tiles: {
    realised_profit: tile("realised_profit", "Realised profit", "currency", "50.00", "+1 unknown-cost sale excluded."),
    gross_revenue: tile("gross_revenue", "Revenue", "currency", "130.00"),
    net_proceeds: tile("net_proceeds", "Net proceeds", "currency", "115.00"),
    items_sold: tile("items_sold", "Items sold", "integer", "3"),
    sell_through: tile("sell_through", "Sell-through", "percent", "18.18"),
    avg_realised_margin: tile("avg_realised_margin", "Avg margin", "percent", "62.50"),
    avg_time_to_sale: tile("avg_time_to_sale", "Avg time to sale", "days", "12"),
    inventory_cost_basis: tile("inventory_cost_basis", "Inventory cost", "currency", "180.00"),
    estimated_inventory_value: tile("estimated_inventory_value", "Est. inventory value", "currency", "394.00"),
    aged_inventory_count: tile("aged_inventory_count", "Aged stock", "integer", "1"),
    unresolved_ebay_staging_count: tile("unresolved_ebay_staging_count", "eBay to triage", "integer", "4"),
    cost_basis_unknown_sales_count: tile("cost_basis_unknown_sales_count", "Unknown-cost sales", "integer", "1")
  },
  action_counts: {
    unresolved_ebay_staging: 4,
    cost_basis_unknown_sales: 1,
    listing_opportunities: 1
  },
  sample: { sales: 2, known_profit_sales: 1, linked_sales: 1 }
};

export const pnl: AnalyticsPnl = {
  currency: "AUD",
  small_sample: true,
  empty: false,
  series: [{
    month: "2026-06-01",
    realised_profit: "50.00",
    net_proceeds: "115.00",
    gross_revenue: "130.00",
    quantity: 3,
    unknown_cost_sales: 1
  }]
};

export const byCategory: AnalyticsByCategory = {
  currency: "AUD",
  empty: false,
  small_sample: true,
  categories: [{
    category_id: "cat-1",
    category: "Stamps",
    gross_revenue: "80.00",
    realised_profit: "50.00",
    margin: "62.50",
    sell_through: "18.18",
    items_sold: 2,
    available_units: 9,
    unknown_cost_sales: 0
  }]
};

export const estimate: AnalyticsEstimateVsActual = {
  currency: "AUD",
  accuracy: {
    sample_size: 1,
    within_20_pct: "100.00",
    median_abs_pct_error: "6.67",
    small_sample: true,
    empty: false
  },
  fees: {
    sample_size: 1,
    estimated_fees_total: "8.00",
    actual_fees_total: "8.00",
    delta: "0.00"
  },
  points: [{
    sale_id: "sale-1",
    item_id: "item-1",
    sku: "STM-00001",
    title: "Stamp lot",
    sale_date: "2026-06-14",
    estimated: "75.00",
    actual: "80.00",
    delta_pct: "6.67"
  }]
};

export const aging: AnalyticsAging = {
  currency: "AUD",
  empty: false,
  buckets: [
    { id: "0_30", label: "0-30 days", count: 0, quantity_remaining: 0, cost_basis: "0.00", estimated_value: "0.00" },
    { id: "31_90", label: "31-90 days", count: 1, quantity_remaining: 8, cost_basis: "80.00", estimated_value: "64.00" },
    { id: "91_180", label: "91-180 days", count: 1, quantity_remaining: 1, cost_basis: "100.00", estimated_value: "330.00" },
    { id: "180_plus", label: "180+ days", count: 0, quantity_remaining: 0, cost_basis: "0.00", estimated_value: "0.00" }
  ]
};

export const opportunities: AnalyticsListingOpportunities = {
  currency: "AUD",
  empty: false,
  items: [{
    item_id: "item-2",
    sku: "STM-00002",
    title: "Gold ring",
    category: "Stamps",
    quantity_remaining: 1,
    estimated_value: "330.00",
    cost_basis: "100.00",
    estimated_margin: "230.00",
    status: "ready_to_list"
  }]
};

export function tile(id: AnalyticsSummary["tiles"][keyof AnalyticsSummary["tiles"]]["id"], label: string, format: AnalyticsSummary["tiles"][keyof AnalyticsSummary["tiles"]]["format"], value: string, secondary = "") {
  return {
    id,
    label,
    format,
    value,
    secondary,
    excluded_count: secondary ? 1 : 0,
    description: label
  };
}

export const sampleLedger: ProfitLedger = {
  currency: "AUD",
  not_tax_advice_label: "Sale records for your accountant - not tax advice.",
  formula_tooltips: {
    profit: "realised profit = seller-receives revenue - fees - all-in direct costs.",
    profit_per_day: "profit/day = realised profit / days held.",
    ranking: "n >= 3; loss groups are not recommendations."
  },
  settings: {
    stale_days: 90,
    ranking_threshold: 3
  },
  summary: {
    sale_count: 4,
    known_profit_sale_count: 3,
    unknown_cost_sale_count: 1,
    revenue: "260.00",
    fees: "18.40",
    total_costs: "210.00",
    realised_profit: "31.60",
    loss_sale_count: 1
  },
  ledger: [
    {
      sale_id: "sale-1",
      item_id: "item-1",
      item_sku: "STM-00001",
      title: "Profitable sale",
      category: "Stamps",
      category_id: "cat-1",
      channel: "manual",
      provenance: "manual",
      lot_id: "lot-1",
      lot_label: "Estate stamp lot",
      source_id: "source-1",
      source_name: "Estate sale",
      source_type: "estate",
      seller_mode: "free_selling",
      seller_mode_basis: "sale_channel_data",
      quantity: 1,
      sold_date: "2026-06-30",
      acquired_date: "2026-06-01",
      acquisition_date_basis: "recorded_acquisition",
      listed_date: "2026-06-05",
      listed_date_basis: "published_at",
      revenue: "100.00",
      price_basis: "seller_receives",
      fees: "5.00",
      fee_provenance: "actual_recorded",
      fee_breakdown: { recorded: "5.00" },
      cost_components: {
        acquisition: "50.00",
        refurb: "10.00",
        inbound_shipping: "5.00",
        packaging: "2.00",
        postage_label: "4.00",
        other_direct: "0.00"
      },
      cost_state: "known",
      cost_warning: "",
      total_costs: "71.00",
      realised_profit: "24.00",
      is_loss: false,
      all_in_roi: "33.80",
      days_held: 29,
      days_held_basis: "recorded_acquisition",
      profit_per_day: "0.83",
      annualised_all_in_roi: "425.24",
      velocity_state: "known",
      detail_url: "/inventory/item-1"
    },
    {
      sale_id: "sale-2",
      item_id: "item-2",
      item_sku: "STM-00002",
      title: "Schedule fee sale",
      category: "Stamps",
      category_id: "cat-1",
      channel: "ebay_au",
      provenance: "ebay_sync",
      lot_id: null,
      lot_label: "",
      source_id: "source-2",
      source_name: "Online buy",
      source_type: "online",
      seller_mode: "pro_starter",
      seller_mode_basis: "sale_channel_data",
      quantity: 1,
      sold_date: "2026-07-01",
      acquired_date: "2026-06-01",
      acquisition_date_basis: "recorded_acquisition",
      listed_date: null,
      listed_date_basis: "no_listing_record",
      revenue: "100.00",
      price_basis: "seller_receives",
      fees: "13.40",
      fee_provenance: "schedule_derived",
      fee_breakdown: { seller_final_value_fee: "13.40" },
      cost_components: {
        acquisition: "50.00",
        refurb: "0.00",
        inbound_shipping: "0.00",
        packaging: "0.00",
        postage_label: "0.00",
        other_direct: "0.00"
      },
      cost_state: "known",
      cost_warning: "",
      total_costs: "50.00",
      realised_profit: "36.60",
      is_loss: false,
      all_in_roi: "73.20",
      days_held: 30,
      days_held_basis: "recorded_acquisition",
      profit_per_day: "1.22",
      annualised_all_in_roi: "890.60",
      velocity_state: "known",
      detail_url: "/inventory/item-2"
    },
    {
      sale_id: "sale-3",
      item_id: "item-3",
      item_sku: "STM-00003",
      title: "Loss-making test sale",
      category: "Coins",
      category_id: "cat-2",
      channel: "manual",
      provenance: "manual",
      lot_id: null,
      lot_label: "",
      source_id: "source-3",
      source_name: "Market stall",
      source_type: "market",
      seller_mode: "free_selling",
      seller_mode_basis: "sale_channel_data",
      quantity: 1,
      sold_date: "2026-06-15",
      acquired_date: "2026-06-20",
      acquisition_date_basis: "recorded_acquisition",
      listed_date: null,
      listed_date_basis: "no_listing_record",
      revenue: "50.00",
      price_basis: "seller_receives",
      fees: "0.00",
      fee_provenance: "actual_recorded",
      fee_breakdown: { total: "0.00" },
      cost_components: {
        acquisition: "100.00",
        refurb: "0.00",
        inbound_shipping: "0.00",
        packaging: "0.00",
        postage_label: "0.00",
        other_direct: "0.00"
      },
      cost_state: "known",
      cost_warning: "",
      total_costs: "100.00",
      realised_profit: "-50.00",
      is_loss: true,
      all_in_roi: "-50.00",
      days_held: 1,
      days_held_basis: "recorded_acquisition_guarded_min_1",
      profit_per_day: "-50.00",
      annualised_all_in_roi: "-18250.00",
      velocity_state: "known",
      detail_url: "/inventory/item-3"
    },
    {
      sale_id: "sale-4",
      item_id: "item-4",
      item_sku: "STM-00004",
      title: "Unknown-cost sale",
      category: "Stamps",
      category_id: "cat-1",
      channel: "manual",
      provenance: "manual",
      lot_id: null,
      lot_label: "",
      source_id: null,
      source_name: "Unknown source",
      source_type: "",
      seller_mode: "free_selling",
      seller_mode_basis: "sale_channel_data",
      quantity: 1,
      sold_date: "2026-06-18",
      acquired_date: null,
      acquisition_date_basis: "unknown_acquisition_date",
      listed_date: null,
      listed_date_basis: "no_listing_record",
      revenue: "10.00",
      price_basis: "seller_receives",
      fees: "0.00",
      fee_provenance: "actual_recorded",
      fee_breakdown: { total: "0.00" },
      cost_components: {
        acquisition: "0.00",
        refurb: "0.00",
        inbound_shipping: "0.00",
        packaging: "0.00",
        postage_label: "0.00",
        other_direct: "0.00"
      },
      cost_state: "unknown",
      cost_warning: "Acquisition/material cost basis is missing; profit is not computed.",
      total_costs: null,
      realised_profit: null,
      is_loss: false,
      all_in_roi: null,
      days_held: null,
      days_held_basis: "unknown_acquisition_date",
      profit_per_day: null,
      annualised_all_in_roi: null,
      velocity_state: "unknown_date",
      detail_url: "/inventory/item-4"
    }
  ],
  aggregates: {
    by_category: [],
    by_channel: [],
    by_source: [
      {
        label: "Estate sale",
        sale_count: 1,
        known_profit_sale_count: 1,
        unknown_cost_sale_count: 0,
        revenue: "100.00",
        fees: "5.00",
        total_costs: "71.00",
        realised_profit: "24.00",
        loss_sale_count: 0
      }
    ]
  },
  velocity: {
    median_profit_per_day: "0.83",
    sample_size: 3,
    unknown_date_count: 1,
    unknown_cost_count: 0,
    thin: false,
    tooltip: "profit/day = realised profit / days held."
  },
  cash_lock: {
    stale_days: 90,
    total_known_cash_locked: "100.00",
    unknown_cost_item_count: 1,
    warning: "Cash-lock totals exclude unknown-cost items, so cash locked may be understated.",
    buckets: [
      {
        id: "unlisted",
        label: "Unlisted",
        cash_locked: "40.00",
        item_count: 2,
        quantity_remaining: 2,
        unknown_cost_item_count: 1,
        items: [
          {
            item_id: "stock-1",
            sku: "STM-01000",
            title: "Unlisted stock",
            category: "Stamps",
            quantity_remaining: 1,
            cash_locked: "40.00",
            cost_state: "known",
            warnings: [],
            listed_date: null,
            listed_age_days: null,
            listed_date_basis: "no_listed_at_or_publish_record",
            nudge: "",
            hint: "No listed date or publish record; treated as unlisted. Set a listed date if this is listed elsewhere.",
            detail_url: "/inventory/stock-1"
          }
        ]
      },
      {
        id: "listed_fresh",
        label: "Listed fresh",
        cash_locked: "0.00",
        item_count: 0,
        quantity_remaining: 0,
        unknown_cost_item_count: 0,
        items: []
      },
      {
        id: "listed_stale",
        label: "Listed stale",
        cash_locked: "60.00",
        item_count: 1,
        quantity_remaining: 1,
        unknown_cost_item_count: 0,
        items: [
          {
            item_id: "stock-2",
            sku: "STM-01001",
            title: "Stale listed stock",
            category: "Stamps",
            quantity_remaining: 1,
            cash_locked: "60.00",
            cost_state: "known",
            warnings: [],
            listed_date: "2026-04-01",
            listed_age_days: 90,
            listed_date_basis: "published_at",
            nudge: "listed 90 days - reprice or relist?",
            hint: "",
            detail_url: "/inventory/stock-2"
          }
        ]
      }
    ]
  },
  buy_more: {
    threshold: 3,
    tooltip: "n >= 3; loss groups are not recommendations.",
    ranked: [],
    empty: false,
    groups: [
      {
        category: "Stamps",
        channel: "manual",
        source_name: "Estate sale",
        n: 2,
        median_profit: "24.00",
        median_profit_per_day: "0.83",
        median_days_held: 29,
        newest_sale_date: "2026-06-30",
        status: "insufficient_data",
        label: "insufficient data (n = 2)",
        recommended: false
      },
      {
        category: "Coins",
        channel: "manual",
        source_name: "Market stall",
        n: 3,
        median_profit: "-50.00",
        median_profit_per_day: "-50.00",
        median_days_held: 1,
        newest_sale_date: "2026-06-15",
        status: "loss_making",
        label: "loss-making - do not buy more",
        recommended: false
      }
    ]
  },
  financial_years: {
    options: [
      { id: "2025-2026", label: "FY2025-26", start_year: 2025, end_year: 2026, start: "2025-07-01", end: "2026-06-30" },
      { id: "2026-2027", label: "FY2026-27", start_year: 2026, end_year: 2027, start: "2026-07-01", end: "2027-06-30" }
    ],
    selected: { id: "2025-2026", label: "FY2025-26", start_year: 2025, end_year: 2026, start: "2025-07-01", end: "2026-06-30" },
    summary: {
      sale_count: 3,
      known_profit_sale_count: 2,
      unknown_cost_sale_count: 1,
      revenue: "160.00",
      fees: "5.00",
      total_costs: "171.00",
      realised_profit: "-26.00",
      loss_sale_count: 1
    }
  }
};
