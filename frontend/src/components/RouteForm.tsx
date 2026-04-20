import { useState, useEffect, useRef } from "react";

import { createRoute, geocode, reverseGeocode } from "../api/client";

type ResolvedLocation = { label: string; lat: number; lng: number };

type RecentRoute = { routeId: string; label: string; leadCount: number; createdAt: string };

type Props = {
  token?: string;
  corridor: number;
  waypoints: string[];
  onWaypointsChange: (waypoints: string[]) => void;
  onCreated: (created: { routeId: string; routeGeoJson: GeoJSON.LineString; originLabel: string; destLabel: string }) => void;
  routeId?: string | null;
  routeLabel?: string;
  onEditRoute?: () => void;
  recentRoutes?: RecentRoute[];
  onReloadRoute?: (routeId: string) => void;
};

type LoadingStep = null | "geocoding" | "routing" | "prospects";

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

function IconClock() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
    </svg>
  );
}

function IconChevron({ open }: { open: boolean }) {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
      style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.15s" }}>
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

const STEP_LABELS: Record<NonNullable<LoadingStep>, string> = {
  geocoding: "Resolving addresses…",
  routing: "Building route…",
  prospects: "Finding prospects…",
};

const STEP_WIDTHS: Record<NonNullable<LoadingStep>, string> = {
  geocoding: "33%",
  routing: "66%",
  prospects: "90%",
};

async function resolveAddress(text: string, token?: string): Promise<ResolvedLocation> {
  const trimmed = text.trim();
  const coordMatch = trimmed.match(/^(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)$/);
  if (coordMatch) {
    return { label: trimmed, lat: parseFloat(coordMatch[1]), lng: parseFloat(coordMatch[2]) };
  }
  let data: { results: ResolvedLocation[]; degraded: boolean };
  try {
    data = await geocode(trimmed, token);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "";
    if (msg.toLowerCase().startsWith("network error")) {
      throw new Error("Geocoding unavailable — check your connection and try again.");
    }
    throw new Error("Geocoding failed — try again in a moment.");
  }
  if (!data.results.length) {
    throw new Error(`Couldn't find "${trimmed}" — try adding a city or zip code.`);
  }
  return data.results[0];
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export function RouteForm({
  token, corridor, waypoints, onWaypointsChange, onCreated,
  routeId, routeLabel, onEditRoute, recentRoutes = [], onReloadRoute,
}: Props) {
  const [originText, setOriginText] = useState("");
  const [destText, setDestText] = useState("");
  const [originSuggestions, setOriginSuggestions] = useState<string[]>([]);
  const [destSuggestions, setDestSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState<LoadingStep>(null);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [waypointsOpen, setWaypointsOpen] = useState(false);
  const [recentOpen, setRecentOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevLenRef = useRef(waypoints.length);

  useEffect(() => {
    if (waypoints.length > prevLenRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
    prevLenRef.current = waypoints.length;
  }, [waypoints.length]);

  const canSubmit = !!originText.trim() && !!destText.trim() && !loading;

  useEffect(() => {
    const trimmed = originText.trim();
    if (trimmed.length < 3) { setOriginSuggestions([]); return; }
    const timer = window.setTimeout(async () => {
      try {
        const data = await geocode(trimmed, token);
        setOriginSuggestions(data.results.slice(0, 5).map((r) => r.label));
      } catch { setOriginSuggestions([]); }
    }, 300);
    return () => window.clearTimeout(timer);
  }, [originText, token]);

  useEffect(() => {
    const trimmed = destText.trim();
    if (trimmed.length < 3) { setDestSuggestions([]); return; }
    const timer = window.setTimeout(async () => {
      try {
        const data = await geocode(trimmed, token);
        setDestSuggestions(data.results.slice(0, 5).map((r) => r.label));
      } catch { setDestSuggestions([]); }
    }, 300);
    return () => window.clearTimeout(timer);
  }, [destText, token]);

  function useMyLocation() {
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude: lat, longitude: lng } = pos.coords;
        try {
          const reversed = await reverseGeocode(lat, lng, token);
          setOriginText(reversed.results[0]?.label ?? `${lat.toFixed(5)}, ${lng.toFixed(5)}`);
        } catch {
          setOriginText(`${lat.toFixed(5)}, ${lng.toFixed(5)}`);
        } finally {
          setLocating(false);
        }
      },
      (posErr) => {
        setError(
          posErr.code === posErr.PERMISSION_DENIED
            ? "Location access denied — enable it in your browser settings."
            : "Couldn't get your current location — please enter your address manually.",
        );
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }

  function addWaypoint() { onWaypointsChange([...waypoints, ""]); }
  function removeWaypoint(i: number) { onWaypointsChange(waypoints.filter((_, idx) => idx !== i)); }
  function updateWaypoint(i: number, value: string) { onWaypointsChange(waypoints.map((w, idx) => (idx === i ? value : w))); }

  async function submit() {
    setLoading(true);
    setError(null);
    setLoadingStep("geocoding");
    try {
      const originLoc = await resolveAddress(originText, token);
      const destLoc = await resolveAddress(destText, token);
      const resolvedWaypoints = await Promise.all(
        waypoints.filter((w) => w.trim()).map((w) => resolveAddress(w, token))
      );
      setLoadingStep("routing");
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
      setLoadingStep("prospects");
      onCreated({
        routeId: created.route_id,
        routeGeoJson: created.route_geojson,
        originLabel: originLoc.label,
        destLabel: destLoc.label,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create route";
      setError(
        msg.startsWith("401") ? "Your session has expired — please sign in again."
        : msg.startsWith("429") ? "Too many requests — wait a moment and try again."
        : msg,
      );
    } finally {
      setLoading(false);
      setLoadingStep(null);
    }
  }

  // Phase B: route is active
  if (routeId) {
    return (
      <div className="route-summary-bar">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="route-summary-label">{routeLabel || "Active route"}</div>
          <div className="route-summary-meta">Route active</div>
        </div>
        {onEditRoute && (
          <button className="btn btn-ghost btn-sm" onClick={onEditRoute}>
            Edit route
          </button>
        )}
      </div>
    );
  }

  // Phase A: no route
  return (
    <div className="route-form">
      <div className="route-form-title">Plan Route</div>

      {/* FROM / TO with route-line glyph */}
      <div className="route-inputs-wrap">
        <div className="route-line-glyph">
          <div className="route-line-glyph-dot" />
          <div className="route-line-glyph-line" />
          <div className="route-line-glyph-dot dest" />
        </div>
        <div className="route-inputs-fields">
          <div className="form-field">
            <label htmlFor="origin-input">From</label>
            <div className="input-row">
              <input
                id="origin-input"
                className="form-input"
                type="text"
                list="origin-suggestions"
                placeholder="Start address or city"
                value={originText}
                onChange={(e) => setOriginText(e.target.value)}
                disabled={loading}
              />
              <datalist id="origin-suggestions">
                {originSuggestions.map((s) => <option key={s} value={s} />)}
              </datalist>
              <button
                type="button"
                className="btn btn-icon locate-btn"
                title="Use my current location"
                aria-label="Use my current location"
                onClick={useMyLocation}
                disabled={loading || locating}
              >
                {locating ? <span className="spinner" /> : <IconLocate />}
              </button>
            </div>
          </div>

          {/* Waypoints */}
          {waypointsOpen && waypoints.map((wp, i) => (
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
                  aria-label="Remove stop"
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
              list="dest-suggestions"
              placeholder="End address or city"
              value={destText}
              onChange={(e) => setDestText(e.target.value)}
              disabled={loading}
            />
            <datalist id="dest-suggestions">
              {destSuggestions.map((s) => <option key={s} value={s} />)}
            </datalist>
          </div>
        </div>
      </div>

      {/* Waypoints toggle */}
      <button
        type="button"
        className="waypoints-toggle"
        onClick={() => {
          if (!waypointsOpen) { addWaypoint(); setWaypointsOpen(true); }
          else setWaypointsOpen(false);
        }}
        disabled={loading}
      >
        <IconPlus />
        {waypointsOpen ? "Hide stops" : "Add stops"}
        {waypoints.length > 0 && waypointsOpen && (
          <span style={{ marginLeft: "0.2rem", fontSize: "0.65rem", color: "var(--text-muted)" }}>({waypoints.length})</span>
        )}
      </button>

      <div ref={bottomRef} />

      {/* Loading progress */}
      {loading && loadingStep && (
        <div>
          <div className="route-progress-bar">
            <div className="route-progress-fill" style={{ width: STEP_WIDTHS[loadingStep] }} />
          </div>
          <div className="route-progress-label">{STEP_LABELS[loadingStep]}</div>
        </div>
      )}

      {error && (
        <p style={{ fontSize: "0.75rem", color: "var(--accent-danger)", margin: "0.25rem 0" }}>{error}</p>
      )}

      <button
        className="btn btn-primary"
        style={{ marginTop: "0.125rem" }}
        disabled={!canSubmit}
        onClick={submit}
      >
        {loading ? (
          <><span className="spinner" /> {loadingStep ? STEP_LABELS[loadingStep] : "Working…"}</>
        ) : (
          <><IconSearch /> Find Prospects</>
        )}
      </button>

      {/* Recent routes */}
      {recentRoutes.length > 0 && (
        <details className="recent-routes-toggle" open={recentOpen} onToggle={(e) => setRecentOpen((e.target as HTMLDetailsElement).open)}>
          <summary>
            <IconClock />
            Recent routes
            <IconChevron open={recentOpen} />
          </summary>
          {recentRoutes.map((r) => (
            <button
              key={r.routeId}
              className="recent-route-btn"
              onClick={() => onReloadRoute?.(r.routeId)}
            >
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>{r.label}</span>
              <span className="recent-route-meta">{r.leadCount} leads · {formatDate(r.createdAt)}</span>
            </button>
          ))}
        </details>
      )}
    </div>
  );
}
