"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function HealthStrip() {
  const q = useQuery({ queryKey: ["fleet"], queryFn: api.fleet, refetchInterval: 8000 });
  if (q.isLoading) return <Skeleton className="h-24" />;
  if (q.isError) return <p className="text-sm text-destructive">Fleet health unavailable.</p>;
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {(q.data?.services ?? []).map((s) => (
        <Card key={s.name}>
          <CardHeader>
            <CardTitle>{s.name}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-baseline justify-between">
            <span className={cn("text-lg font-semibold", s.ok ? "text-emerald-400" : "text-destructive")}>
              {s.ok ? "Healthy" : "Down"}
            </span>
            <span className="text-xs text-muted-foreground">{s.latency_ms} ms</span>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
