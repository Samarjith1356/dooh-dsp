"use client";

import { relativeTime, type MemoryState as MemoryStateT } from "@/lib/sams-desk";

export function MemoryStatePanel({ memory }: { memory?: MemoryStateT | null }) {
  if (!memory) {
    return (
      <div className="rounded-lg border border-border bg-[#161F30]/80 px-4 py-3 text-xs text-muted-foreground">
        Brain memory unreachable — compile still runs; Desk cannot show learning metrics.
      </div>
    );
  }
  const learn = memory.learning ?? {};
  const cells = [
    ["chunks", String(memory.chunks ?? 0)],
    ["architecture", String(learn.architecture_rules ?? 0)],
    ["campaigns", String(learn.campaign_events ?? 0)],
    ["audits", String(learn.audits ?? 0)],
    ["decisions", String(learn.decisions ?? 0)],
    ["compiles", String(learn.compiles ?? 0)],
  ];
  const latest = memory.latest;
  return (
    <section className="rounded-lg border border-emerald-500/25 bg-[#161F30]/80 px-4 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold">Brain memory state</h2>
        <span className="text-[11px] uppercase tracking-wide text-emerald-300">
          {learn.tracking ? "tracking operations" : "idle"}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {cells.map(([label, value]) => (
          <div key={label} className="rounded-md border border-border px-2 py-1 text-[11px]">
            <span className="text-muted-foreground">{label} </span>
            <span className="font-medium">{value}</span>
          </div>
        ))}
      </div>
      {latest ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Latest [{latest.kind}] {latest.title}
          {latest.created_at ? ` · ${relativeTime(latest.created_at)}` : ""}
          {latest.source ? ` · ${latest.source}` : ""}
        </p>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">No chunks yet — architecture seed runs on Brain startup.</p>
      )}
    </section>
  );
}
