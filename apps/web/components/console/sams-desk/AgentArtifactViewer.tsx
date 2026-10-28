"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AgentId } from "@/lib/sams-desk";
import { useWorkspace } from "@/lib/workspace";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMicros, formatNumber } from "@/lib/utils";

export function AgentArtifactViewer({ agent }: { agent: AgentId }) {
  const { advertiserId } = useWorkspace();
  const kpis = useQuery({ queryKey: ["kpis", advertiserId], queryFn: () => api.kpis(advertiserId), refetchInterval: 5000 });
  const fleet = useQuery({ queryKey: ["fleet"], queryFn: api.fleet, refetchInterval: 4000 });
  const campaigns = useQuery({
    queryKey: ["campaigns", advertiserId],
    queryFn: () => api.campaigns(advertiserId),
    refetchInterval: 10000,
  });

  const showFleet = agent === "architect" || agent === "devops";
  const showKpis = agent === "analytics";
  const showCampaigns = agent === "product";

  return (
    <Card className="h-full min-h-[280px] border bg-[#161F30]/90 backdrop-blur-md">
      <CardHeader>
        <CardTitle>Live reads · {agent}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {showFleet ? (
          fleet.isLoading ? (
            <Skeleton className="h-16" />
          ) : (
            <FleetLines fleet={fleet.data} />
          )
        ) : null}
        {showKpis ? (
          kpis.isLoading ? (
            <Skeleton className="h-24" />
          ) : kpis.data ? (
            <div className="space-y-1 text-xs">
              <p>Billable imps (qty included): {formatNumber(kpis.data.billable_imps)}</p>
              <p>Spend: {formatMicros(kpis.data.spend_micros)} · CPM £{kpis.data.avg_cpm.toFixed(2)}</p>
              <p>GB {formatNumber(kpis.data.gb_imps)} · IE {formatNumber(kpis.data.ie_imps)}</p>
              <p>Bids {formatNumber(kpis.data.bids, 0)}</p>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">KPI endpoint returned nothing.</p>
          )
        ) : null}
        {showCampaigns ? (
          campaigns.isLoading ? (
            <Skeleton className="h-24" />
          ) : (
            <div className="space-y-1 text-xs">
              {(campaigns.data ?? []).map((c) => (
                <p key={c.id}>
                  #{c.id} {c.name} · {c.state} · cap {formatMicros(c.total_cap_micros, c.currency)}
                </p>
              ))}
            </div>
          )
        ) : null}
        {!showFleet && !showKpis && !showCampaigns ? (
          <p className="text-xs text-muted-foreground">
            No live artifact feed for this agent. Use Direct chat to dispatch :8091.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function FleetLines({ fleet }: { fleet: { services: { name: string; ok: boolean; latency_ms: number; body?: string }[] } | undefined }) {
  if (!fleet) return <p className="text-xs text-muted-foreground">GET /v1/ops/health failed.</p>;
  return (
    <div className="font-mono text-xs">
      {fleet.services.map((s) => (
        <p key={s.name}>
          {s.name}: {s.ok ? "up" : "down"} · {s.latency_ms}ms RTT
          {s.name === "bidder" && s.body ? ` · ${s.body.slice(0, 160)}` : ""}
        </p>
      ))}
    </div>
  );
}
