import { Boxes, Calculator, DownloadCloud, LayoutDashboard, Megaphone, PackageSearch, PlusCircle, ReceiptText, Settings, TrendingUp } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Dashboard", shortLabel: "Home", icon: LayoutDashboard },
  { to: "/inventory", label: "Inventory", shortLabel: "Items", icon: PackageSearch },
  { to: "/sales", label: "Sales", shortLabel: "Sales", icon: ReceiptText },
  { to: "/profit", label: "Profit", shortLabel: "Profit", icon: TrendingUp },
  { to: "/listings", label: "Listings", shortLabel: "List", icon: Megaphone },
  { to: "/lots", label: "Lots", shortLabel: "Lots", icon: Boxes },
  { to: "/buy-calculator", label: "Buy Calculator", shortLabel: "Buy", icon: Calculator },
  { to: "/ebay/orders", label: "eBay Orders", shortLabel: "eBay", icon: DownloadCloud },
  { to: "/add", label: "Add", shortLabel: "Add", icon: PlusCircle },
  { to: "/settings/ebay", label: "Settings", shortLabel: "Settings", icon: Settings }
];

export function AppShell() {
  return (
    <div className="app-shell min-h-screen bg-[#FFFFFF] text-[#0F172A]">
      <aside className="desktop-sidebar fixed left-0 top-0 hidden h-full w-64 border-r border-[#CBD5E1] bg-white p-5 md:block">
        <div>
          <p className="text-lg font-semibold text-[#0F172A]">Gold, Stamps & Phonetech</p>
          <p className="mt-1 text-sm text-[#334155]">Inventory</p>
        </div>
        <nav className="mt-8 space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `nav-link ${isActive ? "nav-link-active" : ""}`} end={to === "/"}>
              <Icon className="h-5 w-5" aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="app-main min-h-screen pb-24 md:ml-64 md:pb-0">
        <Outlet />
      </main>
      <nav className="mobile-bottom-nav fixed bottom-0 left-0 right-0 z-40 grid grid-cols-5 border-t border-[#CBD5E1] bg-white md:hidden">
        {navItems.map(({ to, shortLabel, icon: Icon }) => (
          <NavLink key={to} to={to} className={({ isActive }) => `mobile-nav-link ${isActive ? "mobile-nav-link-active" : ""}`} end={to === "/"}>
            <Icon className="h-5 w-5" aria-hidden="true" />
            <span>{shortLabel}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
