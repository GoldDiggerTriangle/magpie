import { createBrowserRouter } from "react-router-dom";

import { App } from "./App";
import { AddItem } from "./features/capture/AddItem";
import { Dashboard } from "./features/dashboard/Dashboard";
import { InventoryGrid } from "./features/inventory/InventoryGrid";
import { ItemDetail } from "./features/inventory/ItemDetail";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "inventory", element: <InventoryGrid /> },
      { path: "inventory/:id", element: <ItemDetail /> },
      { path: "add", element: <AddItem /> }
    ]
  }
]);
