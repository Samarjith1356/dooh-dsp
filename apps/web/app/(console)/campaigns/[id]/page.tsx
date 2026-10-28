"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { EventsTable } from "@/components/blocks/events-table";
import { SpendChart } from "@/components/blocks/spend-chart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useRole } from "@/lib/rbac";
import { formatMicros, formatNumber } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function assetSrc(uri: string) {
  if (uri.startsWith("http://") || uri.startsWith("https://")) return uri;
  return `${API}${uri.startsWith("/") ? uri : `/${uri}`}`;
}

function fmtWhen(iso?: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("en-GB");
}

export default function CampaignPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const { setCampaignId, setAdvertiserId } = useWorkspace();
  const { canWrite } = useRole();
  const qc = useQueryClient();

  const campaign = useQuery({
    queryKey: ["campaign", id],
    queryFn: () => api.campaign(id),
    enabled: Number.isFinite(id),
    refetchInterval: 8000,
  });
  const camp = campaign.data;

  useEffect(() => {
    if (Number.isFinite(id)) setCampaignId(id);
    if (camp?.advertiser_id) setAdvertiserId(camp.advertiser_id);
  }, [id, camp?.advertiser_id, setCampaignId, setAdvertiserId]);

  const plans = useQuery({
    queryKey: ["plans", id],
    queryFn: () => api.plans(id),
    enabled: Number.isFinite(id),
  });
  const creatives = useQuery({
    queryKey: ["creatives", camp?.advertiser_id],
    queryFn: () => api.creatives(camp!.advertiser_id),
    enabled: Boolean(camp?.advertiser_id),
  });
  const fences = useQuery({
    queryKey: ["geofences", camp?.advertiser_id],
    queryFn: () => api.geofences(camp!.advertiser_id),
    enabled: Boolean(camp?.advertiser_id),
  });
  const kpis = useQuery({
    queryKey: ["kpis", camp?.advertiser_id, id],
    queryFn: () => api.kpis(camp!.advertiser_id, id),
    enabled: Boolean(camp?.advertiser_id),
    refetchInterval: 8000,
  });
  const hourly = useQuery({
    queryKey: ["hourly", camp?.advertiser_id, id],
    queryFn: () => api.hourly(camp!.advertiser_id, id),
    enabled: Boolean(camp?.advertiser_id),
    refetchInterval: 10000,
  });
  const events = useQuery({
    queryKey: ["events", camp?.advertiser_id, id],
    queryFn: () => api.events(camp!.advertiser_id, 200, id),
    enabled: Boolean(camp?.advertiser_id),
    refetchInterval: 10000,
  });

  const stateMu = useMutation({
    mutationFn: (state: string) => api.setState(id, state),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["campaign", id] });
      void qc.invalidateQueries({ queryKey: ["campaigns"] });
      toast.success("Campaign state updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!Number.isFinite(id)) {
    return <p className="text-sm text-muted-foreground">Invalid campaign id.</p>;
  }
  if (campaign.isError) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-red-300">Campaign #{id} was not found on campaign-api.</p>
        <Link href="/" className="text-sm underline">
          Back to command center
        </Link>
      </div>
    );
  }
  if (campaign.isLoading || !camp) {
    return <Skeleton className="h-96" />;
  }

  const linkedCreatives = (creatives.data ?? []).filter((c) => camp.creative_ids.includes(c.id));
  const linkedFences = (fences.data ?? []).filter((g) => camp.geofence_ids.includes(g.id));
  const remaining = camp.remaining_micros;
  const d = kpis.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/" className="text-xs text-muted-foreground hover:underline">
            ← Command center
          </Link>
          <h1 className="mt-1 text-xl font-semibold">{camp.name}</h1>
          <p className="text-sm text-muted-foreground">
            Campaign #{camp.id} · advertiser {camp.advertiser_id} · Brain compiles only when state is active
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{camp.state}</Badge>
          {canWrite && camp.state === "draft" ? (
            <Button size="sm" variant="outline" onClick={() => stateMu.mutate("pending_approval")}>
              Submit
            </Button>
          ) : null}
          {canWrite && (camp.state === "pending_approval" || camp.state === "paused") ? (
            <Button size="sm" onClick={() => stateMu.mutate("active")}>
              Activate
            </Button>
          ) : null}
          {canWrite && camp.state === "active" ? (
            <Button size="sm" variant="secondary" onClick={() => stateMu.mutate("paused")}>
              Pause
            </Button>
          ) : null}
          <Button size="sm" variant="outline" asChild>
            <Link href="/studio">Open in Studio</Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-px overflow-hidden rounded-lg border border-border bg-border md:grid-cols-4">
        <Metric label="Total cap" value={formatMicros(camp.total_cap_micros, camp.currency)} />
        <Metric
          label="Remaining (Redis)"
          value={remaining == null ? "no key" : formatMicros(remaining, camp.currency)}
        />
        <Metric label="Bid CPM" value={formatMicros(camp.bid_cpm_micros, camp.currency)} />
        <Metric label="Daily cap" value={formatMicros(camp.daily_cap_micros, camp.currency)} />
        <Metric label="Spend (ledger)" value={d ? formatMicros(d.spend_micros, camp.currency) : "—"} />
        <Metric label="Billable imps" value={d ? formatNumber(d.billable_imps, 1) : "—"} />
        <Metric label="Bids" value={d ? formatNumber(d.bids, 0) : "—"} />
        <Metric label="Avg CPM" value={d ? `£${d.avg_cpm.toFixed(2)}` : "—"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Setup</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row k="Priority" v={String(camp.priority ?? "—")} />
            <Row k="Currency" v={camp.currency} />
            <Row k="Flight start" v={fmtWhen(camp.flight_start)} />
            <Row k="Flight end" v={fmtWhen(camp.flight_end)} />
            <Row k="Creative ids" v={camp.creative_ids.join(", ") || "none"} />
            <Row k="Geofence ids" v={camp.geofence_ids.join(", ") || "none"} />
            <p className="pt-2 text-xs text-muted-foreground">
              GB {formatNumber(d?.gb_imps ?? 0)} · IE {formatNumber(d?.ie_imps ?? 0)} on this campaign’s event sample.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Geofences</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {linkedFences.length === 0 ? (
              <p className="text-muted-foreground">No geofences linked (bbox will be empty at compile).</p>
            ) : (
              linkedFences.map((g) => (
                <div key={g.id} className="rounded-md border border-border p-2">
                  <div className="font-medium">
                    #{g.id} {g.name}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {g.min_lat.toFixed(4)},{g.min_lon.toFixed(4)} → {g.max_lat.toFixed(4)},{g.max_lon.toFixed(4)} ·{" "}
                    {g.h3_cells?.length ?? 0} H3 cells
                  </p>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Creatives</CardTitle>
        </CardHeader>
        <CardContent>
          {linkedCreatives.length === 0 ? (
            <p className="text-sm text-muted-foreground">No creatives attached.</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {linkedCreatives.map((cr) => (
                <div key={cr.id} className="rounded-md border border-border p-2 text-xs">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={assetSrc(cr.asset_uri)}
                    alt={cr.filename}
                    className="mb-2 h-28 w-full rounded object-cover bg-muted"
                  />
                  <div className="font-medium">
                    #{cr.id} {cr.filename}
                  </div>
                  <p className="text-muted-foreground">
                    {cr.width}×{cr.height} · {cr.mime} · {cr.validation_status}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Plans</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {(plans.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No PlanIn rows. Create one in Agent Studio.</p>
          ) : (
            (plans.data ?? []).map((p) => (
              <div key={p.id ?? p.created_at} className="rounded-md border border-border p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">Plan #{p.id}</span>
                  <Badge>{p.approved ? "approved" : "unapproved"}</Badge>
                  <span className="text-xs text-muted-foreground">{fmtWhen(p.created_at)}</span>
                </div>
                {p.goal ? <p className="mt-1 text-muted-foreground">{p.goal}</p> : null}
                <p className="mt-2 text-xs">
                  Countries: {(p.countries ?? []).join(", ") || "—"} · Venues: {(p.venue_allowlist ?? []).join(", ") || "—"} ·
                  Shade {p.shade_factor} · Bid {formatMicros(p.bid_cpm_micros || 0, camp.currency)}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Dayparts (Go Sunday=0):{" "}
                  {(p.dayparts ?? []).length
                    ? p.dayparts.map((b) => `${DOW[b.dow] ?? b.dow} h${(b.hours ?? []).join("/")}`).join(" · ")
                    : "all hours (empty = always on)"}
                </p>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Delivery (this campaign)</CardTitle>
        </CardHeader>
        <CardContent>
          {hourly.isLoading ? <Skeleton className="h-64" /> : <SpendChart rows={hourly.data ?? []} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent events</CardTitle>
        </CardHeader>
        <CardContent>
          {events.isLoading ? <Skeleton className="h-48" /> : <EventsTable rows={events.data ?? []} />}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-card px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-border/60 py-1 last:border-0">
      <span className="text-muted-foreground">{k}</span>
      <span className="tabular-nums">{v}</span>
    </div>
  );
}
