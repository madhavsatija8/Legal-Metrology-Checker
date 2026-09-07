import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { RoleGate } from "./components/RoleGate";
import { useAuth } from "./lib/auth";
import { Login } from "./pages/Login";
import { Products } from "./pages/Products";
import { ProductDetail } from "./pages/ProductDetail";
import { Scans } from "./pages/Scans";
import { ScanDetail } from "./pages/ScanDetail";
import { Violations } from "./pages/Violations";
import { RuleVersions } from "./pages/RuleVersions";
import { Users } from "./pages/Users";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex min-h-screen items-center justify-center text-ink-soft">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/products" replace />} />
        <Route path="products" element={<Products />} />
        <Route path="products/:id" element={<ProductDetail />} />
        <Route path="scans" element={<Scans />} />
        <Route path="scans/:id" element={<ScanDetail />} />
        <Route path="violations" element={<Violations />} />
        <Route
          path="rule-versions"
          element={
            <RoleGate roles={["admin"]}>
              <RuleVersions />
            </RoleGate>
          }
        />
        <Route
          path="users"
          element={
            <RoleGate roles={["admin"]}>
              <Users />
            </RoleGate>
          }
        />
        <Route path="*" element={<Navigate to="/products" replace />} />
      </Route>
    </Routes>
  );
}
