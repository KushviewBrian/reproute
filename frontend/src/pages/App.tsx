import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/clerk-react";
import { useCallback, useEffect, useState } from "react";

import { createNote, fetchLeads, patchRoute, saveLead, type Lead } from "../api/client";
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
  const [insuranceClass, setInsuranceClass] = useState<string>("");
  const [sortBy, setSortBy] = useState<"score" | "business_type">("score");
  const [corridor, setCorridor] = useState(1609);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [waypoints, setWaypoints] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [cacheMeta, setCacheMeta] = useState<string | null>(null);
  const [savedCount, setSavedCount] = useState(0);
  const [showInstallHint, setShowInstallHint] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const dismissed = window.localStorage.getItem("reproute_install_hint_dismissed");
    if (!dismissed) {
      setShowInstallHint(true);
    }
  }, []);

  function sortLeads(input: Lead[], mode: "score" | "business_type"): Lead[] {
    const next = [...input];
    if (mode === "business_type") {
      next.sort((a, b) => {
        const classCmp = (a.insurance_class ?? "ZZZ").localeCompare(b.insurance_class ?? "ZZZ");
        if (classCmp !== 0) return classCmp;
        return b.final_score - a.final_score;
      });
      return next;
    }
    next.sort((a, b) => b.final_score - a.final_score);
    return next;
  }

  const loadLeads = useCallback(
    async (id: string) => {
      try {
        const data = await fetchLeads(id, token, {
          minScore,
          hasPhone,
          hasWebsite,
          insuranceClass: insuranceClass ? [insuranceClass] : undefined,
          limit: 100,
        });
        const sorted = sortLeads(data.leads, sortBy);
        setLeads(sorted);
        cacheRouteLeads(id, sorted);
        setCacheMeta(null);
      } catch (err) {
        const cached = readCachedRouteLeads(id);
        if (cached) {
          setLeads(sortLeads(cached.leads, sortBy));
          setCacheMeta(`Cached ${new Date(cached.updatedAt).toLocaleString()}`);
          return;
        }
        throw err;
      }
    },
    [token, minScore, hasPhone, hasWebsite, insuranceClass, sortBy],
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

  async function onSaveLeadWithNote(lead: Lead, noteText: string) {
    let savedOk = false;
    try {
      await saveLead({ business_id: lead.business_id, route_id: routeId ?? undefined }, token);
      savedOk = true;
      await createNote(
        {
          business_id: lead.business_id,
          route_id: routeId ?? undefined,
          note_text: noteText,
        },
        token,
      );
      setError(null);
    } catch (err) {
      if (savedOk) {
        setError(err instanceof Error ? `Lead saved, but note failed: ${err.message}` : "Lead saved, but note failed");
      } else {
        setError(err instanceof Error ? `Failed to save lead: ${err.message}` : "Failed to save lead");
      }
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

  function onAddStop(lead: Lead) {
    if (lead.lat == null || lead.lng == null) return;
    const label = `${lead.name}, ${lead.lat.toFixed(5)}, ${lead.lng.toFixed(5)}`;
    setWaypoints((prev) => [...prev, label]);
    setTab("route");
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
            {savedCount > 0 && (
              <span
                style={{
                  marginLeft: "0.35rem",
                  fontSize: "0.65rem",
                  fontWeight: 700,
                  padding: "0.05rem 0.35rem",
                  borderRadius: "100px",
                  background: "var(--gray-200)",
                  color: "var(--gray-700)",
                }}
              >
                {savedCount}
              </span>
            )}
          </button>
        </div>

        <div className="sidebar-scroll">
          {showInstallHint && (
            <div className="cache-banner" style={{ marginBottom: "0.5rem" }}>
              <IconDatabase />
              <span style={{ flex: 1 }}>
                Install for faster access: Android Chrome menu → Install App. iPhone Safari share menu → Add to Home Screen.
              </span>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  window.localStorage.setItem("reproute_install_hint_dismissed", "1");
                  setShowInstallHint(false);
                }}
                style={{ marginLeft: "0.4rem", padding: "0.15rem 0.35rem" }}
              >
                Dismiss
              </button>
            </div>
          )}

          {tab === "route" && (
            <>
              <RouteForm
                onCreated={onCreated}
                token={token}
                corridor={corridor}
                waypoints={waypoints}
                onWaypointsChange={setWaypoints}
              />

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
                      onClick={() => { setHasPhone(hasPhone ? undefined : true); }}
                    >
                      Phone
                    </button>
                    <button
                      className={`toggle-chip${hasWebsite ? " active" : ""}`}
                      onClick={() => { setHasWebsite(hasWebsite ? undefined : true); }}
                    >
                      Website
                    </button>
                  </div>
                </div>

                <div className="filter-row">
                  <span className="filter-label">Business type</span>
                  <select
                    className="form-select"
                    style={{ width: "auto", fontSize: "0.75rem" }}
                    value={insuranceClass}
                    onChange={(e) => setInsuranceClass(e.target.value)}
                  >
                    <option value="">All</option>
                    <option value="Auto Service">Auto Service</option>
                    <option value="Contractor / Trades">Contractor / Trades</option>
                    <option value="Retail">Retail</option>
                    <option value="Food & Beverage">Food & Beverage</option>
                    <option value="Personal Services">Personal Services</option>
                    <option value="Medical / Clinic">Medical / Clinic</option>
                    <option value="Professional / Office">Professional / Office</option>
                    <option value="Light Industrial">Light Industrial</option>
                    <option value="Other Commercial">Other Commercial</option>
                  </select>
                </div>

                <div className="filter-row">
                  <span className="filter-label">Sort</span>
                  <select
                    className="form-select"
                    style={{ width: "auto", fontSize: "0.75rem" }}
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as "score" | "business_type")}
                  >
                    <option value="score">Top score</option>
                    <option value="business_type">Business type</option>
                  </select>
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
                onSaveWithNote={onSaveLeadWithNote}
                onSelect={setSelectedLead}
                onAddStop={onAddStop}
                corridorMiles={corridorMiles}
              />
            </>
          )}

          {tab === "saved" && (
            <SavedLeads
              token={token}
              currentRouteId={routeId}
              onCountChange={setSavedCount}
              onAddToRoute={(lead) => {
                if (!lead.business_name) return;
                const label = lead.address
                  ? `${lead.business_name}, ${lead.address}`
                  : lead.business_name;
                setWaypoints((prev) => [...prev, label]);
                setTab("route");
              }}
            />
          )}
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
          <div>
            Rep<span>Route</span>
            <div style={{ fontSize: "0.55rem", opacity: 0.5, letterSpacing: "0.05em", marginTop: "-2px" }}>by Kushview</div>
          </div>
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
            <p className="signin-title">Welcome to RepRoute</p>
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
