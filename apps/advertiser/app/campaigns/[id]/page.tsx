"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Campaign, Report, Screen } from "@/lib/api";
import { useApi } from "@/lib/providers";
import { formatMicros, formatNumber } from "@/lib/utils";

const ScreenMap = dynamic(() => import("@/components/blocks/screen-map").then((m) => m.ScreenMap), {
  ssr: false,
  loading: () => <div className="h-[280px] animate-pulse rounded-md bg-muted" />,
});

const TIMELINE: { key: Campaign["status"] | "submitted_gate"; label: string }[] = [
  { key: "submitted", label: "Submitted" },
  { key: "compliance_review", label: "Compliance" },
  { key: "awaiting_media_owner", label: "Media-owner approval" },
  { key: "live", label: "Live" },
  { key: "finished", label: "Finished" },
];

function statusRank(status: Campaign["status"]) {
  const order: Campaign["status"][] = [
    "draft",
    "submitted",
    "compliance_review",
    "awaiting_media_owner",
    "live",
    "paused",
    "finished",
    "rejected",
  ];
  return order.indexOf(status);
}

export default function CampaignPage() {
  const params = useParams<{ id: string }>();
  const { api, me, loading } = useApi();
  const router = useRouter();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [screens, setScreens] = useState<Screen[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (loading) return;
    if (!me) router.replace("/signup");
  }, [loading, me, router]);

  useEffect(() => {
    if (!api || !params.id) return;
    void (async () => {
      try {
        const c = await api.getCampaign(params.id);
        setCampaign(c);
        setReport(await api.getReport(params.id));
        const lat = me?.profile?.lat ?? 53.3498;
        const lng = me?.profile?.lng ?? -6.2603;
        const all = await api.listScreens(lat, lng, 20000);
        setScreens(all.filter((s) => c.screen_ids.includes(s.id)));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Not found");
      }
    })();
  }, [api, params.id, me]);

  const center = useMemo(
    () => ({
      lat: me?.profile?.lat ?? screens[0]?.lat ?? 53.3498,
      lng: me?.profile?.lng ?? screens[0]?.lng ?? -6.2603,
    }),
    [me, screens],
  );

  if (error) {
    return (
      <AppShell title="Campaign">
        <p className="text-sm text-destructive">{error}</p>
        <Button asChild variant="outline" className="mt-3">
          <Link href="/home">Back to Home</Link>
        </Button>
      </AppShell>
    );
  }

  if (!campaign) {
    return (
      <AppShell title="Campaign">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </AppShell>
    );
  }

  const rank = statusRank(campaign.status);

  return (
    <AppShell title={campaign.name}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge data-testid="campaign-status">{campaign.status.replaceAll("_", " ")}</Badge>
          <span className="text-xs text-muted-foreground">Demo campaign</span>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Status timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="flex flex-col gap-2" data-testid="status-timeline">
              {TIMELINE.map((item) => {
                const itemRank = statusRank(item.key === "submitted_gate" ? "submitted" : item.key);
                const reached =
                  campaign.status === "rejected"
                    ? false
                    : rank >= itemRank || (campaign.status === "paused" && item.key === "live");
                const current = campaign.status === item.key;
                return (
                  <li
                    key={item.label}
                    className={`flex items-center gap-2 text-sm ${reached ? "text-foreground" : "text-muted-foreground"}`}
                  >
                    <span
                      className={`inline-block h-2.5 w-2.5 rounded-full ${current ? "bg-primary" : reached ? "bg-emerald-400" : "bg-muted"}`}
                    />
                    {item.label}
                  </li>
                );
              })}
            </ol>
            {campaign.compliance ? (
              <div className="mt-3 rounded-md border border-border p-3 text-sm" data-testid="compliance-result">
                <p>
                  Compliance: <strong>{campaign.compliance.verdict.replaceAll("_", " ")}</strong>
                </p>
                {campaign.compliance.reasons.map((r) => (
                  <p key={r.rule} className="text-muted-foreground">
                    {r.message}
                  </p>
                ))}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Results (demo)</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <p className="text-muted-foreground">Plays</p>
              <p className="text-lg font-semibold">{report ? formatNumber(report.plays) : "—"}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Impressions</p>
              <p className="text-lg font-semibold">{report ? formatNumber(report.impressions) : "—"}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Spent</p>
              <p className="text-lg font-semibold">{formatMicros(campaign.spent.micros)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Budget</p>
              <p className="text-lg font-semibold">{formatMicros(campaign.budget.micros)}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Screens played</CardTitle>
          </CardHeader>
          <CardContent>
            <ScreenMap screens={screens} selectedIds={campaign.screen_ids} center={center} interactive={false} />
          </CardContent>
        </Card>

        <Button asChild variant="outline">
          <Link href="/home">Back to Home</Link>
        </Button>
      </div>
    </AppShell>
  );
}
