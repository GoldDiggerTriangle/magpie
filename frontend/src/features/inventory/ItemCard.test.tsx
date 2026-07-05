import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ItemCard } from "./ItemCard";
import type { InventoryItemList } from "../../types";

const item: InventoryItemList = {
  id: "item-1",
  sku: "STM-00001",
  title: "Blue stamp",
  status: "needs_research",
  condition: "good",
  category: "cat-1",
  category_name: "Stamps",
  lot: null,
  source: null,
  source_name: null,
  disposition: "for_sale",
  scrapped_at: null,
  quantity_total: 4,
  quantity_sold: 1,
  quantity_remaining: 3,
  estimated_value: "25.00",
  currency: "AUD",
  main_thumb_url: null,
  created_at: "2026-06-09T00:00:00Z"
};

test("ItemCard renders title, SKU, and status badge", () => {
  render(
    <MemoryRouter>
      <ItemCard item={item} />
    </MemoryRouter>
  );

  expect(screen.getByText("Blue stamp")).toBeInTheDocument();
  expect(screen.getByText("STM-00001")).toBeInTheDocument();
  expect(screen.getByText("Needs research")).toBeInTheDocument();
  expect(screen.getByText("3/4 remaining")).toBeInTheDocument();
});
