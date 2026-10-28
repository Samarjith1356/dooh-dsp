"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { ApprovalItem } from "@/lib/sams-desk";

export function ApprovalQueue({
  items,
  live,
  busyId,
  onDecide,
}: {
  items: ApprovalItem[];
  live: boolean;
  busyId?: string | null;
  onDecide: (id: string, status: "approved" | "rejected", comment: string) => void;
}) {
  const [comment, setComment] = useState("");
  const pending = items.filter((i) => i.status === "pending");
  const done = items.filter((i) => i.status !== "pending").slice(0, 5);

  return (
    <Card className="border bg-[#161F30]/90 backdrop-blur-md">
      <CardHeader>
        <CardTitle>Executive approval queue</CardTitle>
        <p className="text-xs text-muted-foreground">
          {live ? "Live orchestrator :8091 — Approve mutates ClickHouse / caps / plans." : "Orchestrator unreachable. Queue is empty on purpose (not mocked)."}
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {pending.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            {live
              ? "Nothing waiting on Sam. Compiles still require campaign active + approved plan."
              : "Start the agents service to load live findings."}
          </p>
        ) : (
          pending.map((item) => (
            <div key={item.id} className="rounded-md border border-border p-3">
              <div className="text-sm font-medium">{item.title}</div>
              <p className="mt-1 text-xs text-muted-foreground">
                {item.agent} · {item.detail}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  disabled={!live || busyId === item.id}
                  onClick={() => {
                    onDecide(item.id, "approved", comment);
                  }}
                >
                  {busyId === item.id ? "Applying…" : "Approve"}
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={!live || busyId === item.id}
                  onClick={() => {
                    if (!comment.trim()) {
                      toast.error("Add a reject comment");
                      return;
                    }
                    onDecide(item.id, "rejected", comment);
                  }}
                >
                  Reject with comments
                </Button>
              </div>
            </div>
          ))
        )}
        <Textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Reject comments (required to reject)" rows={2} />
        {done.length ? (
          <div className="space-y-1 border-t border-border pt-2">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Executed</p>
            {done.map((item) => (
              <p key={item.id} className="text-[11px] text-muted-foreground">
                {item.status}: {item.title}
                {item.result ? ` — ${item.result}` : ""}
              </p>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
