import { useState } from "react";

import { createRoute, geocode } from "../api/client";

type Props = {
  token?: string;
  onCreated: (created: { routeId: string; routeGeoJson: GeoJSON.LineString }) => void;
};

export function RouteForm({ token, onCreated }: Props) {
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [originCoords, setOriginCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [destinationCoords, setDestinationCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [corridor, setCorridor] = useState(1609);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function resolveOrigin() {
    const r = await geocode(origin, token);
    if (r.results[0]) {
      setOrigin(r.results[0].label);
      setOriginCoords({ lat: r.results[0].lat, lng: r.results[0].lng });
    }
  }

  async function resolveDestination() {
    const r = await geocode(destination, token);
    if (r.results[0]) {
      setDestination(r.results[0].label);
      setDestinationCoords({ lat: r.results[0].lat, lng: r.results[0].lng });
    }
  }

  function useMyLocation() {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setOrigin(`Current location (${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)})`);
        setOriginCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      },
      () => setError("Could not get current location"),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }

  async function submit() {
    if (!originCoords || !destinationCoords) return;
    setLoading(true);
    setError(null);
    try {
      const created = await createRoute(
        {
          origin_label: origin,
          origin_lat: originCoords.lat,
          origin_lng: originCoords.lng,
          destination_label: destination,
          destination_lat: destinationCoords.lat,
          destination_lng: destinationCoords.lng,
          corridor_width_meters: corridor,
        },
        token,
      );
      onCreated({ routeId: created.route_id, routeGeoJson: created.route_geojson });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create route");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <h2>Route Entry</h2>
      {!token && <p className="meta">Waiting for auth token...</p>}
      <label>
        Origin
        <input value={origin} onChange={(e) => setOrigin(e.target.value)} onBlur={resolveOrigin} disabled={!token} />
      </label>
      <button type="button" onClick={useMyLocation} disabled={!token}>Use my location</button>
      <label>
        Destination
        <input value={destination} onChange={(e) => setDestination(e.target.value)} onBlur={resolveDestination} disabled={!token} />
      </label>

      <label>
        Corridor
        <select value={corridor} onChange={(e) => setCorridor(Number(e.target.value))}>
          <option value={805}>0.5 mi</option>
          <option value={1609}>1.0 mi</option>
          <option value={3218}>2.0 mi</option>
        </select>
      </label>

      <button disabled={!token || !originCoords || !destinationCoords || loading} onClick={submit}>
        {loading ? "Finding..." : "Find Prospects"}
      </button>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
