import { LayoutDashboard, PackageSearch, PlusCircle, Settings } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/inventory", label: "Inventory", icon: PackageSearch },
  { to: "/add", label: "Add", icon: PlusCircle },
  { to: "/settings/ebay", label: "Settings", icon: Settings }
];

export function AppShell() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <aside className="fixed left-0 top-0 hidden h-full w-64 border-r border-slate-800 bg-slate-950/95 p-5 md:block">
        <div>
          <p className="text-lg font-semibold">Gold, Stamps & Phonetech</p>
          <p className="mt-1 text-sm text-slate-500">Inventory</p>
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
      <main className="min-h-screen pb-24 md:ml-64 md:pb-0">
        <Outlet />
      </main>
      <nav className="fixed bottom-0 left-0 right-0 z-40 grid grid-cols-4 border-t border-slate-800 bg-slate-950 md:hidden">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={({ isActive }) => `mobile-nav-link ${isActive ? "mobile-nav-link-active" : ""}`} end={to === "/"}>
            <Icon className="h-5 w-5" aria-hidden="true" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
