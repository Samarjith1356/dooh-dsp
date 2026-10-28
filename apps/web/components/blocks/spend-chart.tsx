"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HourlyRow } from "@/lib/types";

export function SpendChart({ rows }: { rows: HourlyRow[] }) {
  const data = [...rows]
    .filter((r) => r.event_type === "bid")
    .reverse()
    .map((r) => ({
      hour: String(r.hour).slice(11, 16) || String(r.hour),
      spend: Number(r.spend_micros) / 1_000_000,
      imps: Number(r.imps),
    }));
  if (data.length === 0) {
    return <p className="text-sm text-muted-foreground">No hourly ClickHouse rollups yet.</p>;
  }
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(222 12% 22%)" />
          <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Area type="monotone" dataKey="spend" stroke="#c4a35a" fill="#c4a35a33" name="Spend" />
          <Area type="monotone" dataKey="imps" stroke="#6ee7b7" fill="#6ee7b722" name="Imps" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
