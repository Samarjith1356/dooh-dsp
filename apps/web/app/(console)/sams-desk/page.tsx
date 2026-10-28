"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Command } from "lucide-react";
import { ActivityStream } from "@/components/console/sams-desk/ActivityStream";
import { AgentChatDrawer } from "@/components/console/sams-desk/AgentChatDrawer";
import { AgentGrid } from "@/components/console/sams-desk/AgentGrid";
import { ApprovalQueue } from "@/components/console/sams-desk/ApprovalQueue";
import { FleetStrip } from "@/components/console/sams-desk/FleetStrip";
import { MemoryStatePanel } from "@/components/console/sams-desk/MemoryState";
import { KpiRibbon } from "@/components/console/sams-desk/KpiRibbon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  WORKFORCE,
  decideApproval,
  dispatchAgent,
  fetchAgentHealth,
  fetchDesk,
  overlayWorkforce,
  type ActivityItem,
  type AgentId,
} from "@/lib/sams-desk";
import { cn } from "@/lib/utils";

const IDS = WORKFORCE.map((w) => w.id);

function SamsDeskInner() {
  const params = useSearchParams();
  const router = useRouter();
  const path = usePathname();
  const urlAgent = (IDS.includes(params.get("agent") as AgentId) ? params.get("agent") : "product") as AgentId;
  const [chatAgent, setChatAgent] = useState<AgentId | null>(null);
  const selected = chatAgent ?? urlAgent;
  const [palette, setPalette] = useState(false);
  const [broadcast, setBroadcast] = useState(false);
  const [broadcastText, setBroadcastText] = useState("");
  const [localFeed, setLocalFeed] = useState<ActivityItem[]>([]);
  const [chatOpen, setChatOpen] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const health = useQuery({
    queryKey: ["agents-health"],
    queryFn: fetchAgentHealth,
    refetchInterval: 4000,
    retry: false,
  });
  const desk = useQuery({
    queryKey: ["sams-desk"],
    queryFn: fetchDesk,
    refetchInterval: 4000,
    retry: false,
  });
  const live = Boolean(health.data?.live);
  const online = live ? (health.data?.agents?.length ?? 7) : 0;
  const agents = useMemo(() => overlayWorkforce(desk.data?.agents), [desk.data]);
  const agent = useMemo(() => agents.find((w) => w.id === selected) ?? agents[6], [agents, selected]);
  const approvals = desk.data?.approvals ?? [];
  const feed = useMemo(() => [...localFeed, ...(desk.data?.feed ?? [])], [desk.data?.feed, localFeed]);

  const select = useCallback(
    (id: AgentId) => {
      router.replace(`${path}?agent=${id}`);
    },
    [path, router],
  );

  const openChat = useCallback(
    (id: AgentId) => {
      setChatAgent(id);
      setChatOpen(true);
      select(id);
    },
    [select],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPalette((v) => !v);
      }
      if (e.key === "Escape") {
        setPalette(false);
        setBroadcast(false);
        setChatOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function pushFeed(text: string, from: AgentId | "orchestrator" = "orchestrator") {
    setLocalFeed((prev) => [
      {
        id: `live-${Date.now()}`,
        at: new Date().toISOString(),
        from,
        to: "*",
        severity: "info",
        topic: "desk",
        text,
      },
      ...prev,
    ]);
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-[#161F30]/80 px-4 py-3 backdrop-blur-md">
        <div>
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.25em] text-muted-foreground">
            <span className={cn("h-2 w-2 rounded-full", live ? "animate-pulse bg-emerald-400" : "bg-amber-400")} />
            Sam&apos;s Desk
          </div>
          <h1 className="text-lg font-semibold">Executive agent command center</h1>
          <p className="text-xs text-muted-foreground">
            {live ? `${online} control-plane agents on :8091` : "orchestrator :8091 unreachable"}
            {health.data?.llm
              ? ` · LLM ${health.data.llm.configured ? `${health.data.llm.provider}/${health.data.llm.model}` : "not configured"}`
              : ""}
          </p>
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={!live} onClick={() => setBroadcast(true)}>
            Broadcast
          </Button>
          <Button size="sm" variant="outline" onClick={() => setPalette(true)}>
            <Command className="h-3.5 w-3.5" />
            Jump
          </Button>
        </div>
      </header>

      <FleetStrip services={health.data?.fleet?.services ?? []} redisOk={health.data?.fleet?.redis_ok} />

      <MemoryStatePanel memory={desk.data?.memory ?? health.data?.memory} />

      <KpiRibbon bidderLive={Boolean(health.data?.fleet?.services?.find((s) => s.name === "bidder")?.ok)} />

      <AgentGrid agents={agents} selected={selected} onSelect={select} onChat={openChat} />

      {chatOpen ? (
        <>
          <button
            type="button"
            aria-label="Dismiss chat overlay"
            className="fixed inset-0 z-30 bg-black/40 md:left-[240px]"
            onClick={() => setChatOpen(false)}
          />
          <AgentChatDrawer
            agent={agent}
            live={live}
            onClose={() => setChatOpen(false)}
            onLog={(t) => pushFeed(t, selected)}
          />
        </>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {feed.length ? <ActivityStream items={feed} /> : (
          <p className="text-xs text-muted-foreground">No Redis bus events yet (health ticks are hidden).</p>
        )}
        <ApprovalQueue
          items={approvals}
          live={live}
          busyId={busyId}
          onDecide={async (id, status, comment) => {
            setBusyId(id);
            try {
              const item = await decideApproval(id, status, comment);
              toast.success(status === "approved" ? `Applied: ${item.result || item.title}` : `Rejected: ${item.title}`);
              pushFeed(`${status} ${item.title}${item.result ? `: ${item.result}` : ""}`, "orchestrator");
              await desk.refetch();
            } catch (e) {
              toast.error(e instanceof Error ? e.message : "decision failed");
            } finally {
              setBusyId(null);
            }
          }}
        />
      </div>

      {palette ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-24" onClick={() => setPalette(false)}>
          <div className="w-full max-w-lg rounded-lg border border-border bg-card p-3" onClick={(e) => e.stopPropagation()}>
            <p className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Open Direct chat</p>
            {WORKFORCE.map((w) => (
              <button
                key={w.id}
                className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm hover:bg-muted"
                onClick={() => {
                  openChat(w.id);
                  setPalette(false);
                }}
              >
                {w.name}
                <Badge>{w.persona}</Badge>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {broadcast ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setBroadcast(false)}>
          <div className="w-full max-w-md rounded-lg border border-border bg-card p-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-sm font-semibold">Broadcast to all seven agents</h2>
            <Textarea className="mt-2" value={broadcastText} onChange={(e) => setBroadcastText(e.target.value)} />
            <div className="mt-3 flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setBroadcast(false)}>
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={async () => {
                  try {
                    if (live) await dispatchAgent("*", broadcastText);
                    pushFeed(`BROADCAST: ${broadcastText}`);
                    toast.success("Broadcast dispatched");
                    setBroadcast(false);
                  } catch (e) {
                    toast.error(e instanceof Error ? e.message : "broadcast failed");
                  }
                }}
              >
                Send
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function SamsDeskPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      <SamsDeskInner />
    </Suspense>
  );
}
