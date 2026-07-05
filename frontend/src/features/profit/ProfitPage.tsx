import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Banknote, FileDown, Gauge, LockKeyhole, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getProfitLedger, profitLedgerCsvUrl } from "../../api/profit";
import { AuthRequiredState } from "../../components/AuthRequiredState";
import { EmptyState } from "../../components/EmptyState";
import type { BuyMoreGroup, CashLockBucket, FinancialYearOption, ProfitLedger, ProfitLedgerRow, ProfitSummary } from "../../types";

const currencyFormatter = new Intl.NumberFormat("en-AU", {
  style: "currency",
  currency: "AUD",
  maximumFractionDigits: 2
});

const numberFormatter = new Intl.NumberFormat("en-AU");

export function ProfitPage() {
  const [staleDays, setStaleDays] = useState(90);
  const [fy, setFy] = useState("");
  const ledger = useQuery({
    queryKey: ["profit-ledger", staleDays, fy],
    queryFn: () => getProfitLedger({ stale_days: staleDays, fy: fy || undefined })
  });

  if (ledger.error) {
    return (
      <ProfitFrame>
        <AuthRequiredState detail="The profit ledger needs your Magpie session. Sign in, then return to Profit." />
      </ProfitFrame>
    );
  }

  const data = ledger.data;
  const selectedFy = data?.financial_years.selected.id ?? fy;

  return (
    <ProfitFrame>
      <header className="profit-hero">
        <div>
          <p className="ledger-kicker">Profit intelligence</p>
          <h1 className="ledger-title">Realised profit ledger</h1>
          <p className="ledger-subtitle">
            Owned sales only. Revenue is seller-receives, fees are labelled actual or schedule-derived, and thin data stays thin.
          </p>
        </div>
        <div className="profit-controls">
          <label>
            <span>Stale after</span>
            <input
              inputMode="numeric"
              min={1}
              type="number"
              value={staleDays}
              onChange={(event) => setStaleDays(Math.max(1, Number(event.target.value) || 90))}
            />
          </label>
          <label>
            <span>Financial year</span>
            <select value={selectedFy || ""} onChange={(event) => setFy(event.target.value)}>
              {(data?.financial_years.options ?? []).map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {ledger.isLoading || !data ? (
        <ProfitSkeleton />
      ) : (
        <>
          <SummaryTiles summary={data.summary} velocity={data.velocity} cashLocked={data.cash_lock.total_known_cash_locked} />
          <section className="profit-section">
            <div className="profit-section-header">
              <div>
                <p className="ledger-kicker">Ledger</p>
                <h2>Per-sale realised P&amp;L</h2>
              </div>
              <p title={data.formula_tooltips.profit}>seller-receives revenue - fees - all-in direct costs</p>
            </div>
            <LedgerTable rows={data.ledger} />
          </section>

          <section className="profit-section">
            <div className="profit-section-header">
              <div>
                <p className="ledger-kicker">Velocity</p>
                <h2>Profit per day held</h2>
              </div>
              <p title={data.velocity.tooltip}>Median profit/day is the headline; annualised ROI is context only.</p>
            </div>
            <VelocityPanel data={data} />
          </section>

          <section className="profit-section" id="cash-lock">
            <div className="profit-section-header">
              <div>
                <p className="ledger-kicker">Cash lock</p>
                <h2>Unsold stock cash lock</h2>
              </div>
              <p>Listed stale threshold: {data.cash_lock.stale_days} days.</p>
            </div>
            {data.cash_lock.warning ? <WarningLine>{data.cash_lock.warning}</WarningLine> : null}
            <CashLockView buckets={data.cash_lock.buckets} />
          </section>

          <section className="profit-section">
            <div className="profit-section-header">
              <div>
                <p className="ledger-kicker">Buying signal</p>
                <h2>Buy more of this</h2>
              </div>
              <p title={data.buy_more.tooltip}>Rule: n &gt;= {data.buy_more.threshold}; loss-making groups are not recommendations.</p>
            </div>
            <BuyMoreList groups={data.buy_more.groups} />
          </section>

          <section className="profit-section" id="fy-export">
            <div className="profit-section-header">
              <div>
                <p className="ledger-kicker">Financial year</p>
                <h2>Accountant export</h2>
              </div>
              <a className="ledger-button ledger-button-primary" href={profitLedgerCsvUrl({ stale_days: staleDays, fy: selectedFy })}>
                <FileDown className="h-4 w-4" aria-hidden="true" />
                Download CSV
              </a>
            </div>
            <p className="profit-warning-text">{data.not_tax_advice_label}</p>
            <FySummary option={data.financial_years.selected} summary={data.financial_years.summary} />
          </section>
        </>
      )}
    </ProfitFrame>
  );
}

function ProfitFrame({ children }: { children: ReactNode }) {
  return <div className="profit-page">{children}</div>;
}

function SummaryTiles({ summary, velocity, cashLocked }: { summary: ProfitSummary; velocity: ProfitLedger["velocity"]; cashLocked: string }) {
  return (
    <section className="profit-summary-grid" aria-label="Profit summary">
      <ProfitTile icon={<Banknote />} label="Realised profit" value={formatCurrency(summary.realised_profit)} note={`${summary.known_profit_sale_count} known-cost sales`} tone={Number(summary.realised_profit) < 0 ? "loss" : "profit"} />
      <ProfitTile icon={<TrendingUp />} label="Median profit/day" value={velocity.median_profit_per_day ? formatCurrency(velocity.median_profit_per_day) : "Thin"} note={`${velocity.sample_size} known-date rows`} />
      <ProfitTile icon={<LockKeyhole />} label="Cash locked" value={formatCurrency(cashLocked)} note="Known-cost unsold stock" />
      <ProfitTile icon={<Gauge />} label="Losses" value={String(summary.loss_sale_count)} note="Loss rows stay visible" tone={summary.loss_sale_count ? "loss" : "neutral"} />
    </section>
  );
}

function ProfitTile({ icon, label, value, note, tone = "neutral" }: { icon: ReactNode; label: string; value: string; note: string; tone?: "neutral" | "profit" | "loss" }) {
  return (
    <article className={`profit-tile profit-tile-${tone}`}>
      <div aria-hidden="true">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

function LedgerTable({ rows }: { rows: ProfitLedgerRow[] }) {
  if (rows.length === 0) {
    return <EmptyState title="No sold rows yet" detail="Record sales or resolve eBay orders and realised P&L lands here." />;
  }
  return (
    <div className="profit-ledger-list">
      {rows.map((row) => (
        <article className={`profit-ledger-row ${row.is_loss ? "profit-ledger-loss" : ""}`} key={row.sale_id}>
          <div>
            <Link to={row.detail_url}>{row.item_sku}</Link>
            <strong>{row.title || "Untitled"}</strong>
            <small>{row.category} · {channelLabel(row.channel)} · {row.sold_date}</small>
          </div>
          <dl>
            <Metric label="Revenue" value={formatCurrency(row.revenue)} />
            <Metric label={`Fees (${feeLabel(row.fee_provenance)})`} value={formatCurrency(row.fees)} />
            <Metric label="Costs" value={row.total_costs ? formatCurrency(row.total_costs) : "Unknown"} />
            <Metric label="Profit" value={row.realised_profit ? formatCurrency(row.realised_profit) : "Unknown"} />
            <Metric label="Days held" value={row.days_held ? `${row.days_held}d` : "Unknown"} />
            <Metric label="Profit/day" value={row.profit_per_day ? formatCurrency(row.profit_per_day) : "Thin"} />
          </dl>
          {row.cost_warning ? <WarningLine>{row.cost_warning}</WarningLine> : null}
          {row.days_held_basis === "unknown_acquisition_date" ? <WarningLine>Acquisition date missing; velocity not computed.</WarningLine> : null}
        </article>
      ))}
    </div>
  );
}

function VelocityPanel({ data }: { data: ProfitLedger }) {
  return (
    <div className="profit-velocity-grid">
      <div>
        <span>Median profit/day</span>
        <strong>{data.velocity.median_profit_per_day ? formatCurrency(data.velocity.median_profit_per_day) : "Thin"}</strong>
        <small>{data.velocity.sample_size} rows with known cost and recorded acquisition date.</small>
      </div>
      <div>
        <span>Unknown date rows</span>
        <strong>{numberFormatter.format(data.velocity.unknown_date_count)}</strong>
        <small>Not silently using created/today fallback.</small>
      </div>
      <div>
        <span>Unknown cost rows</span>
        <strong>{numberFormatter.format(data.velocity.unknown_cost_count)}</strong>
        <small>Excluded from profit velocity.</small>
      </div>
    </div>
  );
}

function CashLockView({ buckets }: { buckets: CashLockBucket[] }) {
  return (
    <div className="cash-lock-grid">
      {buckets.map((bucket) => (
        <article className="cash-lock-bucket" key={bucket.id}>
          <header>
            <span>{bucket.label}</span>
            <strong>{formatCurrency(bucket.cash_locked)}</strong>
            <small>{bucket.item_count} items · {bucket.quantity_remaining} qty · {bucket.unknown_cost_item_count} unknown cost</small>
          </header>
          <div className="cash-lock-items">
            {bucket.items.length === 0 ? <p>No rows in this bucket.</p> : null}
            {bucket.items.slice(0, 5).map((item) => (
              <Link className="cash-lock-item" key={item.item_id} to={item.detail_url}>
                <span>
                  <strong>{item.sku}</strong>
                  <small>{item.title || item.category}</small>
                </span>
                <span>{item.cash_locked ? formatCurrency(item.cash_locked) : "Cost needed"}</span>
                {item.nudge ? <em>{item.nudge}</em> : null}
                {item.hint ? <em>{item.hint}</em> : null}
              </Link>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function BuyMoreList({ groups }: { groups: BuyMoreGroup[] }) {
  if (groups.length === 0) {
    return <EmptyState title="Not enough realised sales yet" detail="This list unlocks after at least 3 known-cost, known-date sales in a category and channel." />;
  }
  return (
    <div className="buy-more-list">
      {groups.map((group) => (
        <article className={`buy-more-row buy-more-${group.status}`} key={`${group.category}-${group.channel}`}>
          <div>
            <strong>{group.category}</strong>
            <small>{channelLabel(group.channel)} · n = {group.n} · newest {group.newest_sale_date}</small>
          </div>
          <div>
            <span>{group.label}</span>
            <strong>{formatCurrency(group.median_profit_per_day)} / day</strong>
            <small>Median profit {formatCurrency(group.median_profit)} · median held {group.median_days_held ?? "-"}d</small>
          </div>
        </article>
      ))}
    </div>
  );
}

function FySummary({ option, summary }: { option: FinancialYearOption; summary: ProfitSummary }) {
  return (
    <dl className="fy-summary">
      <Metric label="FY" value={`${option.label} (${option.start} to ${option.end})`} />
      <Metric label="Sales" value={String(summary.sale_count)} />
      <Metric label="Revenue" value={formatCurrency(summary.revenue)} />
      <Metric label="Fees" value={formatCurrency(summary.fees)} />
      <Metric label="Total costs" value={formatCurrency(summary.total_costs)} />
      <Metric label="Realised profit" value={formatCurrency(summary.realised_profit)} />
    </dl>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function WarningLine({ children }: { children: ReactNode }) {
  return (
    <p className="profit-warning-line">
      <AlertTriangle className="h-4 w-4" aria-hidden="true" />
      {children}
    </p>
  );
}

function ProfitSkeleton() {
  return (
    <div className="profit-summary-grid">
      {Array.from({ length: 4 }).map((_, index) => (
        <div className="ledger-skeleton profit-tile" key={index} />
      ))}
    </div>
  );
}

function feeLabel(value: ProfitLedgerRow["fee_provenance"]) {
  return value === "actual_recorded" ? "actual recorded" : "schedule derived";
}

function channelLabel(value: string) {
  if (value === "ebay_au") return "eBay AU";
  if (value === "manual") return "Manual";
  return "Other";
}

function formatCurrency(value: string | number) {
  return currencyFormatter.format(Number(value || 0));
}
