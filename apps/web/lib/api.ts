import type {
  Advertiser,
  AgentChatResponse,
  Campaign,
  CampaignPlan,
  Creative,
  EventRow,
  FleetHealth,
  Geofence,
  HourlyRow,
  Kpis,
  ScreenSpec,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const BRAIN = process.env.NEXT_PUBLIC_BRAIN_URL || "http://localhost:8001";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `${res.status} ${path}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  advertisers: () => request<Advertiser[]>("/v1/advertisers"),
  createAdvertiser: (body: { company: string; email: string; name?: string; markets: string[] }) =>
    request<Advertiser>("/v1/advertisers", { method: "POST", body: JSON.stringify(body) }),
  specs: () => request<ScreenSpec[]>("/v1/screen-specs"),
  geofences: (advertiserId: number) => request<Geofence[]>(`/v1/geofences?advertiser_id=${advertiserId}`),
  creatives: (advertiserId: number) => request<Creative[]>(`/v1/creatives?advertiser_id=${advertiserId}`),
  uploadCreative: (form: FormData) => request<Creative>("/v1/creatives", { method: "POST", body: form }),
  campaigns: (advertiserId: number) => request<Campaign[]>(`/v1/campaigns?advertiser_id=${advertiserId}`),
  campaign: (id: number) => request<Campaign>(`/v1/campaigns/${id}`),
  createCampaign: (body: Partial<Campaign> & { advertiser_id: number; name: string }) =>
    request<Campaign>("/v1/campaigns", { method: "POST", body: JSON.stringify(body) }),
  setState: (id: number, state: string) =>
    request<Campaign>(`/v1/campaigns/${id}/state`, { method: "POST", body: JSON.stringify({ state }) }),
  plans: (campaignId: number) => request<CampaignPlan[]>(`/v1/campaigns/${campaignId}/plans`),
  createPlan: (campaignId: number, body: Record<string, unknown>) =>
    request<{ id: number; approved: boolean }>(`/v1/campaigns/${campaignId}/plans`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  approvePlan: (planId: number) => request<{ id: number; approved: boolean }>(`/v1/plans/${planId}/approve`, { method: "POST" }),
  chat: (advertiserId: number, campaignId: number | null, message: string) =>
    request<AgentChatResponse>("/v1/agent/chat", {
      method: "POST",
      body: JSON.stringify({ advertiser_id: advertiserId, campaign_id: campaignId, message }),
    }),
  hourly: (advertiserId: number, campaignId?: number) =>
    request<HourlyRow[]>(
      `/v1/analytics/hourly?advertiser_id=${advertiserId}${campaignId ? `&campaign_id=${campaignId}` : ""}`,
    ),
  kpis: (advertiserId: number, campaignId?: number) =>
    request<Kpis>(
      `/v1/analytics/kpis?advertiser_id=${advertiserId}${campaignId ? `&campaign_id=${campaignId}` : ""}`,
    ),
  events: (advertiserId: number, limit = 200, campaignId?: number) =>
    request<EventRow[]>(
      `/v1/analytics/events?advertiser_id=${advertiserId}&limit=${limit}${campaignId ? `&campaign_id=${campaignId}` : ""}`,
    ),
  insights: (advertiserId: number) =>
    request<{ live: string; stored: { id: number; markdown: string }[] }>(`/v1/insights?advertiser_id=${advertiserId}`),
  fleet: () => request<FleetHealth>("/v1/ops/health"),
  compile: () =>
    fetch(`${BRAIN}/compile`, { method: "POST" }).then(async (res) => {
      if (!res.ok) throw new Error(await res.text());
      return res.json() as Promise<{ snapshot_id: number; campaigns: number }>;
    }),
};
