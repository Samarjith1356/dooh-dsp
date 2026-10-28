"use client";

import { useEffect, useRef } from "react";
import type { Geofence, ScreenSpec } from "@/lib/types";

export function SpatialMap({ fences, specs, region }: { fences: Geofence[]; specs: ScreenSpec[]; region: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let map: import("leaflet").Map | undefined;
    const el = ref.current;
    if (!el) return;
    void import("leaflet").then((L) => {
      el.innerHTML = "";
      const filtered = fences.filter((f) => {
        if (region === "GB") return f.name.toLowerCase().includes("london");
        if (region === "IE") return f.name.toLowerCase().includes("dublin");
        return true;
      });
      map = L.map(el, { scrollWheelZoom: false }).setView([52.2, -2.2], 6);
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: "&copy; OpenStreetMap &copy; CARTO",
      }).addTo(map);
      filtered.forEach((f) => {
        const bounds: [[number, number], [number, number]] = [
          [f.min_lat, f.min_lon],
          [f.max_lat, f.max_lon],
        ];
        L.rectangle(bounds, { color: "#c4a35a", weight: 1, fillOpacity: 0.15 }).addTo(map!);
        L.marker([(f.min_lat + f.max_lat) / 2, (f.min_lon + f.max_lon) / 2])
          .addTo(map!)
          .bindPopup(
            `<strong>${f.name}</strong><br/>H3 cells: ${f.h3_cells.length}<br/>Specs in market: ${
              specs.filter((s) => (region === "ALL" ? true : s.country === region)).length
            }`,
          );
      });
      if (filtered[0]) {
        map.fitBounds([
          [filtered[0].min_lat, filtered[0].min_lon],
          [filtered[0].max_lat, filtered[0].max_lon],
        ]);
      }
      setTimeout(() => map?.invalidateSize(), 200);
    });
    return () => {
      map?.remove();
    };
  }, [fences, specs, region]);

  return <div ref={ref} className="h-[360px] w-full overflow-hidden rounded-md border border-border" />;
}
