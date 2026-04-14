import { useEffect, useRef } from "react";

import maplibregl from "maplibre-gl";
import { PMTiles, Protocol } from "pmtiles";

import type { Lead } from "../api/client";

type Props = {
  routeGeoJson: GeoJSON.LineString | null;
  leads: Lead[];
  onSelectLead: (lead: Lead) => void;
};

const protocol = new Protocol();
// Safe to register once for the app lifecycle.
maplibregl.addProtocol("pmtiles", protocol.tile);

export function MapPanel({ routeGeoJson, leads, onSelectLead }: Props) {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const leadsRef = useRef<Lead[]>([]);

  leadsRef.current = leads;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const pmtilesUrl = import.meta.env.VITE_MAP_PMTILES_URL as string;
    if (pmtilesUrl) {
      const p = new PMTiles(pmtilesUrl);
      protocol.add(p);
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {},
        layers: [{ id: "background", type: "background", paint: { "background-color": "#f1f5f9" } }],
      },
      center: [-87.65, 41.88],
      zoom: 10,
    });

    mapRef.current = map;

    map.on("load", () => {
      map.addSource("route", {
        type: "geojson",
        data: { type: "Feature", geometry: { type: "LineString", coordinates: [] }, properties: {} },
      });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        paint: { "line-color": "#2563eb", "line-width": 4 },
      });

      map.addSource("leads", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "lead-points",
        type: "circle",
        source: "leads",
        paint: {
          "circle-color": "#ef4444",
          "circle-radius": 5,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#fff",
        },
      });

      map.on("click", "lead-points", (e) => {
        const feature = e.features?.[0];
        if (!feature) return;
        const businessId = feature.properties?.business_id as string | undefined;
        const found = leadsRef.current.find((l) => l.business_id === businessId);
        if (found) onSelectLead(found);
      });

      map.on("mouseenter", "lead-points", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "lead-points", () => (map.getCanvas().style.cursor = ""));
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [onSelectLead]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const routeSource = map.getSource("route") as maplibregl.GeoJSONSource | undefined;
    if (routeSource) {
      routeSource.setData({
        type: "Feature",
        geometry: routeGeoJson ?? { type: "LineString", coordinates: [] },
        properties: {},
      });
    }

    const leadSource = map.getSource("leads") as maplibregl.GeoJSONSource | undefined;
    if (leadSource) {
      leadSource.setData({
        type: "FeatureCollection",
        features: leads
          .filter((l) => typeof l.lng === "number" && typeof l.lat === "number")
          .map((l) => ({
            type: "Feature",
            geometry: { type: "Point", coordinates: [l.lng as number, l.lat as number] },
            properties: { business_id: l.business_id, name: l.name },
          })),
      });
    }
  }, [routeGeoJson, leads]);

  return <div className="map-panel" ref={containerRef} />;
}
