import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { RoleGate } from "./RoleGate";

function TabLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `border-b-2 px-1 pb-3 pt-1 text-sm transition-colors ${
          isActive ? "border-ink text-ink font-medium" : "border-transparent text-ink-soft hover:text-ink"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-rule bg-paper-raised">
        <div className="mx-auto flex max-w-6xl items-baseline justify-between px-6 pt-5">
          <div>
            <p className="font-serif text-xl font-semibold tracking-tight text-ink">Compliance Register</p>
            <p className="text-xs text-ink-soft">Legal Metrology (Packaged Commodities) Rules, 2011</p>
          </div>
          {user && (
            <div className="flex items-baseline gap-4 text-sm text-ink-soft">
              <span>
                {user.full_name} <span className="text-ink-soft/70">· {user.role}</span>
              </span>
              <button onClick={logout} className="text-action hover:underline">
                Sign out
              </button>
            </div>
          )}
        </div>
        <nav className="mx-auto flex max-w-6xl gap-6 px-6">
          <TabLink to="/products">Products</TabLink>
          <TabLink to="/scans">Scans</TabLink>
          <TabLink to="/violations">Violations</TabLink>
          <RoleGate roles={["admin"]}>
            <TabLink to="/rule-versions">Rule versions</TabLink>
            <TabLink to="/users">Users</TabLink>
          </RoleGate>
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
