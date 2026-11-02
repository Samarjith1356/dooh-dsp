"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Campaign, Wallet } from "@/lib/api";
import { useApi } from "@/lib/providers";
import { formatMicros } from "@/lib/utils";

export default function HomePage() {
  const { api, me, loading } = useApi();
  const router = useRouter();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [blocked, setBlocked] = useState("");

  useEffect(() => {
    if (loading) return;
    if (!me) {
      router.replace("/signup");
      return;
    }
    if (!me.profile) {
      router.replace("/profile");
      return;
    }
  }, [loading, me, router]);

  useEffect(() => {
    if (!api || !me?.profile) return;
    void (async () => {
      setCampaigns(await api.listCampaigns());
      setWallet(await api.getWallet());
      if (api.isCategoryRefused(me.profile!.category)) {
        setBlocked(api.categoryRefusalMessage(me.profile!.category));
      }
    })();
  }, [api, me]);

  return (
    <AppShell title="Home">
      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Wallet</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between gap-3">
            <div>
              <p className="text-2xl font-semibold" data-testid="wallet-balance">
                {wallet ? formatMicros(wallet.balance.micros) : "—"}
              </p>
              <p className="text-xs text-muted-foreground">Demo balance</p>
            </div>
            <Button asChild variant="outline">
              <Link href="/wallet">Open wallet</Link>
            </Button>
          </CardContent>
        </Card>

        {blocked ? (
          <div role="alert" data-testid="home-category-block" className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm">
            {blocked}
            <p className="mt-1 text-muted-foreground">Campaign creation is blocked for this account.</p>
          </div>
        ) : (
          <Button asChild data-testid="new-campaign">
            <Link href="/campaigns/new">New campaign</Link>
          </Button>
        )}

        <section aria-labelledby="campaigns-heading">
          <div className="mb-2 flex items-center justify-between">
            <h2 id="campaigns-heading" className="text-sm font-semibold text-muted-foreground">
              Campaigns
            </h2>
            <Badge>Demo list</Badge>
          </div>
          <ul className="flex flex-col gap-2" data-testid="campaign-list">
            {campaigns.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/campaigns/${c.id}`}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card p-3 hover:bg-muted/40"
                  data-testid={`campaign-${c.id}`}
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium">{c.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatMicros(c.spent.micros)} spent of {formatMicros(c.budget.micros)} · demo
                    </p>
                  </div>
                  <Badge data-testid={`status-${c.id}`}>{c.status.replaceAll("_", " ")}</Badge>
                </Link>
              </li>
            ))}
            {campaigns.length === 0 ? (
              <li className="text-sm text-muted-foreground">No campaigns yet.</li>
            ) : null}
          </ul>
        </section>

        <div className="flex flex-wrap gap-2 text-sm">
          <Link className="text-primary underline-offset-2 hover:underline" href="/assistant">
            Ask the Assistant (AI)
          </Link>
          <Link className="text-primary underline-offset-2 hover:underline" href="/profile">
            Edit profile
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
