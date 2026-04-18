import { useEffect, useRef, useState } from "react";

import maplibregl from "maplibre-gl";
import { PMTiles, Protocol } from "pmtiles";

import type { Lead } from "../api/client";

type Props = {
  routeGeoJson: GeoJSON.LineString | null;
  leads: Lead[];
  selectedLead: { business_id: string; lat?: number | null; lng?: number | null } | null;
  onSelectLead: (lead: Lead) => void;
};

const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

// OSM-style basemap via a simple raster fallback (used when no PMTiles URL is set)
const RASTER_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
      maxzoom: 19,
    },
  },
  layers: [{ id: "osm-tiles", type: "raster", source: "osm" }],
};

export function MapPanel({ routeGeoJson, leads, selectedLead, onSelectLead }: Props) {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const leadsRef = useRef<Lead[]>([]);
  const onSelectLeadRef = useRef(onSelectLead);
  const [styleLoaded, setStyleLoaded] = useState(false);

  leadsRef.current = leads;
  onSelectLeadRef.current = onSelectLead;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const pmtilesUrl = import.meta.env.VITE_MAP_PMTILES_URL as string | undefined;
    if (pmtilesUrl) {
      const p = new PMTiles(pmtilesUrl);
      protocol.add(p);
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: pmtilesUrl
        ? {
            version: 8,
            sources: {
              protomaps: {
                type: "vector",
                url: `pmtiles://${pmtilesUrl}`,
                attribution: "© OpenStreetMap contributors | Protomaps",
              },
            },
            layers: [
              { id: "background", type: "background", paint: { "background-color": "#f8f9fa" } },
              { id: "water",      type: "fill", source: "protomaps", "source-layer": "water",   paint: { "fill-color": "#bfdbfe" } },
              { id: "earth",      type: "fill", source: "protomaps", "source-layer": "earth",   paint: { "fill-color": "#f1f5f9" } },
              { id: "roads-case", type: "line", source: "protomaps", "source-layer": "roads",   paint: { "line-color": "#fff",    "line-width": ["interpolate", ["linear"], ["zoom"], 10, 1.5, 15, 5] }, layout: { "line-cap": "round", "line-join": "round" } },
              { id: "roads",      type: "line", source: "protomaps", "source-layer": "roads",   paint: { "line-color": "#e2e8f0", "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.75, 15, 3] }, layout: { "line-cap": "round", "line-join": "round" } },
              { id: "buildings",  type: "fill", source: "protomaps", "source-layer": "buildings", paint: { "fill-color": "#e8ecf0", "fill-opacity": 0.7 } },
            ],
          }
        : RASTER_STYLE,
      center: [-87.65, 41.88],
      zoom: 10,
      attributionControl: false,
    });

    // Controls
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");

    mapRef.current = map;

    map.on("load", () => {
      setStyleLoaded(true);
      // Route corridor glow
      map.addSource("route", {
        type: "geojson",
        data: { type: "Feature", geometry: { type: "LineString", coordinates: [] }, properties: {} },
      });
      map.addLayer({
        id: "route-glow",
        type: "line",
        source: "route",
        paint: { "line-color": "#93c5fd", "line-width": 12, "line-opacity": 0.3, "line-blur": 6 },
        layout: { "line-cap": "round", "line-join": "round" },
      });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        paint: { "line-color": "#2563eb", "line-width": 3, "line-opacity": 0.9 },
        layout: { "line-cap": "round", "line-join": "round" },
      });

      // Lead points — outer ring
      map.addSource("leads", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "lead-halo",
        type: "circle",
        source: "leads",
        paint: {
          "circle-color": "#fef2f2",
          "circle-radius": 9,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#f87171",
          "circle-opacity": ["case", ["==", ["get", "selected"], true], 1, 0],
          "circle-stroke-opacity": ["case", ["==", ["get", "selected"], true], 1, 0],
        },
      });
      map.addLayer({
        id: "lead-points",
        type: "circle",
        source: "leads",
        paint: {
          "circle-color": [
            "case",
            ["==", ["get", "selected"], true], "#2563eb",
            "#ef4444",
          ],
          "circle-radius": [
            "case",
            ["==", ["get", "selected"], true], 7,
            5,
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      map.on("click", "lead-points", (e) => {
        const feature = e.features?.[0];
        if (!feature) return;
        const businessId = feature.properties?.business_id as string | undefined;
        const found = leadsRef.current.find((l) => l.business_id === businessId);
        if (found) onSelectLeadRef.current(found);
      });

      map.on("mouseenter", "lead-points", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "lead-points", () => { map.getCanvas().style.cursor = ""; });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update route + leads data
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleLoaded) return;

    const routeSource = map.getSource("route") as maplibregl.GeoJSONSource | undefined;
    if (routeSource) {
      routeSource.setData({
        type: "Feature",
        geometry: routeGeoJson ?? { type: "LineString", coordinates: [] },
        properties: {},
      });

      // Fit bounds when route appears
      if (routeGeoJson && routeGeoJson.coordinates.length > 1) {
        const coords = routeGeoJson.coordinates as [number, number][];
        const bounds = coords.reduce(
          (b, c) => b.extend(c),
          new maplibregl.LngLatBounds(coords[0], coords[0]),
        );
        map.fitBounds(bounds, { padding: 80, maxZoom: 14 });
      }
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
            properties: {
              business_id: l.business_id,
              name: l.name,
              selected: selectedLead?.business_id === l.business_id,
            },
          })),
      });
    }
  }, [routeGeoJson, leads, selectedLead, styleLoaded]);

  // Pan to selected lead
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedLead || typeof selectedLead.lng !== "number") return;
    map.easeTo({ center: [selectedLead.lng as number, selectedLead.lat as number], zoom: Math.max(map.getZoom(), 14), duration: 400 });
  }, [selectedLead]);

  return (
    <div className="map-container" ref={containerRef} />
  );
}
