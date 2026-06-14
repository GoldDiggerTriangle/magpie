import { Link } from "react-router-dom";

import { PhotoThumb } from "../../components/PhotoThumb";
import { StatusBadge } from "../../components/StatusBadge";
import { ValueBadge } from "../../components/ValueBadge";
import type { InventoryItemList } from "../../types";

export function ItemCard({ item }: { item: InventoryItemList }) {
  return (
    <Link className="item-card" to={`/inventory/${item.id}`}>
      <PhotoThumb src={item.main_thumb_url} alt={item.title || item.sku} />
      <div className="space-y-3 p-3">
        <div>
          <p className="line-clamp-2 min-h-10 text-sm font-semibold text-slate-100">
            {item.title || "Untitled item"}
          </p>
          <p className="mt-1 text-xs text-slate-500">{item.sku}</p>
          <p className="mt-1 text-xs text-slate-500">
            {item.quantity_remaining}/{item.quantity_total} remaining
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <StatusBadge status={item.status} />
          <ValueBadge value={item.estimated_value} currency={item.currency} />
        </div>
      </div>
    </Link>
  );
}
