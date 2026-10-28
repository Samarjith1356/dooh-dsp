export type AgentId =
  | "architect"
  | "compliance"
  | "devops"
  | "analytics"
  | "frontend"
  | "qa"
  | "product";

export type AgentStatus = "IDLE" | "WORKING" | "AUDITING" | "SELF-CORRECTING" | "ATTENTION REQUIRED";

export type JobStep = { label: string; done: boolean };

export type AgentJob = {
  id: string;
  agent: string;
  title: string;
  status: string;
  progress: number;
  steps?: JobStep[];
  started_at?: string;
  updated_at?: string;
  summary?: string;
};

export type ChatMsg = { id?: string; role: "sam" | "agent" | "system"; text: string; at?: string; job_id?: string };

export type AgentThread = {
  agent: AgentId;
  messages: ChatMsg[];
  current: AgentJob | null;
  history: AgentJob[];
  status: AgentStatus | string;
};

export type AgentProfile = {
  id: AgentId;
  name: string;
  persona: string;
  focus: string;
  lastAction: string;
  lastActionAt: string;
  status: AgentStatus;
  prompts: string[];
  /** Shown on the card when status is ATTENTION REQUIRED */
  attention?: string;
  progress?: number;
  job?: AgentJob | null;
  recent_jobs?: AgentJob[];
};

export type ActivityItem = {
  id: string;
  at: string;
  from: AgentId | "orchestrator";
  to: AgentId | "*";
  severity: "info" | "warning" | "critical";
  topic: string;
  text: string;
};

export type ApprovalItem = {
  id: string;
  agent: AgentId;
  title: string;
  detail: string;
  createdAt: string;
  status: "pending" | "approved" | "rejected";
  action?: string;
  result?: string;
  comment?: string;
};

export type MemoryState = {
  ok?: boolean;
  chunks?: number;
  by_kind?: Record<string, number>;
  latest?: { kind?: string; title?: string; source?: string; created_at?: string; body?: string } | null;
  learning?: {
    tracking?: boolean;
    architecture_rules?: number;
    campaign_events?: number;
    audits?: number;
    decisions?: number;
    compiles?: number;
    sources?: string[];
  };
};

export type DeskSnapshot = {
  live: boolean;
  approvals: ApprovalItem[];
  feed: ActivityItem[];
  memory?: MemoryState | null;
  agents: {
    id: AgentId;
    status: AgentStatus;
    lastAction: string;
    lastActionAt: string;
    attention?: string;
    progress?: number;
    job?: AgentJob | null;
    recent_jobs?: AgentJob[];
  }[];
};

export const WORKFORCE: AgentProfile[] = [
  {
    id: "architect",
    name: "Chief Software Architect",
    persona: "SYSTEM ARCHITECT",
    focus: "Bid-path isolation · OpenRTB contracts · sub-1ms decision budget",
    lastAction: "",
    lastActionAt: "",
    status: "IDLE",
    prompts: ["Explain recent daypart change", "Review Redis snapshot contract", "Run bid-path latency budget check"],
  },
  {
    id: "compliance",
    name: "AdTech Compliance",
    persona: "ASA/CAP GUARD",
    focus: "CAP/ASAI gates before Brain compile",
    lastAction: "",
    lastActionAt: "",
    status: "IDLE",
    prompts: ["Audit ASA compliance", "Screen this Dublin commute plan", "List QA rejection vectors"],
  },
  {
    id: "devops",
    name: "DevOps & Infrastructure",
    persona: "SRE",
    focus: "Zero-trust ACLs · Redis snapshot sync · ingest pipeline",
    lastAction: "",
    lastActionAt: "",
    status: "IDLE",
    prompts: ["Run full system diagnostic", "Show chaos playbook", "Propose production ClickHouse ACL"],
  },
  {
    id: "analytics",
    name: "Data & Analytics",
    persona: "OLAP & PACING",
    focus: "Hourly MV · qty.multiplier imps · remaining micros",
    lastAction: "",
    lastActionAt: "",
    status: "IDLE",
    prompts: ["Summarise today’s burn", "Check paced-out campaigns", "Explain qty.multiplier in KPIs"],
  },
  {
    id: "frontend",
    name: "Frontend & Enterprise UX",
    persona: "CONTROL CENTER",
    focus: "Four pillars · HITL Studio · honest client RBAC",
    lastAction: "",
    lastActionAt: "",
    status: "IDLE",
    prompts: ["Audit Sam’s Desk empty states", "List TypeScript pin risk", "Check Ledger skeletons"],
  },
  {
    id: "qa",
    name: "QA & Testing",
    persona: "ZERO-ERROR GUARDIAN",
    focus: "Golden rule · nbr:2 · state machine · OpenRTB vectors",
    lastAction: "",
    lastActionAt: "",
    status: "IDLE",
    prompts: ["Run QA suite", "Show OpenRTB no-bid vectors", "Confirm site/app yields nbr 2"],
  },
  {
    id: "product",
    name: "Product & Orchestrator",
    persona: "LEAD DEPUTY",
    focus: "Client goals → PlanIn JSON · approval gates",
    lastAction: "",
    lastActionAt: "",
    status: "IDLE",
    prompts: ["Parse a 2-week Dublin commute flight", "How is the demo campaign?", "Draft London roadside plan"],
  },
];

const AGENTS = "/api/agents-proxy";

export function overlayWorkforce(liveAgents: DeskSnapshot["agents"] | undefined): AgentProfile[] {
  const map = new Map((liveAgents ?? []).map((a) => [a.id, a]));
  return WORKFORCE.map((w) => {
    const row = map.get(w.id);
    if (!row) {
      return { ...w, status: "IDLE", lastAction: "", lastActionAt: "", attention: undefined };
    }
    const statuses: AgentStatus[] = ["IDLE", "WORKING", "AUDITING", "SELF-CORRECTING", "ATTENTION REQUIRED"];
    return {
      ...w,
      status: statuses.includes(row.status) ? row.status : "IDLE",
      lastAction: row.lastAction || w.lastAction,
      lastActionAt: row.lastActionAt,
      attention: row.attention || undefined,
      progress: row.progress ?? 0,
      job: row.job ?? null,
      recent_jobs: row.recent_jobs ?? [],
    };
  });
}

export async function fetchAgentHealth(): Promise<{
  ok: boolean;
  agents?: string[];
  live: boolean;
  fleet?: { ok: boolean; redis_ok?: boolean; services: { name: string; ok: boolean; latency_ms: number; body?: string }[] };
  llm?: { configured: boolean; provider: string; model: string };
  memory?: MemoryState | null;
}> {
  try {
    const res = await fetch(`${AGENTS}/health`, { cache: "no-store" });
    if (!res.ok) return { ok: false, live: false };
    const body = await res.json();
    return { ok: Boolean(body.ok), agents: body.agents, live: true, fleet: body.fleet, llm: body.llm, memory: body.memory };
  } catch {
    return { ok: false, live: false };
  }
}

export async function fetchDesk(): Promise<DeskSnapshot | null> {
  try {
    const res = await fetch(`${AGENTS}/v1/desk`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as DeskSnapshot;
  } catch {
    return null;
  }
}

export async function decideApproval(id: string, status: "approved" | "rejected", comment: string) {
  const res = await fetch(`${AGENTS}/v1/desk/approvals/${id}/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, comment }),
  });
  if (!res.ok) {
    throw new Error((await res.text()) || `decide ${res.status}`);
  }
  return res.json() as Promise<ApprovalItem>;
}

export async function fetchAgentThread(agent: AgentId): Promise<AgentThread | null> {
  try {
    const res = await fetch(`${AGENTS}/v1/desk/agents/${agent}/thread`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as AgentThread;
  } catch {
    return null;
  }
}

export async function dispatchAgent(
  agent: AgentId | "*",
  objective: string,
  history: { role: string; text: string }[] = [],
) {
  const res = await fetch(`${AGENTS}/v1/agents/dispatch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      objective,
      reply_to: agent === "*" ? "all" : agent,
      context: { agent: agent === "*" ? "all" : agent, history },
    }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `dispatch ${res.status}`);
  }
  return res.json() as Promise<{ ok: boolean; agent?: string; result?: { summary: string; actions?: string[] } }>;
}

export function relativeTime(iso: string) {
  const delta = Date.now() - new Date(iso).getTime();
  const m = Math.max(0, Math.round(delta / 60000));
  if (m < 1) return "just now";
  if (m === 1) return "1 min ago";
  if (m < 60) return `${m} mins ago`;
  const h = Math.round(m / 60);
  return h === 1 ? "1 hr ago" : `${h} hrs ago`;
}
