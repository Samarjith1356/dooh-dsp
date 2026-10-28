"use client";

import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { PlanPreview } from "@/components/blocks/plan-preview";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useRole } from "@/lib/rbac";
import type { CampaignPlan } from "@/lib/types";
import { useWorkspace } from "@/lib/workspace";

export default function StudioPage() {
  const { advertiserId, campaignId, setCampaignId } = useWorkspace();
  const { canWrite } = useRole();
  const qc = useQueryClient();
  const [message, setMessage] = useState("Run a 2-week brand awareness campaign targeting commuters in Dublin");
  const [log, setLog] = useState<{ role: "user" | "agent"; text: string }[]>([]);
  const [draft, setDraft] = useState<CampaignPlan | null>(null);
  const campaigns = useQuery({ queryKey: ["campaigns", advertiserId], queryFn: () => api.campaigns(advertiserId) });
  const plans = useQuery({
    queryKey: ["plans", campaignId],
    queryFn: () => api.plans(campaignId!),
    enabled: Boolean(campaignId),
  });
  const latest = draft ?? plans.data?.[0] ?? null;

  const chat = useMutation({
    mutationFn: () => api.chat(advertiserId, campaignId, message),
    onSuccess: (res) => {
      setLog((prev) => [...prev, { role: "user", text: message }, { role: "agent", text: res.reply }]);
      if (res.plan && typeof res.plan === "object") {
        setDraft(res.plan as CampaignPlan);
      }
      void qc.invalidateQueries({ queryKey: ["plans"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const approve = useMutation({
    mutationFn: async () => {
      if (!campaignId || !latest?.id) {
        if (!campaignId || !draft) throw new Error("Select a campaign and generate a plan first");
        const created = await api.createPlan(campaignId, { ...draft, approved: false });
        await api.approvePlan(created.id);
        return;
      }
      await api.approvePlan(latest.id);
    },
    onSuccess: async () => {
      toast.success("Plan signed off");
      try {
        const snap = await api.compile();
        toast.success(`Brain snapshot ${snap.snapshot_id}`);
      } catch {
        toast.message("Plan approved; Brain compile skipped (CORS or Brain down)");
      }
      void qc.invalidateQueries({ queryKey: ["plans"] });
      void qc.invalidateQueries({ queryKey: ["campaigns"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const activeCampaign = useMemo(
    () => campaigns.data?.find((c) => c.id === campaignId) ?? campaigns.data?.[0],
    [campaigns.data, campaignId],
  );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canWrite) return;
    chat.mutate();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">AI agent studio</h1>
          <p className="text-sm text-muted-foreground">Human-in-the-loop: chat left, compiled plan right. Sign-off before Brain update.</p>
        </div>
        <select
          className="h-9 rounded-md border border-input bg-background px-2 text-sm"
          value={campaignId ?? activeCampaign?.id ?? ""}
          onChange={(e) => setCampaignId(Number(e.target.value))}
        >
          {(campaigns.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} · {c.state}
            </option>
          ))}
        </select>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="flex min-h-[520px] flex-col">
          <CardHeader>
            <CardTitle>Campaign manager</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col gap-3">
            <div className="min-h-0 flex-1 space-y-2 overflow-auto rounded-md border border-border bg-background p-3 text-sm">
              {log.length === 0 ? (
                <p className="text-muted-foreground">Ask for a Dublin commute burst or London roadside flight. Plans never execute on the bid path.</p>
              ) : (
                log.map((m, i) => (
                  <div key={i} className={m.role === "user" ? "text-foreground" : "text-muted-foreground"}>
                    <span className="text-[10px] uppercase">{m.role}</span>
                    <p>{m.text}</p>
                  </div>
                ))
              )}
            </div>
            <form onSubmit={onSubmit} className="space-y-2">
              <Textarea value={message} onChange={(e) => setMessage(e.target.value)} disabled={!canWrite} />
              <div className="flex gap-2">
                <Button type="submit" disabled={!canWrite || chat.isPending}>
                  {chat.isPending ? "Planning…" : "Send to agent"}
                </Button>
                <Button type="button" variant="outline" disabled={!canWrite || approve.isPending} onClick={() => approve.mutate()}>
                  Sign off & compile
                </Button>
              </div>
            </form>
            <Input readOnly value={activeCampaign ? `Campaign ${activeCampaign.id} · ${activeCampaign.state}` : "No campaign"} />
          </CardContent>
        </Card>
        <PlanPreview plan={latest} />
      </div>
    </div>
  );
}
