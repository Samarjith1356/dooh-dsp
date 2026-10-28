"use client";

import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { EventRow } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

export function EventsTable({ rows }: { rows: EventRow[] }) {
  const parent = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parent.current,
    estimateSize: () => 36,
    overscan: 12,
  });
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No proof-of-play rows. Activate a campaign and let the simulator bid.</p>;
  }
  return (
    <div ref={parent} className="h-[420px] overflow-auto rounded-md border border-border">
      <div className="sticky top-0 z-10 grid grid-cols-8 bg-card px-3 py-2 text-[11px] uppercase text-muted-foreground">
        <span>Time</span>
        <span>Type</span>
        <span>Camp</span>
        <span>Country</span>
        <span>Venue</span>
        <span>CPM</span>
        <span>Qty</span>
        <span>Imps</span>
      </div>
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {virtualizer.getVirtualItems().map((item) => {
          const row = rows[item.index];
          return (
            <div
              key={item.key}
              className="absolute left-0 grid w-full grid-cols-8 border-t border-border px-3 py-2 text-xs tabular-nums"
              style={{ transform: `translateY(${item.start}px)` }}
            >
              <span>{String(row.event_time).slice(11, 19)}</span>
              <span>{row.event_type}</span>
              <span>{row.campaign_id}</span>
              <span>{row.country}</span>
              <span className="truncate">{row.venue_type}</span>
              <span>{formatNumber(row.price_cpm, 2)}</span>
              <span>{formatNumber(row.qty_multiplier, 1)}</span>
              <span>{formatNumber(row.billable_imps, 1)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
