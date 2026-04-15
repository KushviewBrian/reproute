import { useState } from "react";

import { createRoute } from "../api/client";
import { AddressAutocomplete, type ResolvedLocation } from "./AddressAutocomplete";

type Props = {
  token?: string;
  authRequired: boolean;
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

export function RouteForm({ token, authRequired, onCreated }: Props) {
  const [originLoc, setOriginLoc] = useState<ResolvedLocation | null>(null);
  const [destinationLoc, setDestinationLoc] = useState<ResolvedLocation | null>(null);
  const [corridor, setCorridor] = useState(1609);
  const [loading, setLoading] = useState(false);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [originKey, setOriginKey] = useState(0); // force re-mount to reset input after "use location"

  const disabled = authRequired && !token;
  const canSubmit = !disabled && !!originLoc && !!destinationLoc && !loading;

  function useMyLocation() {
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        // Inject as a resolved location directly — no geocoding needed
        const loc: ResolvedLocation = {
          label: `${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)}`,
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        };
        setOriginLoc(loc);
        // Re-mount the autocomplete so it shows the new label
        setOriginKey((k) => k + 1);
        setLocating(false);
      },
      () => {
        setError("Could not get current location");
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }

  async function submit() {
    if (!originLoc || !destinationLoc) return;
    setLoading(true);
    setError(null);
    try {
      const created = await createRoute(
        {
          origin_label: originLoc.label,
          origin_lat: originLoc.lat,
          origin_lng: originLoc.lng,
          destination_label: destinationLoc.label,
          destination_lat: destinationLoc.lat,
          destination_lng: destinationLoc.lng,
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
    <div className="route-form">
      <h2>Plan Route</h2>

      {disabled && (
        <p style={{ fontSize: "0.75rem", color: "var(--gray-400)", marginBottom: "0.625rem" }}>
          Waiting for authentication…
        </p>
      )}

      {/* Origin with "use my location" button */}
      <div className="autocomplete-with-action">
        <AddressAutocomplete
          key={originKey}
          id="origin"
          label="From"
          placeholder="Start address, city, or zip"
          token={token}
          disabled={disabled}
          onResolve={setOriginLoc}
          onClear={() => setOriginLoc(null)}
          initialLabel={originLoc?.label}
        />
        <button
          type="button"
          className="btn btn-icon locate-btn"
          title="Use my current location"
          onClick={useMyLocation}
          disabled={disabled || locating}
        >
          {locating ? <span className="spinner" /> : <IconLocate />}
        </button>
      </div>

      <AddressAutocomplete
        id="destination"
        label="To"
        placeholder="End address, city, or zip"
        token={token}
        disabled={disabled}
        onResolve={setDestinationLoc}
        onClear={() => setDestinationLoc(null)}
      />

      <div className="form-field" style={{ marginTop: "0.5rem" }}>
        <label htmlFor="corridor-select" style={{ fontSize: "0.75rem", fontWeight: 500, color: "var(--gray-600)", marginBottom: "0.25rem", display: "block" }}>
          Corridor width
        </label>
        <select
          id="corridor-select"
          className="form-select"
          value={corridor}
          onChange={(e) => setCorridor(Number(e.target.value))}
          disabled={disabled}
        >
          <option value={805}>0.5 mi — tight focus</option>
          <option value={1609}>1.0 mi — recommended</option>
          <option value={3218}>2.0 mi — wide sweep</option>
        </select>
      </div>

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
