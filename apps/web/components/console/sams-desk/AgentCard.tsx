"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { AgentProfile, AgentStatus } from "@/lib/sams-desk";
import { relativeTime } from "@/lib/sams-desk";
import { AgentWorkFeed } from "./AgentWorkFeed";

const STATUS: Record<AgentStatus, string> = {
  IDLE: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  WORKING: "bg-amber-500/15 text-amber-200 border-amber-500/30",
  AUDITING: "bg-sky-500/15 text-sky-200 border-sky-500/30",
  "SELF-CORRECTING": "bg-violet-500/15 text-violet-200 border-violet-500/30",
  "ATTENTION REQUIRED": "bg-red-500/15 text-red-300 border-red-500/40",
};

export function AgentCard({
  agent,
  selected,
  onSelect,
  onChat,
}: {
  agent: AgentProfile;
  selected: boolean;
  onSelect: () => void;
  onChat: () => void;
}) {
  const pulse = agent.status === "WORKING" || agent.status === "AUDITING";
  return (
    <Card
      className={cn(
        "cursor-pointer border bg-[#161F30]/90 backdrop-blur-md transition hover:border-primary/40",
        selected && "ring-1 ring-primary",
      )}
      onClick={onSelect}
    >
      <CardContent className="space-y-2 p-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="text-sm font-semibold leading-tight">{agent.name}</div>
            <Badge className="mt-1">{agent.persona}</Badge>
          </div>
          <span
            className={cn("shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium", STATUS[agent.status])}
            title={agent.attention || agent.lastAction}
          >
            {pulse ? <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" /> : null}
            {agent.status}
          </span>
        </div>
        <p className="line-clamp-2 text-xs text-muted-foreground">{agent.focus}</p>
        {agent.job || agent.lastAction ? (
          <AgentWorkFeed job={agent.job ?? (agent.lastAction ? { id: "last", agent: agent.id, title: agent.lastAction, status: agent.status === "WORKING" ? "working" : "done", progress: agent.progress ?? 0 } : null)} compact />
        ) : null}
        {agent.lastActionAt && !agent.job ? (
          <p className="text-[11px] text-muted-foreground">{relativeTime(agent.lastActionAt)}</p>
        ) : null}
        <div className="flex justify-end">
          <Button
            size="sm"
            variant="outline"
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onChat();
            }}
          >
            Direct chat
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
