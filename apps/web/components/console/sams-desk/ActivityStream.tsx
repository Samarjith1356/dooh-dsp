"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ActivityItem, AgentId } from "@/lib/sams-desk";
import { relativeTime } from "@/lib/sams-desk";

const SEV: Record<ActivityItem["severity"], string> = {
  info: "text-sky-300",
  warning: "text-amber-300",
  critical: "text-red-300",
};

export function ActivityStream({ items }: { items: ActivityItem[] }) {
  const [agent, setAgent] = useState<AgentId | "all">("all");
  const [sev, setSev] = useState<ActivityItem["severity"] | "all">("all");
  const rows = useMemo(
    () =>
      items.filter((i) => (agent === "all" || i.from === agent || i.to === agent) && (sev === "all" || i.severity === sev)),
    [items, agent, sev],
  );

  return (
    <Card className="border bg-[#161F30]/90 backdrop-blur-md">
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle>Autonomous operations feed</CardTitle>
        <div className="flex gap-2">
          <select className="h-8 rounded-md border border-input bg-background px-2 text-xs" value={agent} onChange={(e) => setAgent(e.target.value as AgentId | "all")}>
            <option value="all">All agents</option>
            {["architect", "compliance", "devops", "analytics", "frontend", "qa", "product"].map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
          <select className="h-8 rounded-md border border-input bg-background px-2 text-xs" value={sev} onChange={(e) => setSev(e.target.value as ActivityItem["severity"] | "all")}>
            <option value="all">All severity</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="critical">Critical</option>
          </select>
        </div>
      </CardHeader>
      <CardContent>
        <div className="max-h-56 space-y-2 overflow-auto pr-1">
          {rows.length === 0 ? (
            <p className="text-xs text-muted-foreground">No bus messages in this filter.</p>
          ) : (
            rows.map((row) => (
              <div key={row.id} className="border-b border-border/60 pb-2 text-xs last:border-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge>{row.topic}</Badge>
                  <span className={SEV[row.severity]}>{row.severity}</span>
                  <span className="text-muted-foreground">{relativeTime(row.at)}</span>
                </div>
                <p className="mt-1">
                  <span className="font-medium">{row.from}</span>
                  <span className="text-muted-foreground"> → {row.to}: </span>
                  {row.text}
                </p>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
