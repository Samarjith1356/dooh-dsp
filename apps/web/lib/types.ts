export type Role = "org_admin" | "campaign_manager" | "client_viewer" | "auditor";

export type Advertiser = {
  id: number;
  company: string;
  markets: string[];
  asa_notes?: string;
};

export type ScreenSpec = {
  id: number;
  publisher: string;
  format_code: string;
  width: number;
  height: number;
  aspect: string;
  max_bytes: number;
  venue_types: string[];
  country: string;
};

export type Geofence = {
  id: number;
  name: string;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
  h3_cells: number[];
};

export type Creative = {
  id: number;
  filename: string;
  validation_status: string;
  asset_uri: string;
  width: number;
  height: number;
  mime: string;
  validation_errors?: { field: string; message: string }[];
};

export type Campaign = {
  id: number;
  advertiser_id: number;
  name: string;
  state: string;
  currency: string;
  daily_cap_micros: number;
  total_cap_micros: number;
  bid_cpm_micros: number;
  creative_ids: number[];
  geofence_ids: number[];
  priority?: number;
  flight_start?: string | null;
  flight_end?: string | null;
  remaining_micros?: number | null;
};

export type CampaignPlan = {
  id?: number;
  goal: string;
  approved: boolean;
  dayparts: { dow: number; hours: number[] }[];
  venue_allowlist: string[];
  countries: string[];
  geofence_ids: number[];
  bid_cpm_micros: number;
  shade_factor: number;
  created_at?: string;
};

export type HourlyRow = {
  advertiser_id: number;
  campaign_id: number;
  hour: string;
  event_type: string;
  bids: number | string;
  imps: number;
  spend_micros: number | string;
};

export type EventRow = {
  event_time: string;
  event_type: string;
  campaign_id: number;
  country: string;
  venue_type: string;
  creative_id: number;
  bid_request_id: string;
  price_cpm: number;
  qty_multiplier: number;
  billable_imps: number;
  spend_micros: number;
};

export type Kpis = {
  bids: number;
  billable_imps: number;
  spend_micros: number;
  avg_cpm: number;
  gb_imps: number;
  ie_imps: number;
  hours: number;
};

export type FleetHealth = {
  ok: boolean;
  services: { name: string; ok: boolean; status: number; latency_ms: number; error?: string; body?: string }[];
};

export type AgentChatResponse = {
  reply: string;
  plan: CampaignPlan | Record<string, unknown> | null;
  needs_approval?: boolean;
  compliance_flags?: string[];
};
