import { apiRequest } from "./client";
import type {
  AnalyticsAging,
  AnalyticsByCategory,
  AnalyticsEstimateVsActual,
  AnalyticsListingOpportunities,
  AnalyticsPnl,
  AnalyticsSummary,
  DashboardKpiId,
  DashboardPreference,
  DashboardSummary
} from "../types";

export function getDashboardSummary() {
  return apiRequest<DashboardSummary>("/api/dashboard/summary/");
}

export interface AnalyticsQuery {
  range?: string;
  start?: string;
  end?: string;
  category?: string[];
  channel?: string;
  unknown?: string;
}

function analyticsQueryString(query: AnalyticsQuery = {}) {
  const params = new URLSearchParams();
  if (query.range) params.set("range", query.range);
  if (query.start) params.set("start", query.start);
  if (query.end) params.set("end", query.end);
  if (query.channel) params.set("channel", query.channel);
  if (query.unknown) params.set("unknown", query.unknown);
  for (const category of query.category ?? []) {
    params.append("category", category);
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function getDashboardPreferences() {
  return apiRequest<DashboardPreference>("/api/dashboard/preferences/");
}

export function updateDashboardPreferences(kpiTiles: DashboardKpiId[]) {
  return apiRequest<DashboardPreference>("/api/dashboard/preferences/", {
    method: "PUT",
    body: { kpi_tiles: kpiTiles }
  });
}

export function getAnalyticsSummary(query: AnalyticsQuery) {
  return apiRequest<AnalyticsSummary>(`/api/analytics/summary/${analyticsQueryString(query)}`);
}

export function getAnalyticsPnl(query: AnalyticsQuery) {
  return apiRequest<AnalyticsPnl>(`/api/analytics/pnl/${analyticsQueryString(query)}`);
}

export function getAnalyticsByCategory(query: AnalyticsQuery) {
  return apiRequest<AnalyticsByCategory>(`/api/analytics/by-category/${analyticsQueryString(query)}`);
}

export function getAnalyticsEstimateVsActual(query: AnalyticsQuery) {
  return apiRequest<AnalyticsEstimateVsActual>(`/api/analytics/estimate-vs-actual/${analyticsQueryString(query)}`);
}

export function getAnalyticsAging(query: AnalyticsQuery) {
  return apiRequest<AnalyticsAging>(`/api/analytics/aging/${analyticsQueryString(query)}`);
}

export function getAnalyticsListingOpportunities(query: AnalyticsQuery) {
  return apiRequest<AnalyticsListingOpportunities>(`/api/analytics/listing-opportunities/${analyticsQueryString(query)}`);
}
