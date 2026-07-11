import { createBrowserRouter } from "react-router-dom";

import { App } from "./App";
import { AdminRouteRecovery } from "./components/AdminRouteRecovery";
import { AddItem } from "./features/capture/AddItem";
import { Dashboard } from "./features/dashboard/Dashboard";
import { EbayOrders } from "./features/ebay/EbayOrders";
import { InventoryGrid } from "./features/inventory/InventoryGrid";
import { ItemDetail } from "./features/inventory/ItemDetail";
import { ChannelListingsPage } from "./features/listings/ChannelListingsPage";
import { BuyCalculator } from "./features/profit/BuyCalculator";
import { LotDetail, LotsPage } from "./features/profit/LotsPage";
import { ProfitPage } from "./features/profit/ProfitPage";
import { SalesList } from "./features/sales/SalesList";
import { EbaySettings } from "./features/settings/EbaySettings";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "dashboard", element: <Dashboard /> },
      { path: "inventory", element: <InventoryGrid /> },
      { path: "inventory/:id", element: <ItemDetail /> },
      { path: "sales", element: <SalesList /> },
      { path: "profit", element: <ProfitPage /> },
      { path: "listings", element: <ChannelListingsPage /> },
      { path: "lots", element: <LotsPage /> },
      { path: "lots/:id", element: <LotDetail /> },
      { path: "buy-calculator", element: <BuyCalculator /> },
      { path: "ebay/orders", element: <EbayOrders /> },
      { path: "add", element: <AddItem /> },
      { path: "settings/ebay", element: <EbaySettings /> },
      { path: "admin/*", element: <AdminRouteRecovery /> }
    ]
  }
]);
