import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { listCategories } from "../../api/categories";
import { listItems } from "../../api/items";
import { EmptyState } from "../../components/EmptyState";
import { CategorySelect } from "../../components/CategorySelect";
import { ItemCard } from "./ItemCard";

const statusOptions = [
  ["", "All statuses"],
  ["captured", "Captured"],
  ["needs_identification", "Needs ID"],
  ["needs_research", "Needs research"],
  ["ready_to_list", "Ready"],
  ["listed", "Listed"],
  ["partially_sold", "Partially sold"],
  ["sold", "Sold"],
  ["stored", "Stored"]
];

const conditionOptions = [
  ["", "All conditions"],
  ["ungraded", "Ungraded"],
  ["new", "New"],
  ["like_new", "Like new"],
  ["very_good", "Very good"],
  ["good", "Good"],
  ["acceptable", "Acceptable"],
  ["for_parts", "For parts"]
];

export function InventoryGrid() {
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState(Number(params.get("page") ?? "1"));

  const query = useMemo(
    () => ({
      page,
      search: params.get("search") ?? "",
      status: params.get("status") ?? "",
      category: params.get("category") ?? "",
      condition: params.get("condition") ?? "",
      has_photos: params.get("has_photos") ?? ""
    }),
    [page, params]
  );

  const items = useQuery({ queryKey: ["items", query], queryFn: () => listItems(query) });
  const categories = useQuery({ queryKey: ["categories"], queryFn: listCategories });

  function updateParam(key: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    next.delete("page");
    setPage(1);
    setParams(next);
  }

  return (
    <div className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="page-title">Inventory</h1>
          <p className="mt-1 text-sm text-slate-500">{items.data?.count ?? 0} items</p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <input
            className="field"
            placeholder="Search"
            value={params.get("search") ?? ""}
            onChange={(event) => updateParam("search", event.target.value)}
          />
          <select className="field" value={params.get("status") ?? ""} onChange={(event) => updateParam("status", event.target.value)}>
            {statusOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <select className="field" value={params.get("condition") ?? ""} onChange={(event) => updateParam("condition", event.target.value)}>
            {conditionOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <CategorySelect
            categories={categories.data?.results ?? []}
            value={params.get("category")}
            onChange={(value) => updateParam("category", value)}
          />
        </div>
      </div>

      <div className="mt-6">
        {items.isLoading ? <EmptyState title="Loading inventory" /> : null}
        {items.error ? <EmptyState title="Unable to load inventory" detail="Check your Django admin session." /> : null}
        {items.data && items.data.results.length === 0 ? <EmptyState title="No items found" /> : null}
        {items.data && items.data.results.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {items.data.results.map((item) => <ItemCard key={item.id} item={item} />)}
          </div>
        ) : null}
      </div>

      {items.data ? (
        <div className="mt-6 flex justify-between">
          <button className="btn-secondary" disabled={!items.data.previous} onClick={() => setPage(Math.max(1, page - 1))} type="button">
            Previous
          </button>
          <button className="btn-secondary" disabled={!items.data.next} onClick={() => setPage(page + 1)} type="button">
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}
