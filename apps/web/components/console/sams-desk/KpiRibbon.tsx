"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatMicros, formatNumber } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";
import { Skeleton } from "@/components/ui/skeleton";

export function KpiRibbon({ bidderLive }: { bidderLive: boolean }) {
  const { advertiserId } = useWorkspace();
  const kpis = useQuery({
    queryKey: ["kpis", advertiserId],
    queryFn: () => api.kpis(advertiserId),
    refetchInterval: 5000,
  });
  const campaigns = useQuery({
    queryKey: ["campaigns", advertiserId],
    queryFn: () => api.campaigns(advertiserId),
    refetchInterval: 10000,
  });
  const fleet = useQuery({ queryKey: ["fleet"], queryFn: api.fleet, refetchInterval: 5000 });
  const bidder = fleet.data?.services.find((s) => s.name === "bidder");
  const active = (campaigns.data ?? []).filter((c) => c.state === "active").length;
  const d = kpis.data;
  let bidderLabel = "down";
  if (bidder?.ok) {
    bidderLabel = `${bidder.latency_ms}ms RTT`;
    try {
      const parsed = JSON.parse(bidder.body || "{}") as { avg_decision_us?: number; bids?: number };
      if (typeof parsed.avg_decision_us === "number") {
        bidderLabel = `${parsed.avg_decision_us}µs avg decision`;
      }
    } catch {
      /* body is not JSON */
    }
  } else if (bidderLive) {
    bidderLabel = "orchestrator up, bidder body missing";
  }

  if (kpis.isLoading) return <Skeleton className="h-14" />;

  const cells = [
    { label: "Active campaigns", value: String(active) },
    { label: "Spend (ledger)", value: d ? formatMicros(d.spend_micros) : "—" },
    { label: "Billable imps (qty incl.)", value: d ? formatNumber(d.billable_imps, 1) : "—" },
    { label: "Avg shaded CPM", value: d ? `£${d.avg_cpm.toFixed(2)}` : "—" },
    { label: "Bids", value: d ? formatNumber(d.bids, 0) : "—" },
    { label: "Bidder X-DSP-Decision-Us", value: bidderLabel },
  ];

  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border md:grid-cols-6">
      {cells.map((c) => (
        <div key={c.label} className="bg-card/80 px-3 py-2 backdrop-blur-md">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{c.label}</div>
          <div className="mt-0.5 text-sm font-semibold tabular-nums">{c.value}</div>
        </div>
      ))}
    </div>
  );
}
