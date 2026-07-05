import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Check, SlidersHorizontal } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { listCategories } from "../../api/categories";
import {
  getAnalyticsAging,
  getAnalyticsByCategory,
  getAnalyticsEstimateVsActual,
  getAnalyticsListingOpportunities,
  getAnalyticsPnl,
  getAnalyticsSummary,
  getDashboardPreferences,
  updateDashboardPreferences,
  type AnalyticsQuery
} from "../../api/dashboard";
import { AuthRequiredState } from "../../components/AuthRequiredState";
import { EmptyState } from "../../components/EmptyState";
import type {
  AgingBucket,
  AnalyticsByCategory,
  AnalyticsPnl,
  DashboardAvailableTile,
  DashboardKpiId,
  DashboardKpiTile,
  EstimateVsActualPoint,
  ListingOpportunity,
  ProductCategory
} from "../../types";

const DEFAULT_ROW: DashboardKpiId[] = [
  "realised_profit",
  "net_proceeds",
  "sell_through",
  "items_sold",
  "avg_realised_margin"
];

const currencyFormatter = new Intl.NumberFormat("en-AU", {
  style: "currency",
  currency: "AUD",
  maximumFractionDigits: 0
});

const compactCurrencyFormatter = new Intl.NumberFormat("en-AU", {
  style: "currency",
  currency: "AUD",
  notation: "compact",
  maximumFractionDigits: 1
});

const numberFormatter = new Intl.NumberFormat("en-AU");

export function Dashboard() {
  const queryClient = useQueryClient();
  const [range, setRange] = useState("12m");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [channel, setChannel] = useState("all");
  const [unknown, setUnknown] = useState("honest");
  const [categoryIds, setCategoryIds] = useState<string[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [draftTiles, setDraftTiles] = useState<DashboardKpiId[]>(DEFAULT_ROW);

  const categories = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const preferences = useQuery({
    queryKey: ["dashboard-preferences"],
    queryFn: getDashboardPreferences
  });

  const filters: AnalyticsQuery = useMemo(
    () => ({
      range,
      start: range === "custom" ? start : undefined,
      end: range === "custom" ? end : undefined,
      channel,
      unknown,
      category: categoryIds
    }),
    [categoryIds, channel, end, range, start, unknown]
  );

  const summary = useQuery({
    queryKey: ["analytics-summary", filters],
    queryFn: () => getAnalyticsSummary(filters)
  });
  const pnl = useQuery({
    queryKey: ["analytics-pnl", filters],
    queryFn: () => getAnalyticsPnl(filters)
  });
  const byCategory = useQuery({
    queryKey: ["analytics-by-category", filters],
    queryFn: () => getAnalyticsByCategory(filters)
  });
  const estimate = useQuery({
    queryKey: ["analytics-estimate-vs-actual", filters],
    queryFn: () => getAnalyticsEstimateVsActual(filters)
  });
  const aging = useQuery({
    queryKey: ["analytics-aging", filters],
    queryFn: () => getAnalyticsAging(filters)
  });
  const opportunities = useQuery({
    queryKey: ["analytics-listing-opportunities", filters],
    queryFn: () => getAnalyticsListingOpportunities(filters)
  });

  const selectedTiles = sanitizeSelectedTiles(
    preferences.data?.kpi_tiles ?? DEFAULT_ROW,
    preferences.data?.available_tiles ?? [],
    summary.data?.tiles
  );

  useEffect(() => {
    if (!pickerOpen) {
      setDraftTiles(selectedTiles);
    }
  }, [pickerOpen, selectedTiles.join("|")]);

  const preferenceMutation = useMutation({
    mutationFn: updateDashboardPreferences,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard-preferences"] });
      setPickerOpen(false);
    }
  });

  const hasAuthError = [summary, pnl, byCategory, estimate, aging, opportunities].some(
    (query) => query.error
  );

  if (hasAuthError) {
    return (
      <DashboardFrame>
        <AuthRequiredState detail="The analytics API needs a Magpie session. Open the admin login, sign in, then return to the dashboard." />
      </DashboardFrame>
    );
  }

  return (
    <DashboardFrame>
      <header className="dashboard-hero">
        <div>
          <p className="ledger-kicker">Command centre</p>
          <h1 className="ledger-title">Dealer's ledger</h1>
          <p className="ledger-subtitle">
            Live sales, valuation accuracy, aged stock, and listing priorities from the current Magpie database.
          </p>
        </div>
        <FilterBar
          range={range}
          setRange={setRange}
          start={start}
          setStart={setStart}
          end={end}
          setEnd={setEnd}
          channel={channel}
          setChannel={setChannel}
          unknown={unknown}
          setUnknown={setUnknown}
          categoryIds={categoryIds}
          setCategoryIds={setCategoryIds}
          categories={categories.data?.results ?? []}
        />
      </header>

      {(summary.data?.action_counts.take_down_checklists ?? 0) > 0 ? (
        <div className="mx-auto mt-5 w-full max-w-7xl">
          <div className="take-down-alert">
            <div>
              <div>
                <h2>{summary.data?.action_counts.take_down_checklists} sold-out listing checklist{summary.data?.action_counts.take_down_checklists === 1 ? "" : "s"} open</h2>
                <p>End the real marketplace listings yourself, then tick them off in Magpie.</p>
              </div>
            </div>
            <div className="mt-3">
              <Link className="btn-danger" to="/listings">Open listings board</Link>
            </div>
          </div>
        </div>
      ) : null}

      <section className="kpi-ledger-row" aria-label="Selected KPI tiles">
        <div className="kpi-row-header">
          <div>
            <p className="ledger-kicker">Personal row</p>
            <h2 className="ledger-section-title">KPI register</h2>
          </div>
          <button type="button" className="ledger-button" onClick={() => setPickerOpen((value) => !value)}>
            <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
            Customise
          </button>
        </div>
        {pickerOpen ? (
          <KpiPicker
            availableTiles={preferences.data?.available_tiles ?? []}
            draftTiles={draftTiles}
            setDraftTiles={setDraftTiles}
            onSave={() => preferenceMutation.mutate(draftTiles)}
            isSaving={preferenceMutation.isPending}
            error={preferenceMutation.error ? String(preferenceMutation.error.message) : ""}
          />
        ) : null}
        {summary.isLoading || preferences.isLoading ? (
          <KpiSkeleton />
        ) : (
          <div className="kpi-grid">
            {selectedTiles.map((tileId) => {
              const tile = summary.data?.tiles[tileId];
              return tile ? <KpiTile key={tileId} tile={tile} /> : null;
            })}
          </div>
        )}
      </section>

      <LedgerSection
        eyebrow="Profit path"
        title="Realised P&L over time"
        note="Profit excludes sales without known cost basis; net proceeds still includes known revenue and fees."
      >
        <PnlSection data={pnl.data} isLoading={pnl.isLoading} />
      </LedgerSection>

      <LedgerSection
        eyebrow="Signature"
        title="Estimate vs actual"
        note="Each point compares the sale-time valuation snapshot with the actual sale price."
        prominent
      >
        <EstimateSection data={estimate.data} isLoading={estimate.isLoading} />
      </LedgerSection>

      <div className="dashboard-two-column">
        <LedgerSection eyebrow="Cash movement" title="Revenue / net proceeds">
          <RevenueSection data={pnl.data} isLoading={pnl.isLoading} />
        </LedgerSection>
        <LedgerSection eyebrow="Category read" title="Margin by category">
          <MarginSection data={byCategory.data} isLoading={byCategory.isLoading} />
        </LedgerSection>
      </div>

      <LedgerSection eyebrow="Velocity" title="Sell-through & time-to-sale">
        <VelocitySection summary={summary.data} byCategory={byCategory.data} isLoading={summary.isLoading || byCategory.isLoading} />
      </LedgerSection>

      <LedgerSection eyebrow="Stock age" title="Aging inventory">
        <AgingSection data={aging.data} isLoading={aging.isLoading} />
      </LedgerSection>

      <LedgerSection eyebrow="Next listing work" title="What's worth listing next">
        <OpportunitiesSection data={opportunities.data?.items ?? []} isLoading={opportunities.isLoading} empty={opportunities.data?.empty ?? false} />
      </LedgerSection>
    </DashboardFrame>
  );
}

function DashboardFrame({ children }: { children: ReactNode }) {
  return <div className="dashboard-ledger-page">{children}</div>;
}

function FilterBar({
  range,
  setRange,
  start,
  setStart,
  end,
  setEnd,
  channel,
  setChannel,
  unknown,
  setUnknown,
  categoryIds,
  setCategoryIds,
  categories
}: {
  range: string;
  setRange: (value: string) => void;
  start: string;
  setStart: (value: string) => void;
  end: string;
  setEnd: (value: string) => void;
  channel: string;
  setChannel: (value: string) => void;
  unknown: string;
  setUnknown: (value: string) => void;
  categoryIds: string[];
  setCategoryIds: (value: string[]) => void;
  categories: ProductCategory[];
}) {
  return (
    <div className="ledger-filter-bar" aria-label="Dashboard filters">
      <label className="ledger-filter">
        <span>Range</span>
        <select value={range} onChange={(event) => setRange(event.target.value)}>
          <option value="this_month">This month</option>
          <option value="3m">Last 3 months</option>
          <option value="6m">Last 6 months</option>
          <option value="12m">Last 12 months</option>
          <option value="all">All</option>
          <option value="custom">Custom</option>
        </select>
      </label>
      {range === "custom" ? (
        <>
          <label className="ledger-filter">
            <span>Start</span>
            <input type="date" value={start} onChange={(event) => setStart(event.target.value)} />
          </label>
          <label className="ledger-filter">
            <span>End</span>
            <input type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
          </label>
        </>
      ) : null}
      <label className="ledger-filter">
        <span>Category</span>
        <select
          multiple
          value={categoryIds}
          onChange={(event) => {
            setCategoryIds(Array.from(event.target.selectedOptions).map((option) => option.value));
          }}
        >
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
      </label>
      <label className="ledger-filter">
        <span>Channel</span>
        <select value={channel} onChange={(event) => setChannel(event.target.value)}>
          <option value="all">All</option>
          <option value="ebay_au">eBay</option>
          <option value="manual">Manual</option>
          <option value="external">External</option>
          <option value="other">Other</option>
        </select>
      </label>
      <label className="ledger-filter">
        <span>Unknown cost</span>
        <select value={unknown} onChange={(event) => setUnknown(event.target.value)}>
          <option value="honest">Revenue only</option>
          <option value="hide">Hide</option>
          <option value="include">Inspect</option>
        </select>
      </label>
    </div>
  );
}

function KpiPicker({
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

function KpiTile({ tile }: { tile: DashboardKpiTile }) {
  return (
    <article className="ledger-kpi-tile">
      <span>{tile.label}</span>
      <strong>{formatTile(tile)}</strong>
      <small>{tile.secondary || tile.description}</small>
    </article>
  );
}

function LedgerSection({
  eyebrow,
  title,
  note,
  prominent = false,
  children
}: {
  eyebrow: string;
  title: string;
  note?: string;
  prominent?: boolean;
  children: ReactNode;
}) {
  return (
    <section className={prominent ? "ledger-section ledger-section-prominent" : "ledger-section"}>
      <div className="ledger-section-header">
        <div>
          <p className="ledger-kicker">{eyebrow}</p>
          <h2 className="ledger-section-title">{title}</h2>
        </div>
        {note ? <p>{note}</p> : null}
      </div>
      {children}
    </section>
  );
}

function PnlSection({ data, isLoading }: { data?: AnalyticsPnl; isLoading: boolean }) {
  if (isLoading) return <ChartSkeleton />;
  if (!data || data.empty) {
    return <ActionEmpty title="No sales yet." detail="Resolve eBay orders or log a sale and your profit lands here." to="/ebay/orders" action="Review eBay orders" />;
  }
  const chartData = data.series.map(chartMoneyPoint);
  return (
    <>
      {data.small_sample ? <SmallSample count={data.series.reduce((sum, row) => sum + row.quantity, 0)} /> : null}
      <div className="ledger-chart">
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={chartData} margin={{ top: 12, right: 18, bottom: 8, left: 0 }}>
            <defs>
              <linearGradient id="profitFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="5%" stopColor="#2E7D5B" stopOpacity={0.24} />
                <stop offset="95%" stopColor="#2E7D5B" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#E4E1D8" vertical={false} />
            <XAxis dataKey="monthLabel" tickLine={false} axisLine={false} />
            <YAxis tickFormatter={(value) => compactCurrencyFormatter.format(Number(value))} tickLine={false} axisLine={false} />
            <Tooltip formatter={(value) => currencyFormatter.format(Number(value))} />
            <Area type="monotone" dataKey="net_proceeds" stroke="#2C3340" fill="transparent" name="Net proceeds" />
            <Area type="monotone" dataKey="realised_profit" stroke="#2E7D5B" fill="url(#profitFill)" name="Realised profit" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

function EstimateSection({ data, isLoading }: { data?: import("../../types").AnalyticsEstimateVsActual; isLoading: boolean }) {
  if (isLoading) return <ChartSkeleton />;
  if (!data || data.accuracy.empty) {
    return <ActionEmpty title="No valuation pairs yet." detail="Record sales with valuation snapshots and this becomes your estimate-vs-actual ledger." to="/sales" action="Open Sales" />;
  }
  const chartData = data.points.map((point) => ({
    ...point,
    estimatedNumber: Number(point.estimated),
    actualNumber: Number(point.actual)
  }));
  const axisMax = Math.max(10, ...chartData.map((point) => Math.max(point.estimatedNumber, point.actualNumber))) * 1.12;
  return (
    <div className="estimate-layout">
      <div className="accuracy-strip">
        <div>
          <span>Within 20%</span>
          <strong>{Number(data.accuracy.within_20_pct).toFixed(0)}%</strong>
        </div>
        <div>
          <span>Median error</span>
          <strong>{data.accuracy.median_abs_pct_error ? `${Number(data.accuracy.median_abs_pct_error).toFixed(1)}%` : "-"}</strong>
        </div>
        <div>
          <span>Fee delta</span>
          <strong>{formatCurrency(data.fees.delta)}</strong>
        </div>
      </div>
      {data.accuracy.small_sample ? <SmallSample count={data.accuracy.sample_size} /> : null}
      <div className="ledger-chart estimate-chart">
        <ResponsiveContainer width="100%" height={340}>
          <ScatterChart margin={{ top: 18, right: 24, bottom: 18, left: 0 }}>
            <CartesianGrid stroke="#E4E1D8" />
            <XAxis dataKey="estimatedNumber" name="Estimated" type="number" domain={[0, axisMax]} tickFormatter={(value) => compactCurrencyFormatter.format(Number(value))} tickLine={false} axisLine={false} />
            <YAxis dataKey="actualNumber" name="Actual" type="number" domain={[0, axisMax]} tickFormatter={(value) => compactCurrencyFormatter.format(Number(value))} tickLine={false} axisLine={false} />
            <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(value) => currencyFormatter.format(Number(value))} />
            <ReferenceLine segment={[{ x: 0, y: 0 }, { x: axisMax, y: axisMax }]} stroke="#9A7B2E" strokeWidth={2} />
            <Scatter data={chartData} fill="#2C3340" name="Sales" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="estimate-table" aria-label="Estimate versus actual table">
        <table>
          <thead>
            <tr>
              <th>Item</th>
              <th>Estimated</th>
              <th>Actual</th>
              <th>Delta</th>
            </tr>
          </thead>
          <tbody>
            {data.points.map((point) => (
              <tr key={point.sale_id}>
                <td>{point.sku}</td>
                <td>{formatCurrency(point.estimated)}</td>
                <td>{formatCurrency(point.actual)}</td>
                <td>{Number(point.delta_pct).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RevenueSection({ data, isLoading }: { data?: AnalyticsPnl; isLoading: boolean }) {
  if (isLoading) return <ChartSkeleton compact />;
  if (!data || data.empty) {
    return <ActionEmpty title="No revenue yet." detail="Resolve staged eBay orders or record a sale to start the cash ledger." to="/sales" action="Record a sale" />;
  }
  return (
    <div className="ledger-chart ledger-chart-compact">
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data.series.map(chartMoneyPoint)}>
          <CartesianGrid stroke="#E4E1D8" vertical={false} />
          <XAxis dataKey="monthLabel" tickLine={false} axisLine={false} />
          <YAxis tickFormatter={(value) => compactCurrencyFormatter.format(Number(value))} tickLine={false} axisLine={false} />
          <Tooltip formatter={(value) => currencyFormatter.format(Number(value))} />
          <Bar dataKey="gross_revenue" fill="#9A7B2E" name="Revenue" radius={[4, 4, 0, 0]} />
          <Bar dataKey="net_proceeds" fill="#2C3340" name="Net proceeds" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function MarginSection({ data, isLoading }: { data?: AnalyticsByCategory; isLoading: boolean }) {
  if (isLoading) return <ChartSkeleton compact />;
  if (!data || data.empty) {
    return <ActionEmpty title="No category margin yet." detail="Known-cost sales will show which categories are carrying profit." to="/sales" action="Open Sales" />;
  }
  return (
    <div className="ledger-chart ledger-chart-compact">
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data.categories.map((row) => ({ ...row, marginNumber: Number(row.margin) }))}>
          <CartesianGrid stroke="#E4E1D8" vertical={false} />
          <XAxis dataKey="category" tickLine={false} axisLine={false} />
          <YAxis tickFormatter={(value) => `${Number(value).toFixed(0)}%`} tickLine={false} axisLine={false} />
          <Tooltip formatter={(value) => `${Number(value).toFixed(1)}%`} />
          <Bar dataKey="marginNumber" fill="#2E7D5B" name="Margin" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function VelocitySection({
  summary,
  byCategory,
  isLoading
}: {
  summary?: import("../../types").AnalyticsSummary;
  byCategory?: AnalyticsByCategory;
  isLoading: boolean;
}) {
  if (isLoading) return <KpiSkeleton count={3} />;
  const sellThrough = summary?.tiles.sell_through;
  const avgDays = summary?.tiles.avg_time_to_sale;
  const strongest = byCategory?.categories.slice().sort((a, b) => Number(b.sell_through) - Number(a.sell_through))[0];
  return (
    <div className="velocity-grid">
      <KpiTile tile={sellThrough ?? fallbackTile("sell_through", "Sell-through", "percent")} />
      <KpiTile tile={avgDays ?? fallbackTile("avg_time_to_sale", "Avg time to sale", "days")} />
      <article className="ledger-kpi-tile">
        <span>Best category velocity</span>
        <strong>{strongest ? `${Number(strongest.sell_through).toFixed(0)}%` : "-"}</strong>
        <small>{strongest ? strongest.category : "Sales by category will show here."}</small>
      </article>
    </div>
  );
}

function AgingSection({ data, isLoading }: { data?: import("../../types").AnalyticsAging; isLoading: boolean }) {
  if (isLoading) return <TableSkeleton />;
  if (!data || data.empty) {
    return <ActionEmpty title="No available inventory." detail="Add inventory or restore available stock and aging buckets will fill in." to="/add" action="Add inventory" />;
  }
  return (
    <div className="ledger-table-wrap">
      <table className="ledger-table">
        <thead>
          <tr>
            <th>Age bucket</th>
            <th>Items</th>
            <th>Qty remaining</th>
            <th>Cost basis</th>
            <th>Est. value</th>
          </tr>
        </thead>
        <tbody>
          {data.buckets.map((bucket: AgingBucket) => (
            <tr key={bucket.id}>
              <td>{bucket.label}</td>
              <td>{bucket.count}</td>
              <td>{bucket.quantity_remaining}</td>
              <td>{formatCurrency(bucket.cost_basis)}</td>
              <td>{formatCurrency(bucket.estimated_value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OpportunitiesSection({ data, isLoading, empty }: { data: ListingOpportunity[]; isLoading: boolean; empty: boolean }) {
  if (isLoading) return <TableSkeleton />;
  if (empty || data.length === 0) {
    return <ActionEmpty title="Nothing waiting to be listed." detail="Add inventory or run a valuation to see what is worth listing." to="/inventory" action="Review inventory" />;
  }
  return (
    <div className="ledger-table-wrap">
      <table className="ledger-table">
        <thead>
          <tr>
            <th>Item</th>
            <th>Category</th>
            <th>Qty</th>
            <th>Est. value</th>
            <th>Est. margin</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item) => (
            <tr key={item.item_id}>
              <td>
                <Link to={`/inventory/${item.item_id}`}>{item.sku}</Link>
                <small>{item.title || "Untitled"}</small>
              </td>
              <td>{item.category}</td>
              <td>{item.quantity_remaining}</td>
              <td>{formatCurrency(item.estimated_value)}</td>
              <td>{item.estimated_margin ? formatCurrency(item.estimated_margin) : "Cost needed"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ActionEmpty({ title, detail, to, action }: { title: string; detail: string; to: string; action: string }) {
  return (
    <div className="ledger-empty">
      <div>
        <strong>{title}</strong>
        <p>{detail}</p>
      </div>
      <Link to={to}>{action}</Link>
    </div>
  );
}

function SmallSample({ count }: { count: number }) {
  return <p className="small-sample">Small sample: {count} data point{count === 1 ? "" : "s"}. Read directionally, not as a trend.</p>;
}

function KpiSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="kpi-grid">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="ledger-skeleton ledger-kpi-tile" />
      ))}
    </div>
  );
}

function ChartSkeleton({ compact = false }: { compact?: boolean }) {
  return <div className={compact ? "ledger-skeleton ledger-chart-compact" : "ledger-skeleton ledger-chart"} />;
}

function TableSkeleton() {
  return <div className="ledger-skeleton ledger-table-skeleton" />;
}

function sanitizeSelectedTiles(
  kpiTiles: DashboardKpiId[],
  availableTiles: DashboardAvailableTile[],
  summaryTiles?: Partial<Record<DashboardKpiId, DashboardKpiTile>>
) {
  const allowed = new Set(availableTiles.map((tile) => tile.id));
  const next = kpiTiles.filter((tileId, index) => {
    return kpiTiles.indexOf(tileId) === index && (allowed.size === 0 || allowed.has(tileId)) && (!summaryTiles || summaryTiles[tileId]);
  });
  return next.length >= 3 ? next.slice(0, 5) : DEFAULT_ROW;
}

function formatTile(tile: DashboardKpiTile) {
  if (tile.format === "currency") return formatCurrency(tile.value);
  if (tile.format === "percent") return `${Number(tile.value).toFixed(1)}%`;
  if (tile.format === "days") return `${numberFormatter.format(Number(tile.value))}d`;
  return numberFormatter.format(Number(tile.value));
}

function formatCurrency(value: string | number) {
  return currencyFormatter.format(Number(value));
}

function chartMoneyPoint(row: import("../../types").AnalyticsPnlPoint) {
  return {
    ...row,
    monthLabel: monthLabel(row.month),
    realised_profit: Number(row.realised_profit),
    net_proceeds: Number(row.net_proceeds),
    gross_revenue: Number(row.gross_revenue)
  };
}

function monthLabel(value: string) {
  const date = new Date(`${value}T00:00:00`);
  return date.toLocaleDateString("en-AU", { month: "short", year: "2-digit" });
}

function fallbackTile(id: DashboardKpiId, label: string, format: DashboardKpiTile["format"]): DashboardKpiTile {
  return {
    id,
    label,
    format,
    value: "0",
    secondary: "",
    excluded_count: 0,
    description: "No data yet."
  };
}
