import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { RoleGate } from "./RoleGate";
import {
  FileSearch,
  Gavel,
  LayoutGrid,
  LogOut,
  Menu,
  ScrollText,
  ShieldCheck,
  Users as UsersIcon,
  X,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/products", label: "Products", icon: LayoutGrid },
  { to: "/scans", label: "Scans", icon: FileSearch },
  { to: "/violations", label: "Violations", icon: Gavel },
];

const ADMIN_NAV_ITEMS = [
  { to: "/rule-versions", label: "Rule versions", icon: ScrollText },
  { to: "/users", label: "Users", icon: UsersIcon },
];

function NavItem({ to, label, icon: Icon, onNavigate }: { to: string; label: string; icon: typeof LayoutGrid; onNavigate?: () => void }) {
  return (
    <NavLink
      to={to}
      onClick={onNavigate}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors ${
          isActive ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5 hover:text-white"
        }`
      }
    >
      <Icon className="h-[18px] w-[18px]" />
      {label}
    </NavLink>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 px-5 pb-6 pt-6">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-action text-white shadow-pop">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <p className="truncate font-serif text-[15px] font-bold leading-tight text-white">Compliance Register</p>
          <p className="truncate text-[11px] text-white/50">Legal Metrology · Packaged Commodities</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map((item) => (
          <NavItem key={item.to} {...item} onNavigate={onNavigate} />
        ))}
        <RoleGate roles={["admin"]}>
          <p className="px-3.5 pb-1 pt-5 text-[11px] font-semibold uppercase tracking-wider text-white/30">Admin</p>
          {ADMIN_NAV_ITEMS.map((item) => (
            <NavItem key={item.to} {...item} onNavigate={onNavigate} />
          ))}
        </RoleGate>
      </nav>

      {user && (
        <div className="m-3 flex items-center gap-2.5 rounded-xl bg-white/5 p-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-action text-xs font-bold text-white">
            {user.full_name.slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{user.full_name}</p>
            <p className="truncate text-xs capitalize text-white/50">{user.role}</p>
          </div>
          <button onClick={logout} title="Sign out" className="rounded-lg p-1.5 text-white/50 hover:bg-white/10 hover:text-white">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}

function pageTitle(pathname: string): { title: string; subtitle: string } {
  if (pathname.startsWith("/scans")) return { title: "Scans", subtitle: "Label scans and their extracted declarations" };
  if (pathname.startsWith("/violations")) return { title: "Violations", subtitle: "Findings raised across all scans" };
  if (pathname.startsWith("/rule-versions")) return { title: "Rule versions", subtitle: "Legal Metrology (Packaged Commodities) Rules, 2011 config history" };
  if (pathname.startsWith("/users")) return { title: "Users", subtitle: "Inspectors, supervisors, and admins" };
  return { title: "Products", subtitle: "Registered products and their compliance status" };
}

export function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { title, subtitle } = pageTitle(location.pathname);

  return (
    <div className="min-h-screen bg-paper lg:flex">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 bg-sidebar lg:block">
        <div className="sticky top-0 h-screen">
          <SidebarContent />
        </div>
      </aside>

      {/* Mobile sidebar */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-64 bg-sidebar shadow-pop">
            <button
              onClick={() => setMobileOpen(false)}
              className="absolute right-3 top-3 rounded-lg p-1.5 text-white/60 hover:bg-white/10"
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-10 border-b border-rule bg-paper-raised/90 backdrop-blur">
          <div className="flex items-center gap-3 px-5 py-4 sm:px-8">
            <button
              onClick={() => setMobileOpen(true)}
              className="rounded-lg border border-rule p-2 text-ink-soft hover:bg-paper lg:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="min-w-0">
              <h1 className="truncate font-serif text-xl font-bold tracking-tight text-ink">{title}</h1>
              <p className="truncate text-sm text-ink-soft">{subtitle}</p>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-5 py-6 sm:px-8 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
