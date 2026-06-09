import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { getDashboardSummary } from "../../api/dashboard";
import { EmptyState } from "../../components/EmptyState";
import { statusLabels } from "../../components/StatusBadge";

export function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: getDashboardSummary
  });

  if (isLoading) {
    return <PageFrame title="Dashboard"><EmptyState title="Loading dashboard" /></PageFrame>;
  }

  if (error || !data) {
    return (
      <PageFrame title="Dashboard">
        <EmptyState title="Sign in through Django admin" detail="The inventory API needs your Django session." />
      </PageFrame>
    );
  }

  const totalValue = new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: data.currency,
    maximumFractionDigits: 0
  }).format(Number(data.total_estimated_value));

  const cards = [
    { label: "Inventory value", value: totalValue, to: "/inventory" },
    { label: "Items", value: data.total_items, to: "/inventory" },
    { label: "Needs research", value: data.by_status.needs_research ?? 0, to: "/inventory?status=needs_research" },
    { label: "Ready", value: data.by_status.ready_to_list ?? 0, to: "/inventory?status=ready_to_list" },
    { label: "Missing photos", value: data.missing_photos, to: "/inventory?has_photos=false" },
    { label: "High value open", value: data.high_value_unlisted, to: "/inventory" }
  ];

  return (
    <PageFrame title="Dashboard">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <Link key={card.label} to={card.to} className="metric-tile">
            <span className="text-sm text-slate-400">{card.label}</span>
            <span className="mt-2 text-2xl font-semibold text-slate-50">{card.value}</span>
          </Link>
        ))}
      </div>
      <section className="mt-8">
        <h2 className="section-title">Status</h2>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {Object.entries(data.by_status).map(([status, count]) => (
            <Link key={status} to={`/inventory?status=${status}`} className="row-link">
              <span>{statusLabels[status] ?? status}</span>
              <strong>{count}</strong>
            </Link>
          ))}
        </div>
      </section>
    </PageFrame>
  );
}

function PageFrame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
      <h1 className="page-title">{title}</h1>
      <div className="mt-5">{children}</div>
    </div>
  );
}
