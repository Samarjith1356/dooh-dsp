"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { AgentMessage } from "@/lib/api";
import { useApi } from "@/lib/providers";

export default function AssistantPage() {
  const { api, me, loading } = useApi();
  const router = useRouter();
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!me) router.replace("/signup");
  }, [loading, me, router]);

  useEffect(() => {
    if (!api) return;
    void api.getAgentMessages().then(setMessages);
  }, [api]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!api || !text.trim()) return;
    setBusy(true);
    try {
      setMessages(await api.sendAgentMessage(text.trim()));
      setText("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title="Assistant">
      <Card>
        <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
          <CardTitle>Chat</CardTitle>
          <Badge data-testid="ai-label">AI</Badge>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-xs text-muted-foreground">
            This is an AI assistant with demo replies only. It cannot spend money or change live campaigns.
          </p>
          <ul className="flex max-h-[420px] flex-col gap-2 overflow-y-auto" data-testid="agent-messages">
            {messages.map((m, i) => (
              <li
                key={`${m.created_at}-${i}`}
                className={`rounded-md px-3 py-2 text-sm ${m.role === "agent" ? "bg-muted" : "border border-border"}`}
              >
                <p className="mb-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                  {m.role === "agent" ? "Agent (AI)" : "You"}
                </p>
                {m.text}
              </li>
            ))}
          </ul>
          <form className="flex flex-col gap-2" onSubmit={send}>
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Ask about bidding, budgets, or screens…"
              data-testid="agent-input"
            />
            <Button type="submit" disabled={busy || !text.trim()} data-testid="agent-send">
              {busy ? "Sending…" : "Send"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </AppShell>
  );
}
