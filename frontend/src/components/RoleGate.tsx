import type { ReactNode } from "react";
import { useAuth } from "../lib/auth";
import type { UserRole } from "../lib/types";

export function RoleGate({ roles, children }: { roles: UserRole[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) return null;
  return <>{children}</>;
}
