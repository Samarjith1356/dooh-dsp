"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { HealthStrip } from "@/components/blocks/health-strip";
import { KpiStrip } from "@/components/blocks/kpi-strip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useRole } from "@/lib/rbac";
import { formatMicros } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

export default function CommandCenterPage() {
  const { advertiserId, setCampaignId } = useWorkspace();
  const { canWrite, canSeeOps } = useRole();
  const qc = useQueryClient();
  const campaigns = useQuery({
    queryKey: ["campaigns", advertiserId],
    queryFn: () => api.campaigns(advertiserId),
    refetchInterval: 10000,
  });
  const kpis = useQuery({ queryKey: ["kpis", advertiserId], queryFn: () => api.kpis(advertiserId) });
  const compile = useMutation({
    mutationFn: api.compile,
    onSuccess: (d) => toast.success(`Snapshot ${d.snapshot_id} · ${d.campaigns} campaigns`),
    onError: (e: Error) => toast.error(e.message),
  });
  const stateMu = useMutation({
    mutationFn: ({ id, state }: { id: number; state: string }) => api.setState(id, state),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["campaigns"] });
      toast.success("Campaign state updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Global command center</h1>
        <p className="text-sm text-muted-foreground">
          Multi-brand GB/IE delivery. Billable impressions include OpenRTB qty.multiplier.
        </p>
      </div>
      <KpiStrip />
      {canSeeOps ? <HealthStrip /> : null}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Campaign fleet</CardTitle>
          {canWrite && canSeeOps ? (
            <Button size="sm" variant="outline" onClick={() => compile.mutate()}>
              Compile Brain snapshot
            </Button>
          ) : null}
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="py-2">Name</th>
                  <th>State</th>
                  <th>Cap</th>
                  <th>CPM</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(campaigns.data ?? []).map((c) => (
                  <tr key={c.id} className="border-t border-border">
                    <td className="py-2">
                      <Link href={`/campaigns/${c.id}`} className="hover:underline" onClick={() => setCampaignId(c.id)}>
                        {c.name}
                      </Link>
                    </td>
                    <td>
                      <Badge>{c.state}</Badge>
                    </td>
                    <td>{formatMicros(c.total_cap_micros, c.currency)}</td>
                    <td>{formatMicros(c.bid_cpm_micros, c.currency)}</td>
                    <td className="space-x-1 text-right">
                      <Button size="sm" variant="ghost" asChild>
                        <Link href={`/campaigns/${c.id}`} onClick={() => setCampaignId(c.id)}>
                          Focus
                        </Link>
                      </Button>
                      {canWrite ? (
                        <>
                          {c.state === "draft" ? (
                            <Button size="sm" variant="outline" onClick={() => stateMu.mutate({ id: c.id, state: "pending_approval" })}>
                              Submit
                            </Button>
                          ) : null}
                          {c.state === "pending_approval" || c.state === "paused" ? (
                            <Button size="sm" onClick={() => stateMu.mutate({ id: c.id, state: "active" })}>
                              Activate
                            </Button>
                          ) : null}
                          {c.state === "active" ? (
                            <Button size="sm" variant="secondary" onClick={() => stateMu.mutate({ id: c.id, state: "paused" })}>
                              Pause
                            </Button>
                          ) : null}
                        </>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(campaigns.data ?? []).length === 0 ? (
              <p className="py-6 text-sm text-muted-foreground">No campaigns for this brand.</p>
            ) : null}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            GB imps {kpis.data?.gb_imps ?? 0} · IE imps {kpis.data?.ie_imps ?? 0} (from recent event sample)
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
