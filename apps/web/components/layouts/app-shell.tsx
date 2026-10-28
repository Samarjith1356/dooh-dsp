"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Bot, LayoutDashboard, MapPinned, Moon, Sun, Armchair } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRole } from "@/lib/rbac";
import type { Role } from "@/lib/types";
import { useWorkspace, type Region } from "@/lib/workspace";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

const NAV = [
  { href: "/", label: "Command Center", icon: LayoutDashboard },
  { href: "/inventory", label: "Inventory", icon: MapPinned },
  { href: "/studio", label: "Agent Studio", icon: Bot },
  { href: "/analytics", label: "Ledger", icon: BarChart3 },
  { href: "/sams-desk", label: "Sam's Desk", icon: Armchair },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { role, setRole } = useRole();
  const { advertiserId, setAdvertiserId, region, setRegion } = useWorkspace();
  const [light, setLight] = useState(false);
  const advertisers = useQuery({ queryKey: ["advertisers"], queryFn: api.advertisers });

  useEffect(() => {
    document.documentElement.classList.toggle("theme-light", light);
  }, [light]);

  return (
    <div className="grid min-h-screen grid-cols-[240px_1fr]">
      <aside className="flex flex-col border-r border-border bg-card">
        <div className="px-4 py-4">
          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">DOOH DSP</div>
          <div className="mt-1 text-sm font-semibold">UK & Ireland Control</div>
        </div>
        <Separator />
        <nav className="flex flex-1 flex-col gap-1 p-2">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active =
              item.href === "/"
                ? path === "/" || path.startsWith("/campaigns")
                : path === item.href || path.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm",
                  active ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 text-[11px] text-muted-foreground">JCDecaux / VIOOH-shaped · OpenRTB 2.6</div>
      </aside>
      <div className="flex min-w-0 flex-col">
        <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2">
          <select
            className="h-8 rounded-md border border-input bg-background px-2 text-sm"
            value={advertiserId}
            onChange={(e) => setAdvertiserId(Number(e.target.value))}
          >
            {(advertisers.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.company}
              </option>
            ))}
          </select>
          <select
            className="h-8 rounded-md border border-input bg-background px-2 text-sm"
            value={region}
            onChange={(e) => setRegion(e.target.value as Region)}
          >
            <option value="ALL">GB + IE</option>
            <option value="GB">Great Britain</option>
            <option value="IE">Ireland</option>
          </select>
          <select
            className="h-8 rounded-md border border-input bg-background px-2 text-sm"
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
          >
            <option value="org_admin">Org Admin</option>
            <option value="campaign_manager">Campaign Manager</option>
            <option value="client_viewer">Client Viewer</option>
            <option value="auditor">Auditor</option>
          </select>
          <Badge>Workspace</Badge>
          <div className="ml-auto flex items-center gap-2">
            <Button size="sm" variant="ghost" onClick={() => setLight((v) => !v)} aria-label="Toggle theme">
              {light ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            </Button>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-auto p-4">{children}</main>
      </div>
    </div>
  );
}
