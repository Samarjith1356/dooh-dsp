"use client";

import { cn } from "@/lib/utils";
import type { AgentJob } from "@/lib/sams-desk";

export function AgentWorkFeed({
  job,
  history,
  compact,
}: {
  job?: AgentJob | null;
  history?: AgentJob[];
  compact?: boolean;
}) {
  const pct = Math.max(0, Math.min(100, job?.progress ?? 0));
  const working = job && job.status === "working";
  if (!job && !(history && history.length)) return null;
  return (
    <div className={cn("space-y-2", compact ? "text-[11px]" : "text-xs")}>
      {job ? (
        <div>
          <div className="flex items-center justify-between gap-2">
            <p className="font-medium leading-snug">{working ? "Now" : "Last"}: {job.title}</p>
            <span className="shrink-0 text-muted-foreground">{working ? `${pct}%` : "done"}</span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full", working ? "bg-amber-400" : "bg-emerald-400")}
              style={{ width: `${working ? pct : 100}%` }}
            />
          </div>
          {!compact && job.steps?.length ? (
            <ul className="mt-2 space-y-0.5 text-muted-foreground">
              {job.steps.map((s) => (
                <li key={s.label}>
                  {s.done ? "✓" : "·"} {s.label}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {!compact && history && history.length ? (
        <div>
          <p className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">Job history</p>
          <ul className="space-y-1">
            {history.map((h) => (
              <li key={h.id} className="text-muted-foreground">
                {h.title} <span className="text-[10px]">({h.status})</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
