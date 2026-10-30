import type {
  AgentMessage,
  ApiClient,
  Campaign,
  ComplianceResult,
  CreateCampaignInput,
  CreativeCheck,
  CreativeUploadMeta,
  Estimate,
  EstimateRequest,
  Me,
  Money,
  ProfileInput,
  Report,
  Screen,
  SignUpInput,
  Wallet,
} from "./api";
import { REFUSED_CATEGORIES } from "./api";

const STORAGE_KEY = "advertiser-app-demo-v1";

type Store = {
  me: Me | null;
  campaigns: Campaign[];
  wallet: Wallet;
  creatives: Record<string, CreativeUploadMeta & { id: string }>;
  messages: AgentMessage[];
};

const DEMO_SCREENS: Screen[] = [
  {
    id: "scr-grafton",
    name: "Grafton Street Digi",
    lat: 53.3425,
    lng: -6.2597,
    venue_type: "high_street",
    format: "landscape_1920x1080",
    media_owner: "Demo Media Dublin",
  },
  {
    id: "scr-temple-bar",
    name: "Temple Bar Corner",
    lat: 53.3454,
    lng: -6.2641,
    venue_type: "nightlife",
    format: "portrait_1080x1920",
    media_owner: "Demo Media Dublin",
  },
  {
    id: "scr-st-stephens",
    name: "St Stephen's Green Mall",
    lat: 53.3382,
    lng: -6.2591,
    venue_type: "mall",
    format: "landscape_1920x1080",
    media_owner: "Demo Screens IE",
  },
  {
    id: "scr-connolly",
    name: "Connolly Station Concourse",
    lat: 53.352,
    lng: -6.2488,
    venue_type: "transit",
    format: "landscape_1920x1080",
    media_owner: "Demo Transit Ads",
  },
  {
    id: "scr-heuston",
    name: "Heuston Plaza",
    lat: 53.3463,
    lng: -6.2927,
    venue_type: "transit",
    format: "landscape_1920x1080",
    media_owner: "Demo Transit Ads",
  },
  {
    id: "scr-docklands",
    name: "Docklands Boardwalk",
    lat: 53.3472,
    lng: -6.2315,
    venue_type: "street",
    format: "portrait_1080x1920",
    media_owner: "Demo Screens IE",
  },
  {
    id: "scr-pheenix",
    name: "Phoenix Park Gate",
    lat: 53.3558,
    lng: -6.3094,
    venue_type: "park",
    format: "landscape_1920x1080",
    media_owner: "Demo Media Dublin",
  },
  {
    id: "scr-rathmines",
    name: "Rathmines Road",
    lat: 53.3224,
    lng: -6.2653,
    venue_type: "neighbourhood",
    format: "landscape_1920x1080",
    media_owner: "Demo Screens IE",
  },
  {
    id: "scr-smithfield",
    name: "Smithfield Square",
    lat: 53.3489,
    lng: -6.2781,
    venue_type: "square",
    format: "portrait_1080x1920",
    media_owner: "Demo Media Dublin",
  },
  {
    id: "scr-ballsbridge",
    name: "Ballsbridge Village",
    lat: 53.3287,
    lng: -6.2304,
    venue_type: "neighbourhood",
    format: "landscape_1920x1080",
    media_owner: "Demo Screens IE",
  },
];

function money(euros: number): Money {
  return { micros: Math.round(euros * 1_000_000), currency: "EUR" };
}

function nowIso() {
  return new Date().toISOString();
}

function uid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

function haversineM(lat1: number, lng1: number, lat2: number, lng2: number) {
  const R = 6371000;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function defaultStore(): Store {
  return {
    me: null,
    campaigns: [
      {
        id: "camp-demo-lunch",
        name: "Lunch rush (demo)",
        status: "live",
        goal: "footfall",
        screen_ids: ["scr-grafton", "scr-st-stephens", "scr-rathmines"],
        start: "2026-10-01",
        end: "2026-10-31",
        dayparts: ["lunch"],
        budget: money(250),
        spent: money(87.4),
        creative_id: "cre-demo-1",
        compliance: { verdict: "pass", reasons: [] },
      },
      {
        id: "camp-demo-event",
        name: "Weekend pop-up (demo)",
        status: "awaiting_media_owner",
        goal: "event",
        screen_ids: ["scr-temple-bar", "scr-smithfield"],
        start: "2026-11-07",
        end: "2026-11-09",
        dayparts: ["evening", "all_day"],
        budget: money(120),
        spent: money(0),
        creative_id: "cre-demo-2",
        compliance: {
          verdict: "human_review",
          reasons: [{ rule: "demo", message: "Demo campaign waiting on media-owner approval." }],
        },
      },
    ],
    wallet: {
      balance: money(500),
      invoices: [
        {
          id: "inv-demo-1",
          date: "2026-10-15",
          amount: money(100),
          url: "#demo-invoice",
        },
      ],
    },
    creatives: {},
    messages: [
      {
        role: "agent",
        text: "Hi — I'm your Advertiser Agent (AI). Ask me about budgets, screens near you, or how bidding works. This chat uses demo replies only.",
        created_at: nowIso(),
      },
    ],
  };
}

function loadStore(): Store {
  if (typeof window === "undefined") return defaultStore();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultStore();
    return { ...defaultStore(), ...JSON.parse(raw) } as Store;
  } catch {
    return defaultStore();
  }
}

function saveStore(store: Store) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    // ignore quota / private mode
  }
}

function categoryRefusalMessage(category: string) {
  const c = category.toLowerCase();
  if (c === "alcohol") {
    return "We can't run alcohol ads on this product yet. Irish rules need extra checks we haven't built. Pick another category, or contact us.";
  }
  if (c === "gambling") {
    return "Gambling ads aren't allowed here. We refuse this category so you don't waste a budget on a campaign we would block.";
  }
  if (c === "political") {
    return "Political advertising isn't supported. Choose a different category to continue.";
  }
  return "";
}

function isCategoryRefused(category: string) {
  return (REFUSED_CATEGORIES as readonly string[]).includes(category.toLowerCase());
}

function buildEstimate(req: EstimateRequest): Estimate {
  const screens = Math.max(req.screen_ids.length, 1);
  const euros = req.budget.micros / 1_000_000;
  const daypartFactor = req.dayparts.includes("all_day") ? 1.4 : 0.7 + req.dayparts.length * 0.2;
  const playsMid = Math.round(euros * 1.8 * screens * daypartFactor);
  const impMid = Math.round(playsMid * 42);
  return {
    plays_low: Math.max(1, Math.round(playsMid * 0.7)),
    plays_high: Math.round(playsMid * 1.35),
    impressions_low: Math.max(10, Math.round(impMid * 0.7)),
    impressions_high: Math.round(impMid * 1.35),
    note: "Demo estimate — a range based on your budget and screens, not a guarantee.",
  };
}

function checkCreative(meta: CreativeUploadMeta): CreativeCheck {
  const id = uid("cre");
  const problems: string[] = [];
  let format: Screen["format"] | undefined;
  const isVideo = meta.mime.startsWith("video/") || /\.(mp4|webm|mov)$/i.test(meta.filename);

  if (isVideo) {
    if (meta.duration_s == null || !Number.isFinite(meta.duration_s)) {
      problems.push("Could not read video duration. Re-export the file or pick another video.");
    } else if (meta.duration_s > 15) {
      problems.push(`Video is ${meta.duration_s}s. Maximum length is 15 seconds.`);
    }
    if (meta.width == null || meta.height == null || !Number.isFinite(meta.width) || !Number.isFinite(meta.height)) {
      problems.push("Could not read video dimensions. Re-export the file or pick another video.");
    } else if (meta.width === 1920 && meta.height === 1080) {
      format = "landscape_1920x1080";
    } else if (meta.width === 1080 && meta.height === 1920) {
      format = "portrait_1080x1920";
    } else {
      problems.push(`Video size ${meta.width}×${meta.height} is not supported. Use 1920×1080 or 1080×1920.`);
    }
  } else {
    if (meta.width && meta.height) {
      if (meta.width === 1920 && meta.height === 1080) format = "landscape_1920x1080";
      else if (meta.width === 1080 && meta.height === 1920) format = "portrait_1080x1920";
      else {
        problems.push(
          `Image is ${meta.width}×${meta.height}. Screens need 1920×1080 (landscape) or 1080×1920 (portrait).`,
        );
      }
    } else {
      problems.push("Could not read image dimensions.");
    }
  }

  return {
    creative_id: id,
    ok: problems.length === 0,
    problems,
    format,
    duration_s: meta.duration_s,
  };
}

function complianceFor(verdict: ComplianceResult["verdict"]): ComplianceResult {
  if (verdict === "pass") return { verdict: "pass", reasons: [] };
  if (verdict === "fix_needed") {
    return {
      verdict: "fix_needed",
      reasons: [
        {
          rule: "creative_clarity",
          message: "Demo: the creative needs a clearer call to action before we can approve it.",
        },
      ],
    };
  }
  return {
    verdict: "human_review",
    reasons: [
      {
        rule: "manual_queue",
        message: "Demo: this campaign was sent to a human reviewer.",
      },
    ],
  };
}

function reportFor(campaign: Campaign): Report {
  const spent = campaign.spent;
  const plays = Math.max(0, Math.round(spent.micros / 1_000_000 / 0.4));
  const impressions = plays * 40;
  return {
    plays,
    impressions,
    spent,
    by_screen: campaign.screen_ids.map((screen_id, i) => ({
      screen_id,
      plays: Math.max(0, Math.floor(plays / campaign.screen_ids.length) + (i === 0 ? plays % campaign.screen_ids.length : 0)),
      impressions: Math.max(
        0,
        Math.floor(impressions / campaign.screen_ids.length) + (i === 0 ? impressions % campaign.screen_ids.length : 0),
      ),
    })),
    first_event_at: campaign.status === "draft" ? undefined : campaign.start,
    last_event_at: campaign.status === "live" || campaign.status === "finished" ? nowIso() : undefined,
  };
}

export function createMockClient(): ApiClient {
  let store = loadStore();

  const persist = () => {
    saveStore(store);
  };

  return {
    isMock: () => true,
    isCategoryRefused,
    categoryRefusalMessage,

    async signUp(input: SignUpInput) {
      store = loadStore();
      store.me = {
        id: uid("user"),
        email: input.email,
        account_type: input.account_type,
      };
      persist();
      return store.me;
    },

    async getMe() {
      store = loadStore();
      return store.me;
    },

    async updateProfile(input: ProfileInput) {
      store = loadStore();
      if (!store.me) throw new Error("Not signed in");
      store.me = {
        ...store.me,
        profile: {
          name: input.name,
          category: input.category,
          lat: input.lat,
          lng: input.lng,
          address: input.address,
        },
      };
      persist();
      return store.me;
    },

    async listCampaigns() {
      store = loadStore();
      return [...store.campaigns];
    },

    async getCampaign(id: string) {
      store = loadStore();
      const c = store.campaigns.find((x) => x.id === id);
      if (!c) throw new Error("Campaign not found");
      return c;
    },

    async getReport(id: string) {
      const c = await this.getCampaign(id);
      return reportFor(c);
    },

    async createCampaign(input: CreateCampaignInput) {
      store = loadStore();
      if (!store.me?.profile) throw new Error("Complete your profile first");
      if (isCategoryRefused(store.me.profile.category)) {
        throw new Error(categoryRefusalMessage(store.me.profile.category));
      }
      const campaign: Campaign = {
        id: uid("camp"),
        name: input.name,
        status: "draft",
        goal: input.goal,
        screen_ids: input.screen_ids,
        start: input.start,
        end: input.end,
        dayparts: input.dayparts,
        budget: input.budget,
        spent: money(0),
        creative_id: input.creative_id,
      };
      store.campaigns = [campaign, ...store.campaigns];
      persist();
      return campaign;
    },

    async submitCampaign(id: string, demoCompliance?: ComplianceResult["verdict"]) {
      store = loadStore();
      const idx = store.campaigns.findIndex((c) => c.id === id);
      if (idx < 0) throw new Error("Campaign not found");
      const verdict = demoCompliance ?? "pass";
      const compliance = complianceFor(verdict);
      const nextStatus: Campaign["status"] =
        verdict === "pass" ? "awaiting_media_owner" : verdict === "fix_needed" ? "draft" : "compliance_review";
      const updated: Campaign = {
        ...store.campaigns[idx],
        status: nextStatus,
        compliance,
      };
      store.campaigns = [...store.campaigns];
      store.campaigns[idx] = updated;
      // Pending Sam sign-off (D-014)
      if (verdict === "pass" && store.wallet.balance.micros >= updated.budget.micros) {
        store.wallet = {
          ...store.wallet,
          balance: {
            micros: store.wallet.balance.micros - Math.min(updated.budget.micros, store.wallet.balance.micros),
            currency: "EUR",
          },
        };
      }
      persist();
      return updated;
    },

    async listScreens(lat: number, lng: number, radius_m: number) {
      return DEMO_SCREENS.filter((s) => haversineM(lat, lng, s.lat, s.lng) <= radius_m);
    },

    async estimate(req: EstimateRequest): Promise<Estimate> {
      return buildEstimate(req);
    },

    async uploadCreative(meta: CreativeUploadMeta): Promise<CreativeCheck> {
      store = loadStore();
      const result = checkCreative(meta);
      if (result.ok) {
        store.creatives[result.creative_id] = { ...meta, id: result.creative_id };
        persist();
      }
      return result;
    },

    async getWallet() {
      store = loadStore();
      return store.wallet;
    },

    async topUp(amount: Money) {
      store = loadStore();
      if (!Number.isFinite(amount.micros) || amount.micros <= 0) {
        throw new Error("Top-up amount must be greater than zero.");
      }
      store.wallet = {
        balance: {
          micros: store.wallet.balance.micros + amount.micros,
          currency: "EUR",
        },
        invoices: [
          {
            id: uid("inv"),
            date: nowIso().slice(0, 10),
            amount,
            url: "#demo-invoice",
          },
          ...store.wallet.invoices,
        ],
      };
      persist();
      return store.wallet;
    },

    async sendAgentMessage(text: string) {
      store = loadStore();
      const userMsg: AgentMessage = { role: "user", text, created_at: nowIso() };
      const lower = text.toLowerCase();
      let reply =
        "I'm an AI assistant with demo replies only. Try asking about bidding, budgets, or nearby screens.";
      if (lower.includes("bid") || lower.includes("pay")) {
        reply =
          "You set a budget. Whenever one of your screens has a free slot, we bid for it automatically. You only pay when your ad actually plays, and never more than your budget. (AI demo reply)";
      } else if (lower.includes("budget")) {
        reply =
          "Start with what you can afford for the whole campaign. The estimate shows a range of plays and impressions — never a single promised number. (AI demo reply)";
      } else if (lower.includes("screen")) {
        reply =
          "On the map step, tap screens near your business to include them. Ten Dublin demo screens are available. (AI demo reply)";
      }
      const agentMsg: AgentMessage = { role: "agent", text: reply, created_at: nowIso() };
      store.messages = [...store.messages, userMsg, agentMsg];
      persist();
      return store.messages;
    },

    async getAgentMessages() {
      store = loadStore();
      return store.messages;
    },
  };
}

export { DEMO_SCREENS };
