"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getApi, isMockMode, type ApiClient, type Me } from "./api";

type ApiContextValue = {
  api: ApiClient | null;
  me: Me | null;
  loading: boolean;
  mock: boolean;
  refreshMe: () => Promise<void>;
  setMe: (me: Me | null) => void;
};

const ApiContext = createContext<ApiContextValue | null>(null);

export function Providers({ children }: { children: ReactNode }) {
  const [api, setApi] = useState<ApiClient | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const mock = isMockMode();

  const refreshMe = useCallback(async () => {
    const client = api ?? (await getApi());
    if (!api) setApi(client);
    const next = await client.getMe();
    setMe(next);
  }, [api]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const client = await getApi();
        if (cancelled) return;
        setApi(client);
        setMe(await client.getMe());
        if (mock && typeof window !== "undefined") {
          (window as Window & { __advertiserApi?: ApiClient }).__advertiserApi = client;
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mock]);

  return (
    <ApiContext.Provider value={{ api, me, loading, mock, refreshMe, setMe }}>{children}</ApiContext.Provider>
  );
}

export function useApi() {
  const ctx = useContext(ApiContext);
  if (!ctx) throw new Error("useApi must be used within Providers");
  return ctx;
}
