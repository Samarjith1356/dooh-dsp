/** Typed client for contracts/advertiser-app.md. Mock by default. */

export type Money = { micros: number; currency: "EUR" };

export type Me = {
  id: string;
  email: string;
  account_type: "business" | "creator";
  profile?: { name: string; category: string; lat: number; lng: number; address: string };
};

export type Screen = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  venue_type: string;
  format: "landscape_1920x1080" | "portrait_1080x1920";
  media_owner: string;
};

export type Daypart = "morning" | "lunch" | "evening" | "all_day";

export type EstimateRequest = {
  screen_ids: string[];
  start: string;
  end: string;
  dayparts: Daypart[];
  budget: Money;
};

export type Estimate = {
  plays_low: number;
  plays_high: number;
  impressions_low: number;
  impressions_high: number;
  note: string;
};

export type CreativeCheck = {
  creative_id: string;
  ok: boolean;
  problems: string[];
  format?: Screen["format"];
  duration_s?: number;
};

export type ComplianceResult = {
  verdict: "pass" | "fix_needed" | "human_review";
  reasons: { rule: string; message: string }[];
};

export type CampaignStatus =
  | "draft"
  | "submitted"
  | "compliance_review"
  | "awaiting_media_owner"
  | "live"
  | "paused"
  | "finished"
  | "rejected";

export type Campaign = {
  id: string;
  name: string;
  status: CampaignStatus;
  goal: string;
  screen_ids: string[];
  start: string;
  end: string;
  dayparts: string[];
  budget: Money;
  spent: Money;
  creative_id?: string;
  compliance?: ComplianceResult;
};

export type Report = {
  plays: number;
  impressions: number;
  spent: Money;
  by_screen: { screen_id: string; plays: number; impressions: number }[];
  first_event_at?: string;
  last_event_at?: string;
};

export type Wallet = {
  balance: Money;
  invoices: { id: string; date: string; amount: Money; url: string }[];
};

export type AgentMessage = { role: "user" | "agent"; text: string; created_at: string };

export type ProfileInput = {
  name: string;
  category: string;
  lat: number;
  lng: number;
  address: string;
};

export type SignUpInput = {
  email: string;
  password: string;
  account_type: "business" | "creator";
};

export type CreateCampaignInput = {
  name: string;
  goal: string;
  screen_ids: string[];
  start: string;
  end: string;
  dayparts: Daypart[];
  budget: Money;
  creative_id?: string;
  /** Demo-only: force a compliance outcome on submit. */
  demo_compliance?: ComplianceResult["verdict"];
};

export type CreativeUploadMeta = {
  filename: string;
  mime: string;
  width?: number;
  height?: number;
  duration_s?: number;
};

export type ApiClient = {
  signUp(input: SignUpInput): Promise<Me>;
  getMe(): Promise<Me | null>;
  updateProfile(input: ProfileInput): Promise<Me>;
  listCampaigns(): Promise<Campaign[]>;
  getCampaign(id: string): Promise<Campaign>;
  getReport(id: string): Promise<Report>;
  createCampaign(input: CreateCampaignInput): Promise<Campaign>;
  submitCampaign(id: string, demoCompliance?: ComplianceResult["verdict"]): Promise<Campaign>;
  listScreens(lat: number, lng: number, radius_m: number): Promise<Screen[]>;
  estimate(req: EstimateRequest): Promise<Estimate>;
  uploadCreative(meta: CreativeUploadMeta): Promise<CreativeCheck>;
  getWallet(): Promise<Wallet>;
  topUp(amount: Money): Promise<Wallet>;
  sendAgentMessage(text: string): Promise<AgentMessage[]>;
  getAgentMessages(): Promise<AgentMessage[]>;
  isMock(): boolean;
  isCategoryRefused(category: string): boolean;
  categoryRefusalMessage(category: string): string;
};

const mode = (process.env.NEXT_PUBLIC_API_MODE ?? "mock").toLowerCase();

let clientPromise: Promise<ApiClient> | null = null;

export function isMockMode() {
  return mode !== "live";
}

export async function getApi(): Promise<ApiClient> {
  if (!clientPromise) {
    clientPromise = mode === "live" ? loadLive() : loadMock();
  }
  return clientPromise;
}

async function loadMock(): Promise<ApiClient> {
  const { createMockClient } = await import("./mock");
  return createMockClient();
}

async function loadLive(): Promise<ApiClient> {
  throw new Error(
    "Live API is not wired yet. Set NEXT_PUBLIC_API_MODE=mock (default) until Platform ships the endpoints.",
  );
}

export const REFUSED_CATEGORIES = ["alcohol", "gambling", "political"] as const;

export const BIDDING_EXPLAINER =
  "You set a budget. Whenever one of your screens has a free slot, we bid for it automatically. You only pay when your ad actually plays, and never more than your budget.";

export const CATEGORIES = [
  "cafe",
  "retail",
  "restaurant",
  "fitness",
  "events",
  "creator",
  "charity",
  "alcohol",
  "gambling",
  "political",
  "other",
] as const;
