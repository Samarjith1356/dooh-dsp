"use client";

import type { CampaignPlan } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMicros } from "@/lib/utils";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function PlanPreview({ plan }: { plan: CampaignPlan | null }) {
  if (!plan) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle>Structured plan</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">No draft plan yet. Ask the agent for a commute or roadside burst.</CardContent>
      </Card>
    );
  }
  const hours = new Set<number>();
  (plan.dayparts ?? []).forEach((d) => d.hours.forEach((h) => hours.add(h)));
  return (
    <Card className="h-full">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Structured plan</CardTitle>
        <Badge className={plan.approved ? "border-emerald-700 text-emerald-400" : "border-amber-700 text-amber-400"}>
          {plan.approved ? "Approved" : "Needs sign-off"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-muted-foreground">{plan.goal || "Untitled goal"}</p>
        <div>
          <div className="mb-1 text-xs uppercase text-muted-foreground">Markets</div>
          <div className="flex gap-1">{(plan.countries ?? []).map((c) => <Badge key={c}>{c}</Badge>)}</div>
        </div>
        <div>
          <div className="mb-1 text-xs uppercase text-muted-foreground">Venues</div>
          <div className="flex flex-wrap gap-1">{(plan.venue_allowlist ?? []).map((v) => <Badge key={v}>{v}</Badge>)}</div>
        </div>
        <div>
          <div className="mb-1 text-xs uppercase text-muted-foreground">Bid / shade</div>
          {formatMicros(plan.bid_cpm_micros)} CPM · shade {plan.shade_factor}
        </div>
        <div>
          <div className="mb-1 text-xs uppercase text-muted-foreground">Daypart bitmask (168h)</div>
          <div className="grid grid-cols-8 gap-px text-[10px]">
            <span />
            {Array.from({ length: 7 }).map((_, i) => (
              <span key={i} className="text-muted-foreground">{DOW[i]}</span>
            ))}
            {Array.from({ length: 24 }).map((_, hour) => (
              <div key={hour} className="contents">
                <span className="text-muted-foreground">{hour}</span>
                {Array.from({ length: 7 }).map((_, dow) => {
                  const on = (plan.dayparts ?? []).some((d) => d.dow === dow && d.hours.includes(hour));
                  const allOn = (plan.dayparts ?? []).length === 0;
                  return (
                    <span
                      key={`${dow}-${hour}`}
                      className={on || allOn ? "bg-primary/70" : "bg-muted"}
                      title={`${DOW[dow]} ${hour}:00`}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
