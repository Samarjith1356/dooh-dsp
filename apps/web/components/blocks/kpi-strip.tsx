"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { formatMicros, formatNumber } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function KpiStrip() {
  const { advertiserId } = useWorkspace();
  const q = useQuery({ queryKey: ["kpis", advertiserId], queryFn: () => api.kpis(advertiserId), refetchInterval: 10000 });
  if (q.isLoading) {
    return (
      <div className="grid gap-3 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }
  const k = q.data;
  const items = [
    { label: "Billable imps (qty)", value: formatNumber(k?.billable_imps ?? 0) },
    { label: "Spend", value: formatMicros(k?.spend_micros ?? 0) },
    { label: "Avg CPM", value: formatMicros((k?.avg_cpm ?? 0) * 1_000_000) },
    { label: "Bids / hours", value: `${formatNumber(k?.bids ?? 0, 0)} / ${k?.hours ?? 0}` },
  ];
  return (
    <div className="grid gap-3 md:grid-cols-4">
      {items.map((item) => (
        <Card key={item.label}>
          <CardHeader>
            <CardTitle>{item.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold tabular-nums">{item.value}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
