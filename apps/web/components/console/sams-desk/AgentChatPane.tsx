"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AgentWorkFeed } from "./AgentWorkFeed";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { dispatchAgent, fetchAgentThread, type AgentProfile, type ChatMsg } from "@/lib/sams-desk";

export function AgentChatPane({
  agent,
  live,
  onLog,
}: {
  agent: AgentProfile;
  live: boolean;
  onLog: (text: string) => void;
}) {
  const qc = useQueryClient();
  const thread = useQuery({
    queryKey: ["agent-thread", agent.id],
    queryFn: () => fetchAgentThread(agent.id),
    refetchInterval: 2500,
    retry: false,
  });
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<ChatMsg[]>([]);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scroller = useRef<HTMLDivElement>(null);

  const serverMsgs = thread.data?.messages ?? [];
  const history = useMemo(() => {
    const ids = new Set(serverMsgs.map((m) => m.text + (m.role || "")));
    const extra = pending.filter((m) => !ids.has(m.text + (m.role || "")));
    return [...serverMsgs, ...extra];
  }, [serverMsgs, pending]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [agent.id]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight });
  }, [history.length, busy]);

  async function send(objective: string) {
    if (!objective.trim()) return;
    if (!live) {
      toast.error("Orchestrator :8091 is down — not sending a fake reply.");
      return;
    }
    setBusy(true);
    setPending((p) => [...p, { role: "sam", text: objective }]);
    try {
      const prior = history.map((m) => ({ role: m.role, text: m.text }));
      const res = await dispatchAgent(agent.id, objective, prior);
      const summary = res.result?.summary || JSON.stringify(res).slice(0, 400);
      setPending((p) => [...p, { role: "agent", text: summary }]);
      onLog(`${agent.id}: ${summary.slice(0, 160)}`);
      await qc.invalidateQueries({ queryKey: ["agent-thread", agent.id] });
      await qc.invalidateQueries({ queryKey: ["sams-desk"] });
      setPending([]);
    } catch (e) {
      const err = e instanceof Error ? e.message : "dispatch failed";
      toast.error(err);
      setPending((p) => [...p, { role: "agent", text: `Error: ${err}` }]);
    } finally {
      setBusy(false);
      setText("");
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(text);
  }

  const job = thread.data?.current ?? agent.job;
  const past = thread.data?.history ?? agent.recent_jobs ?? [];

  return (
    <div className="flex h-full min-h-[420px] flex-col rounded-lg border border-border bg-[#161F30]/90 backdrop-blur-md">
      <div className="border-b border-border px-3 py-2">
        <div className="text-sm font-semibold">{agent.name}</div>
        <p className="text-[11px] text-muted-foreground">{agent.focus}</p>
        <Badge className="mt-1">{agent.persona}</Badge>
        <div className="mt-2">
          <AgentWorkFeed job={job} history={past} />
        </div>
        {live ? null : <p className="mt-1 text-[11px] text-amber-200">Offline — chat disabled until :8091 is up.</p>}
      </div>
      <div ref={scroller} className="min-h-0 flex-1 space-y-2 overflow-auto p-3 text-sm">
        {history.length === 0 ? (
          <p className="text-xs text-muted-foreground">No thread yet. This pane reloads from Redis — closing it will not wipe the job.</p>
        ) : (
          history.map((m, i) => (
            <div key={m.id || `${m.role}-${i}`} className={m.role === "sam" ? "text-right" : ""}>
              <div
                className={
                  m.role === "sam"
                    ? "ml-auto max-w-[90%] rounded-md bg-primary/15 px-2 py-1.5 text-left"
                    : "max-w-[90%] rounded-md bg-muted px-2 py-1.5"
                }
              >
                {m.text}
              </div>
            </div>
          ))
        )}
        {busy ? <p className="animate-pulse text-xs text-amber-200">Agent working… progress stays on the card if you close this.</p> : null}
      </div>
      <div className="flex flex-wrap gap-1 border-t border-border px-3 py-2">
        {agent.prompts.map((p) => (
          <Button key={p} size="sm" variant="ghost" type="button" onClick={() => void send(p)}>
            {p}
          </Button>
        ))}
        <Button size="sm" variant="outline" type="button" disabled={!live || busy} onClick={() => void send("done")}>
          Mark idle
        </Button>
      </div>
      <form onSubmit={onSubmit} className="border-t border-border p-3">
        <Textarea
          ref={inputRef}
          id="sams-desk-chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          placeholder={`Directive for ${agent.name} — reopen later; this thread is saved`}
        />
        <div className="mt-2 flex justify-end">
          <Button type="submit" size="sm" disabled={busy || !live}>
            Send
          </Button>
        </div>
      </form>
    </div>
  );
}
