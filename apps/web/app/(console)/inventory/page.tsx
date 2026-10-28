"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SpatialMap } from "@/components/blocks/spatial-map";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import type { ScreenSpec } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

export default function InventoryPage() {
  const { advertiserId, region } = useWorkspace();
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<ScreenSpec | null>(null);
  const specs = useQuery({ queryKey: ["specs"], queryFn: api.specs });
  const fences = useQuery({
    queryKey: ["geofences", advertiserId],
    queryFn: () => api.geofences(advertiserId),
  });
  const filtered = useMemo(() => {
    return (specs.data ?? []).filter((s) => {
      if (region !== "ALL" && s.country !== region) return false;
      const hay = `${s.publisher} ${s.format_code} ${s.venue_types.join(" ")}`.toLowerCase();
      return hay.includes(q.toLowerCase());
    });
  }, [specs.data, region, q]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Spatial & inventory explorer</h1>
        <p className="text-sm text-muted-foreground">JCDecaux and VIOOH-shaped physical screens, H3 geofences for London and Dublin.</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Geofences</CardTitle>
          </CardHeader>
          <CardContent>
            {fences.isLoading || specs.isLoading ? (
              <Skeleton className="h-[360px]" />
            ) : (
              <SpatialMap fences={fences.data ?? []} specs={specs.data ?? []} region={region} />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Asset inspector</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {selected ? (
              <dl className="space-y-2">
                <div>
                  <dt className="text-xs uppercase text-muted-foreground">Format</dt>
                  <dd>
                    {selected.publisher} {selected.format_code}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-muted-foreground">Pixels</dt>
                  <dd>
                    {selected.width}×{selected.height} ({selected.aspect})
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-muted-foreground">Max payload</dt>
                  <dd>{formatNumber(selected.max_bytes / 1_000_000, 1)} MB</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-muted-foreground">Venues</dt>
                  <dd className="flex flex-wrap gap-1">
                    {selected.venue_types.map((v) => (
                      <Badge key={v}>{v}</Badge>
                    ))}
                  </dd>
                </div>
                <p className="text-muted-foreground">
                  Audience multiplier (`qty.multiplier`) arrives on each OpenRTB bid request, not on the static spec.
                </p>
              </dl>
            ) : (
              <p className="text-muted-foreground">Select a row to inspect physical constraints.</p>
            )}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader className="flex-row items-center justify-between gap-3">
          <CardTitle>Screen catalog</CardTitle>
          <Input className="max-w-xs" placeholder="Filter publisher, format, venue" value={q} onChange={(e) => setQ(e.target.value)} />
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="py-2">Publisher</th>
                <th>Format</th>
                <th>Market</th>
                <th>Size</th>
                <th>Venues</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr
                  key={s.id}
                  className="cursor-pointer border-t border-border hover:bg-muted/40"
                  onClick={() => setSelected(s)}
                >
                  <td className="py-2">{s.publisher}</td>
                  <td>{s.format_code}</td>
                  <td>{s.country}</td>
                  <td>
                    {s.width}×{s.height}
                  </td>
                  <td className="truncate">{s.venue_types.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 ? <p className="py-6 text-sm text-muted-foreground">No screens match this region/filter.</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}
