import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listSales } from "../../api/sales";
import { EmptyState } from "../../components/EmptyState";

export function SalesList() {
  const sales = useQuery({ queryKey: ["sales"], queryFn: listSales });

  return (
    <div className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
      <div>
        <h1 className="page-title">Sales</h1>
        <p className="mt-1 text-sm text-slate-500">{sales.data?.count ?? 0} records</p>
      </div>

      <div className="mt-6 overflow-x-auto rounded border border-slate-800 bg-slate-900">
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
                  <Link className="text-cyan-200 hover:text-cyan-100" to={`/inventory/${sale.item}`}>
                    {sale.item_sku} {sale.item_title ? `- ${sale.item_title}` : ""}
                  </Link>
                </td>
                <td className="px-4 py-3">{sale.quantity}</td>
                <td className="px-4 py-3">${sale.sale_price}</td>
                <td className="px-4 py-3">${sale.net_proceeds}</td>
                <td className="px-4 py-3">${sale.allocated_cost_basis}</td>
                <td className="px-4 py-3">${sale.realised_profit}</td>
                <td className="px-4 py-3">{sale.is_superseded ? "Superseded" : sale.corrected_from ? "Correction" : "Active"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {sales.isLoading ? <EmptyState title="Loading sales" /> : null}
      {sales.error ? <EmptyState title="Unable to load sales" detail="Check your Django admin session." /> : null}
      {sales.data && sales.data.results.length === 0 ? <EmptyState title="No sales recorded" /> : null}
    </div>
  );
}
