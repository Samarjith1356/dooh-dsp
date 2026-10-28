"use client";

import { AgentCard } from "./AgentCard";
import type { AgentId, AgentProfile } from "@/lib/sams-desk";

export function AgentGrid({
  agents,
  selected,
  onSelect,
  onChat,
}: {
  agents: AgentProfile[];
  selected: AgentId;
  onSelect: (id: AgentId) => void;
  onChat: (id: AgentId) => void;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {agents.map((agent) => (
        <AgentCard
          key={agent.id}
          agent={agent}
          selected={selected === agent.id}
          onSelect={() => onSelect(agent.id)}
          onChat={() => onChat(agent.id)}
        />
      ))}
    </div>
  );
}
