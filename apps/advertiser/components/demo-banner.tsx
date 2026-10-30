"use client";

import { useApi } from "@/lib/providers";

export function DemoBanner() {
  const { mock } = useApi();
  if (!mock) return null;
  return (
    <div
      role="status"
      data-testid="demo-banner"
      className="w-full border-b border-amber-700/40 bg-amber-500/15 px-4 py-2 text-center text-xs font-medium text-amber-100"
    >
      Demo data — numbers and campaigns here are sample only, not live totals.
    </div>
  );
}
