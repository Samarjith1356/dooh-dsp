"use client";

import { useEffect, useRef } from "react";
import type { Screen } from "@/lib/api";

type Props = {
  screens: Screen[];
  selectedIds: string[];
  center: { lat: number; lng: number };
  onToggle?: (id: string) => void;
  interactive?: boolean;
};

export function ScreenMap({ screens, selectedIds, center, onToggle, interactive = true }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const selectedKey = selectedIds.slice().sort().join(",");

  useEffect(() => {
    let map: import("leaflet").Map | undefined;
    const el = ref.current;
    if (!el) return;

    void import("leaflet").then((L) => {
      el.innerHTML = "";
      map = L.map(el, { scrollWheelZoom: false }).setView([center.lat, center.lng], 13);
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: "&copy; OpenStreetMap &copy; CARTO",
      }).addTo(map);

      L.circleMarker([center.lat, center.lng], {
        radius: 8,
        color: "#c4a35a",
        fillColor: "#c4a35a",
        fillOpacity: 0.9,
      })
        .addTo(map)
        .bindPopup("Your business");

      screens.forEach((s) => {
        const selected = selectedIds.includes(s.id);
        const marker = L.circleMarker([s.lat, s.lng], {
          radius: selected ? 10 : 7,
          color: selected ? "#7dd3a7" : "#8a93a5",
          fillColor: selected ? "#7dd3a7" : "#3a4150",
          fillOpacity: 0.9,
          weight: 2,
        }).addTo(map!);
        marker.bindPopup(`<strong>${s.name}</strong><br/>${s.venue_type} · ${s.format}`);
        if (interactive && onToggle) {
          marker.on("click", () => onToggle(s.id));
        }
      });

      if (screens.length) {
        const bounds = L.latLngBounds([
          [center.lat, center.lng],
          ...screens.map((s) => [s.lat, s.lng] as [number, number]),
        ]);
        map.fitBounds(bounds.pad(0.2));
      }
      setTimeout(() => map?.invalidateSize(), 200);
    });

    return () => {
      map?.remove();
    };
    // selectedKey stands in for selectedIds content
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screens, selectedKey, center.lat, center.lng, interactive]);

  return (
    <div
      ref={ref}
      data-testid="screen-map"
      className="h-[280px] w-full overflow-hidden rounded-md border border-border sm:h-[360px]"
    />
  );
}
