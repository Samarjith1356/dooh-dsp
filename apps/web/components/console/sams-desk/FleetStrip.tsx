"use client";

import { cn } from "@/lib/utils";

type Svc = { name: string; ok: boolean; latency_ms?: number; body?: string; error?: string | null };

function bidderUs(body?: string): string | null {
  if (!body) return null;
  try {
    const parsed = JSON.parse(body) as { avg_decision_us?: number; bids?: number };
    if (typeof parsed.avg_decision_us === "number") {
      return `${parsed.avg_decision_us}µs avg` + (parsed.bids != null ? ` · ${parsed.bids} bids` : "");
    }
  } catch {
    return null;
  }
  return null;
}

export function FleetStrip({
  services,
  redisOk,
}: {
  services: Svc[];
  redisOk?: boolean;
}) {
  const rows: Svc[] = [...services];
  if (redisOk !== undefined && !rows.some((s) => s.name === "redis")) {
    rows.push({ name: "redis", ok: redisOk, latency_ms: 0 });
  }
  if (!rows.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {rows.map((s) => (
        <div
          key={s.name}
          className={cn(
            "rounded-md border px-2 py-1 text-[11px]",
            s.ok ? "border-emerald-500/30 text-emerald-200" : "border-red-500/40 text-red-200",
          )}
          title={s.error || s.body || ""}
        >
          <span className="font-medium">{s.name}</span>
          <span className="text-muted-foreground">
            {" "}
            {s.ok ? "up" : "down"}
            {s.name === "bidder" && s.ok && bidderUs(s.body) ? ` · ${bidderUs(s.body)}` : s.latency_ms ? ` · ${s.latency_ms}ms RTT` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}
