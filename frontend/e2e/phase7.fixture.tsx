import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "../src/components/AppShell";
import { EbayConnectionHealth } from "../src/components/EbayConnectionHealth";
import "../src/styles/index.css";

const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/settings/ebay"]}>
  <Routes><Route element={<AppShell />}><Route path="/settings/ebay" element={<div className="item-page-frame"><h1 className="page-title">Settings</h1><EbayConnectionHealth /><label className="label">Local item note<input className="field" /></label></div>} /></Route></Routes>
</MemoryRouter></QueryClientProvider>);
