"use client";

import { X } from "lucide-react";
import { AgentChatPane } from "./AgentChatPane";
import { Button } from "@/components/ui/button";
import type { AgentProfile } from "@/lib/sams-desk";

export function AgentChatDrawer({
  agent,
  live,
  onClose,
  onLog,
}: {
  agent: AgentProfile;
  live: boolean;
  onClose: () => void;
  onLog: (text: string) => void;
}) {
  return (
    <div
      className="fixed inset-y-0 left-0 z-40 flex w-full max-w-[420px] flex-col border-r border-border bg-[#0B1220] shadow-2xl md:left-[240px]"
      role="dialog"
      aria-label={`Direct chat with ${agent.name}`}
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div>
          <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Direct chat</p>
          <p className="text-sm font-semibold">{agent.name}</p>
        </div>
        <Button type="button" size="sm" variant="ghost" onClick={onClose} aria-label="Close chat">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden p-2">
        <AgentChatPane key={agent.id} agent={agent} live={live} onLog={onLog} />
      </div>
    </div>
  );
}
