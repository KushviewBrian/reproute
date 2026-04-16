import { useState } from "react";

import { createRoute, geocode, type Lead } from "../api/client";

type ResolvedLocation = { label: string; lat: number; lng: number };

type Props = {
  token?: string;
  corridor: number;
  pendingStop: Lead | null;
  onPendingStopAdded: () => void;
  onCreated: (created: { routeId: string; routeGeoJson: GeoJSON.LineString }) => void;
};

function IconLocate() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function IconPlus() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
    </svg>
  );
}

function IconX() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  );
}

async function resolveAddress(text: string, token?: string): Promise<ResolvedLocation> {
  const trimmed = text.trim();
  const coordMatch = trimmed.match(/^(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)$/);
  if (coordMatch) {
    return { label: trimmed, lat: parseFloat(coordMatch[1]), lng: parseFloat(coordMatch[2]) };
  }
  const data = await geocode(trimmed, token);
  if (!data.results.length) throw new Error(`No results for "${trimmed}"`);
  return data.results[0];
}

export function RouteForm({ token, corridor, pendingStop, onPendingStopAdded, onCreated }: Props) {
  const [originText, setOriginText] = useState("");
  const [destText, setDestText] = useState("");
  const [waypoints, setWaypoints] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If a pending stop arrives, append it as a waypoint before destination
  if (pendingStop && pendingStop.lat != null && pendingStop.lng != null) {
    const label = `${pendingStop.name} (${pendingStop.lat!.toFixed(5)}, ${pendingStop.lng!.toFixed(5)})`;
    setWaypoints((prev) => [...prev, label]);
    onPendingStopAdded();
  }

  const canSubmit = !!originText.trim() && !!destText.trim() && !loading;

  function useMyLocation() {
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setOriginText(`${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)}`);
        setLocating(false);
      },
      () => {
        setError("Could not get current location");
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }

  function addWaypoint() {
    setWaypoints((prev) => [...prev, ""]);
  }

  function removeWaypoint(i: number) {
    setWaypoints((prev) => prev.filter((_, idx) => idx !== i));
  }

  function updateWaypoint(i: number, value: string) {
    setWaypoints((prev) => prev.map((w, idx) => (idx === i ? value : w)));
  }

  async function submit() {
    setLoading(true);
    setError(null);
    try {
      const originLoc = await resolveAddress(originText, token);
      const destLoc = await resolveAddress(destText, token);
      const resolvedWaypoints = await Promise.all(
        waypoints.filter((w) => w.trim()).map((w) => resolveAddress(w, token))
      );

      const created = await createRoute(
        {
          origin_label: originLoc.label,
          origin_lat: originLoc.lat,
          origin_lng: originLoc.lng,
          destination_label: destLoc.label,
          destination_lat: destLoc.lat,
          destination_lng: destLoc.lng,
          corridor_width_meters: corridor,
          waypoints: resolvedWaypoints.map((w) => ({ label: w.label, lat: w.lat, lng: w.lng })),
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
    <div className="route-form">
      <h2>Plan Route</h2>

      <div className="form-field">
        <label htmlFor="origin-input">From</label>
        <div className="input-row">
          <input
            id="origin-input"
            className="form-input"
            type="text"
            placeholder="Start address, city, or zip"
            value={originText}
            onChange={(e) => setOriginText(e.target.value)}
            disabled={loading}
          />
          <button
            type="button"
            className="btn btn-icon locate-btn"
            title="Use my current location"
            onClick={useMyLocation}
            disabled={loading || locating}
          >
            {locating ? <span className="spinner" /> : <IconLocate />}
          </button>
        </div>
      </div>

      {waypoints.map((wp, i) => (
        <div className="form-field" key={i}>
          <label>Stop {i + 1}</label>
          <div className="input-row">
            <input
              className="form-input"
              type="text"
              placeholder="Address, city, or coordinates"
              value={wp}
              onChange={(e) => updateWaypoint(i, e.target.value)}
              disabled={loading}
            />
            <button
              type="button"
              className="btn btn-icon"
              title="Remove stop"
              onClick={() => removeWaypoint(i)}
              disabled={loading}
            >
              <IconX />
            </button>
          </div>
        </div>
      ))}

      <div className="form-field">
        <label htmlFor="dest-input">To</label>
        <input
          id="dest-input"
          className="form-input"
          type="text"
          placeholder="End address, city, or zip"
          value={destText}
          onChange={(e) => setDestText(e.target.value)}
          disabled={loading}
        />
      </div>

      <button
        type="button"
        className="btn btn-ghost btn-sm"
        style={{ alignSelf: "flex-start", marginBottom: "0.25rem" }}
        onClick={addWaypoint}
        disabled={loading}
      >
        <IconPlus /> Add stop
      </button>

      {error && (
        <p style={{ fontSize: "0.75rem", color: "#b91c1c", margin: "0.375rem 0" }}>{error}</p>
      )}

      <button
        className="btn btn-primary"
        style={{ marginTop: "0.25rem" }}
        disabled={!canSubmit}
        onClick={submit}
      >
        {loading ? (
          <><span className="spinner" /> Finding prospects…</>
        ) : (
          <><IconSearch /> Find Prospects</>
        )}
      </button>
    </div>
  );
}
