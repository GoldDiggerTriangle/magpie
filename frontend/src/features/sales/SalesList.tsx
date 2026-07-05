import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listSales } from "../../api/sales";
import { AuthRequiredState } from "../../components/AuthRequiredState";
import { EmptyState } from "../../components/EmptyState";

export function SalesList() {
  const sales = useQuery({ queryKey: ["sales"], queryFn: listSales });

  return (
    <div className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
      <div>
        <h1 className="page-title">Sales</h1>
        <p className="mt-1 text-sm text-slate-500">{sales.data?.count ?? 0} records</p>
      </div>

      <div className="mt-6 hidden overflow-x-auto rounded border border-slate-800 bg-slate-900 sm:block">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="text-xs uppercase tracking-normal text-slate-500">
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Item</th>
              <th className="px-4 py-3">Qty</th>
              <th className="px-4 py-3">Gross</th>
              <th className="px-4 py-3">Net</th>
              <th className="px-4 py-3">Cost</th>
              <th className="px-4 py-3">P&L</th>
              <th className="px-4 py-3">State</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {(sales.data?.results ?? []).map((sale) => (
              <tr key={sale.id} className={sale.is_superseded ? "text-slate-500" : "text-slate-200"}>
                <td className="px-4 py-3">{sale.sale_date}</td>
                <td className="px-4 py-3">
                  {sale.item ? (
                    <Link className="text-cyan-200 hover:text-cyan-100" to={`/inventory/${sale.item}`}>
                      {sale.item_sku} {sale.item_title ? `- ${sale.item_title}` : ""}
                    </Link>
                  ) : (
                    <span>{sale.item_title || "External sale"}</span>
                  )}
                </td>
                <td className="px-4 py-3">{sale.quantity}</td>
                <td className="px-4 py-3">${sale.sale_price}</td>
                <td className="px-4 py-3">${sale.net_proceeds}</td>
                <td className="px-4 py-3">{sale.allocated_cost_basis ? `$${sale.allocated_cost_basis}` : "-"}</td>
                <td className="px-4 py-3">{sale.realised_profit ? `$${sale.realised_profit}` : "-"}</td>
                <td className="px-4 py-3">{sale.is_superseded ? "Superseded" : sale.corrected_from ? "Correction" : "Active"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-6 space-y-3 sm:hidden">
        {(sales.data?.results ?? []).map((sale) => (
          <article key={sale.id} className={`rounded border border-slate-800 bg-slate-900 p-3 ${sale.is_superseded ? "text-slate-500" : "text-slate-200"}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-mono text-sm text-slate-100">{sale.sale_date}</p>
                <p className="mt-1 break-words text-sm">
                  {sale.item ? (
                    <Link className="text-cyan-200 hover:text-cyan-100" to={`/inventory/${sale.item}`}>
                      {sale.item_sku} {sale.item_title ? `- ${sale.item_title}` : ""}
                    </Link>
                  ) : (
                    <span>{sale.item_title || "External sale"}</span>
                  )}
                </p>
              </div>
              <span className="shrink-0 rounded border border-slate-700 px-2 py-1 text-xs text-slate-300">
                {sale.is_superseded ? "Superseded" : sale.corrected_from ? "Correction" : "Active"}
              </span>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <MobileMetric label="Qty" value={String(sale.quantity)} />
              <MobileMetric label="Gross" value={`$${sale.sale_price}`} />
              <MobileMetric label="Net" value={`$${sale.net_proceeds}`} />
              <MobileMetric label="Cost" value={sale.allocated_cost_basis ? `$${sale.allocated_cost_basis}` : "-"} />
              <MobileMetric label="P&L" value={sale.realised_profit ? `$${sale.realised_profit}` : "-"} />
            </dl>
          </article>
        ))}
      </div>

      {sales.isLoading ? <EmptyState title="Loading sales" /> : null}
      {sales.error ? <AuthRequiredState detail="Sales need a Magpie session. Open the admin login, sign in, then return to Sales." /> : null}
      {sales.data && sales.data.results.length === 0 ? <EmptyState title="No sales recorded" /> : null}
    </div>
  );
}

function MobileMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded border border-slate-800 bg-slate-950/50 px-2 py-2">
      <dt className="text-xs uppercase tracking-normal text-slate-500">{label}</dt>
      <dd className="mt-1 break-words font-mono text-slate-100">{value}</dd>
    </div>
  );
}
