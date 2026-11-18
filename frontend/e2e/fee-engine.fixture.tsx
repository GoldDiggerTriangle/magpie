import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "../src/components/AppShell";
import { FeeEnginePanel } from "../src/components/FeeEnginePanel";
import "../src/styles/index.css";
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={["/settings/ebay"]}><Routes><Route element={<AppShell />}><Route path="/settings/ebay" element={<div className="settings-page"><h1>Settings · isolated fixture</h1><FeeEnginePanel /></div>} /></Route></Routes></MemoryRouter></QueryClientProvider>);
