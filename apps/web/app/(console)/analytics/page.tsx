"use client";

import { useQuery } from "@tanstack/react-query";
import { EventsTable } from "@/components/blocks/events-table";
import { SpendChart } from "@/components/blocks/spend-chart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";

export default function AnalyticsPage() {
  const { advertiserId } = useWorkspace();
  const hourly = useQuery({
    queryKey: ["hourly", advertiserId],
    queryFn: () => api.hourly(advertiserId),
    refetchInterval: 10000,
  });
  const events = useQuery({
    queryKey: ["events", advertiserId],
    queryFn: () => api.events(advertiserId, 250),
    refetchInterval: 10000,
  });
  const insights = useQuery({
    queryKey: ["insights", advertiserId],
    queryFn: () => api.insights(advertiserId),
    refetchInterval: 15000,
  });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Financial ledger</h1>
        <p className="text-sm text-muted-foreground">ClickHouse hourly rollups and recent proof-of-play (qty.multiplier already in billable imps).</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Spend & impression velocity</CardTitle>
          </CardHeader>
          <CardContent>{hourly.isLoading ? <Skeleton className="h-64" /> : <SpendChart rows={hourly.data ?? []} />}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>AI insight stream</CardTitle>
          </CardHeader>
          <CardContent className="text-sm leading-relaxed text-muted-foreground">
            {insights.isLoading ? <Skeleton className="h-24" /> : insights.data?.live || "No insight yet."}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Proof-of-play explorer</CardTitle>
        </CardHeader>
        <CardContent>
          {events.isLoading ? <Skeleton className="h-[420px]" /> : <EventsTable rows={events.data ?? []} />}
        </CardContent>
      </Card>
    </div>
  );
}
