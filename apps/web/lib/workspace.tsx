"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type Region = "ALL" | "GB" | "IE";

const WorkspaceContext = createContext<{
  advertiserId: number;
  setAdvertiserId: (id: number) => void;
  region: Region;
  setRegion: (r: Region) => void;
  campaignId: number | null;
  setCampaignId: (id: number | null) => void;
} | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [advertiserId, setAdvertiserId] = useState(1);
  const [region, setRegion] = useState<Region>("ALL");
  const [campaignId, setCampaignId] = useState<number | null>(null);
  const value = useMemo(
    () => ({ advertiserId, setAdvertiserId, region, setRegion, campaignId, setCampaignId }),
    [advertiserId, region, campaignId],
  );
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace outside provider");
  return ctx;
}
