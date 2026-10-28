"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { Role } from "./types";

const RoleContext = createContext<{
  role: Role;
  setRole: (r: Role) => void;
  canWrite: boolean;
  canSeeOps: boolean;
} | null>(null);

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<Role>("org_admin");
  const value = useMemo(
    () => ({
      role,
      setRole,
      canWrite: role === "org_admin" || role === "campaign_manager",
      canSeeOps: role === "org_admin" || role === "auditor",
    }),
    [role],
  );
  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRole() {
  const ctx = useContext(RoleContext);
  if (!ctx) throw new Error("useRole outside provider");
  return ctx;
}
