import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/clerk-react";
import { useCallback, useState } from "react";

import { fetchLeads, patchRoute, saveLead, type Lead } from "../api/client";
import { LeadDetail } from "../components/LeadDetail";
import { LeadList } from "../components/LeadList";
import { MapPanel } from "../components/MapPanel";
import { RouteForm } from "../components/RouteForm";
import { SavedLeads } from "../components/SavedLeads";
import { cacheRouteLeads, readCachedRouteLeads } from "../lib/leadCache";

type Tab = "route" | "saved";

type AppProps = {
  token?: string;
};

function IconRoute() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12h18M3 6h18M3 18h18" />
    </svg>
  );
}

function IconBookmark() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function IconLock() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>
  );
}

function IconAlert() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
  );
}

function IconDatabase() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    </svg>
  );
}

export function App({ token }: AppProps) {
  const [tab, setTab] = useState<Tab>("route");
  const [routeId, setRouteId] = useState<string | null>(null);
  const [routeGeoJson, setRouteGeoJson] = useState<GeoJSON.LineString | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [minScore, setMinScore] = useState(40);
  const [hasPhone, setHasPhone] = useState<boolean | undefined>(undefined);
  const [hasWebsite, setHasWebsite] = useState<boolean | undefined>(undefined);
  const [corridor, setCorridor] = useState(1609);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cacheMeta, setCacheMeta] = useState<string | null>(null);

  const loadLeads = useCallback(
    async (id: string) => {
      try {
        const data = await fetchLeads(id, token, { minScore, hasPhone, hasWebsite, limit: 100 });
        setLeads(data.leads);
        cacheRouteLeads(id, data.leads);
        setCacheMeta(null);
      } catch (err) {
        const cached = readCachedRouteLeads(id);
        if (cached) {
          setLeads(cached.leads);
          setCacheMeta(`Cached ${new Date(cached.updatedAt).toLocaleString()}`);
          return;
        }
        throw err;
      }
    },
    [token, minScore, hasPhone, hasWebsite],
  );

  async function onCreated(created: { routeId: string; routeGeoJson: GeoJSON.LineString }) {
    const id = created.routeId;
    setRouteId(id);
    setRouteGeoJson(created.routeGeoJson);
    setError(null);
    try {
      await loadLeads(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch leads");
    }
  }

  async function onSaveLead(lead: Lead) {
    try {
      await saveLead({ business_id: lead.business_id, route_id: routeId ?? undefined }, token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save lead");
    }
  }

  async function onApplyFilters() {
    if (!routeId) return;
    try {
      await loadLeads(routeId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to apply filters");
    }
  }

  async function onCorridorChange(next: number) {
    setCorridor(next);
    if (!routeId) return;
    await patchRoute(routeId, next, token);
    await loadLeads(routeId);
  }

  const corridorMiles = (corridor / 1609).toFixed(1);

  const appContent = (
    <div className="app-body">
      <aside className="sidebar">
        <div className="sidebar-tabs">
          <button
            className={`sidebar-tab${tab === "route" ? " active" : ""}`}
            onClick={() => setTab("route")}
          >
            <IconRoute />
            Route
          </button>
          <button
            className={`sidebar-tab${tab === "saved" ? " active" : ""}`}
            onClick={() => setTab("saved")}
          >
            <IconBookmark />
            Saved
          </button>
        </div>

        <div className="sidebar-scroll">
          {tab === "route" && (
            <>
              <RouteForm onCreated={onCreated} token={token} />

              <div className="filter-strip">
                <h3>Filters</h3>

                <div className="filter-row">
                  <span className="filter-label">Min score</span>
                  <span className="filter-value">{minScore}</span>
                </div>
                <input
                  className="range-input"
                  type="range"
                  min={0}
                  max={100}
                  value={minScore}
                  onChange={(e) => setMinScore(Number(e.target.value))}
                />

                <div className="filter-row">
                  <span className="filter-label">Corridor</span>
                  <select
                    className="form-select"
                    style={{ width: "auto", fontSize: "0.75rem" }}
                    value={corridor}
                    onChange={(e) => onCorridorChange(Number(e.target.value))}
                  >
                    <option value={805}>0.5 mi</option>
                    <option value={1609}>1.0 mi</option>
                    <option value={3218}>2.0 mi</option>
                  </select>
                </div>

                <div className="filter-row">
                  <span className="filter-label">Contact info</span>
                  <div className="toggle-group">
                    <button
                      className={`toggle-chip${hasPhone ? " active" : ""}`}
                      onClick={() => setHasPhone(hasPhone ? undefined : true)}
                    >
                      Phone
                    </button>
                    <button
                      className={`toggle-chip${hasWebsite ? " active" : ""}`}
                      onClick={() => setHasWebsite(hasWebsite ? undefined : true)}
                    >
                      Website
                    </button>
                  </div>
                </div>

                <button className="btn btn-ghost btn-sm" style={{ alignSelf: "flex-end" }} onClick={onApplyFilters}>
                  Apply
                </button>
              </div>

              {error && (
                <div className="error-banner">
                  <IconAlert />
                  {error}
                </div>
              )}
              {cacheMeta && (
                <div className="cache-banner">
                  <IconDatabase />
                  {cacheMeta}
                </div>
              )}

              <LeadList
                leads={leads}
                selectedLead={selectedLead}
                onSave={onSaveLead}
                onSelect={setSelectedLead}
                corridorMiles={corridorMiles}
              />
            </>
          )}

          {tab === "saved" && <SavedLeads token={token} currentRouteId={routeId} />}
        </div>
      </aside>

      <div className="map-area">
        <MapPanel
          routeGeoJson={routeGeoJson}
          leads={leads}
          selectedLead={selectedLead}
          onSelectLead={setSelectedLead}
        />
      </div>

      {selectedLead && (
        <LeadDetail
          lead={selectedLead}
          routeId={routeId}
          token={token}
          onClose={() => setSelectedLead(null)}
        />
      )}
    </div>
  );

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12h18M3 6h18M3 18h18" />
          </svg>
          Re<span>route</span>
        </div>
        <SignedIn>
          <UserButton />
        </SignedIn>
      </header>

      <SignedOut>
        <div className="signin-screen">
          <div className="signin-card">
            <div className="signin-icon">
              <IconLock />
            </div>
            <p className="signin-title">Welcome to Reproute</p>
            <p className="signin-subtitle">Sign in to start discovering prospects along your route.</p>
            <SignInButton>
              <button className="btn btn-primary" style={{ marginTop: "0.25rem" }}>
                Sign in
              </button>
            </SignInButton>
          </div>
        </div>
      </SignedOut>
      <SignedIn>{appContent}</SignedIn>
    </div>
  );
}
