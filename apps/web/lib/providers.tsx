"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Toaster } from "sonner";
import { RoleProvider } from "./rbac";
import { WorkspaceProvider } from "./workspace";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 8_000, refetchOnWindowFocus: false, retry: 1 },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <RoleProvider>
        <WorkspaceProvider>
          {children}
          <Toaster position="top-right" richColors closeButton />
        </WorkspaceProvider>
      </RoleProvider>
    </QueryClientProvider>
  );
}
