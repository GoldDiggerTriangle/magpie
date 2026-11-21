import { ArrowDown, ArrowUp, Check } from "lucide-react";
import { Link } from "react-router-dom";
import type { DashboardAvailableTile, DashboardKpiId, DashboardKpiTile } from "../../types";
export const DEFAULT_ROW: DashboardKpiId[] = ["realised_profit", "items_sold", "stock_on_hand", "ebay_listings"];
export const KPI_TILE_IDS: DashboardKpiId[] = ["realised_profit", "gross_revenue", "net_proceeds", "items_sold", "sell_through", "avg_realised_margin", "avg_time_to_sale", "inventory_cost_basis", "estimated_inventory_value", "aged_inventory_count", "unresolved_ebay_staging_count", "cost_basis_unknown_sales_count", "stock_on_hand", "ebay_listings"];
const currencyFormatter = new Intl.NumberFormat("en-AU", { style:"currency", currency:"AUD", minimumFractionDigits:2, maximumFractionDigits:2 });
const numberFormatter = new Intl.NumberFormat("en-AU");
function formatCurrency(value: string | number) { return currencyFormatter.format(Number(value)); }

export function KpiPicker({
  availableTiles,
  draftTiles,
  setDraftTiles,
  onSave,
  isSaving,
  error
}: {
  availableTiles: DashboardAvailableTile[];
  draftTiles: DashboardKpiId[];
  setDraftTiles: (tiles: DashboardKpiId[]) => void;
  onSave: () => void;
  isSaving: boolean;
  error: string;
}) {
  function toggle(tileId: DashboardKpiId) {
    if (draftTiles.includes(tileId)) {
      setDraftTiles(draftTiles.filter((id) => id !== tileId));
      return;
    }
    if (draftTiles.length < 5) {
      setDraftTiles([...draftTiles, tileId]);
    }
  }

  function move(tileId: DashboardKpiId, direction: -1 | 1) {
    const index = draftTiles.indexOf(tileId);
    const nextIndex = index + direction;
    if (index < 0 || nextIndex < 0 || nextIndex >= draftTiles.length) return;
    const next = [...draftTiles];
    [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
    setDraftTiles(next);
  }

  return (
    <div className="kpi-picker">
      <div className="kpi-picker-list">
        {availableTiles.map((tile) => {
          const checked = draftTiles.includes(tile.id);
          return (
            <div key={tile.id} className="kpi-picker-row">
              <label>
                <input type="checkbox" checked={checked} onChange={() => toggle(tile.id)} />
                <span>
                  <strong>{tile.label}</strong>
                  <small>{tile.description}</small>
                </span>
              </label>
              {checked ? (
                <span className="kpi-picker-order">
                  <button type="button" aria-label={`Move ${tile.label} up`} onClick={() => move(tile.id, -1)}>
                    <ArrowUp className="h-4 w-4" />
                  </button>
                  <button type="button" aria-label={`Move ${tile.label} down`} onClick={() => move(tile.id, 1)}>
                    <ArrowDown className="h-4 w-4" />
                  </button>
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
      <div className="kpi-picker-footer">
        <span>{draftTiles.length} selected. Choose 3-5.</span>
        {error ? <strong>{error}</strong> : null}
        <button type="button" className="ledger-button ledger-button-primary" disabled={draftTiles.length < 3 || draftTiles.length > 5 || isSaving} onClick={onSave}>
          <Check className="h-4 w-4" aria-hidden="true" />
          Save row
        </button>
      </div>
    </div>
  );
}

export function KpiTile({ tile, linked = true }: { tile: DashboardKpiTile; linked?: boolean }) {
  const monthly = !["stock_on_hand", "ebay_listings", "inventory_cost_basis", "estimated_inventory_value", "aged_inventory_count", "unresolved_ebay_staging_count"].includes(tile.id);
  const chartTarget = ["gross_revenue", "net_proceeds"].includes(tile.id) ? "revenue" : ["items_sold", "sell_through", "avg_time_to_sale", "avg_realised_margin"].includes(tile.id) ? "sell-through" : null;
  const to = tile.id === "ebay_listings" ? "/ebay#live-listings" : tile.id === "unresolved_ebay_staging_count" ? "/ebay/orders" : chartTarget ? `/profit?range=this_month&chart_range=this_month#${chartTarget}` : monthly ? "/profit?range=this_month#profit-summary" : "/inventory";
  if (!linked) return <article className="ledger-kpi-tile"><span>{tile.label}</span><strong>{formatTile(tile)}</strong><small>{tile.secondary || tile.description}</small></article>;
  return (
    <Link className="ledger-kpi-tile" to={to} title={tile.description}>
      <span>{tile.label}</span>
      <strong>{formatTile(tile)}</strong>
      <small>{tile.secondary || tile.description}</small>
    </Link>
  );
}

export function KpiSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="kpi-grid">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="ledger-skeleton ledger-kpi-tile" />
      ))}
    </div>
  );
}

export function sanitizeSelectedTiles(
  kpiTiles: DashboardKpiId[],
  availableTiles: DashboardAvailableTile[],
  summaryTiles?: Partial<Record<DashboardKpiId, DashboardKpiTile>>
) {
  const allowed = new Set(availableTiles.length ? availableTiles.map((tile) => tile.id) : KPI_TILE_IDS);
  const next = kpiTiles.filter((tileId, index) => {
    return kpiTiles.indexOf(tileId) === index && (allowed.size === 0 || allowed.has(tileId)) && (!summaryTiles || summaryTiles[tileId]);
  });
  return next.length >= 3 ? next.slice(0, 5) : DEFAULT_ROW;
}

export function formatTile(tile: DashboardKpiTile) {
  if (tile.state === "unknown" || tile.value === null) return "Profit unknown";
  if (tile.state === "no_sales") return "No sales this month";
  if (tile.format === "currency") return formatCurrency(tile.value);
  if (tile.format === "percent") return `${Number(tile.value).toFixed(1)}%`;
  if (tile.format === "days") return `${numberFormatter.format(Number(tile.value))}d`;
  return numberFormatter.format(Number(tile.value));
}
