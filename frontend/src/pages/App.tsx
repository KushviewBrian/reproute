import { SignedIn, SignedOut, SignInButton, UserButton, useAuth } from "@clerk/clerk-react";
import { useCallback, useEffect, useState } from "react";

import { fetchLeads, patchRoute, saveLead, type Lead } from "../api/client";
import { LeadDetail } from "../components/LeadDetail";
import { LeadList } from "../components/LeadList";
import { MapPanel } from "../components/MapPanel";
import { RouteForm } from "../components/RouteForm";
import { SavedLeads } from "../components/SavedLeads";

type Tab = "route" | "saved";

export function App() {
  const { getToken } = useAuth();
  const [tab, setTab] = useState<Tab>("route");
  const [token, setToken] = useState<string | undefined>(undefined);
  const [routeId, setRouteId] = useState<string | null>(null);
  const [routeGeoJson, setRouteGeoJson] = useState<GeoJSON.LineString | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [minScore, setMinScore] = useState(40);
  const [hasPhone, setHasPhone] = useState<boolean | undefined>(undefined);
  const [hasWebsite, setHasWebsite] = useState<boolean | undefined>(undefined);
  const [corridor, setCorridor] = useState(1609);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getToken().then((t) => setToken(t ?? undefined));
  }, [getToken]);

  const loadLeads = useCallback(
    async (id: string) => {
      if (!token) return;
      const data = await fetchLeads(id, token, { minScore, hasPhone, hasWebsite, limit: 100 });
      setLeads(data.leads);
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
    if (!token) return;
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
    if (!routeId || !token) {
      setCorridor(next);
      return;
    }
    setCorridor(next);
    await patchRoute(routeId, next, token);
    await loadLeads(routeId);
  }

  return (
    <main className="app">
      <header className="topbar">
        <h1>Reproute</h1>
        <SignedIn>
          <UserButton />
        </SignedIn>
      </header>

      <SignedOut>
        <section className="panel">
          <p>Sign in to use the app.</p>
          <SignInButton />
        </section>
      </SignedOut>

      <SignedIn>
        <nav className="tabs">
          <button className={tab === "route" ? "active" : ""} onClick={() => setTab("route")}>Route Entry</button>
          <button className={tab === "saved" ? "active" : ""} onClick={() => setTab("saved")}>Saved Leads</button>
        </nav>

        {tab === "route" && (
          <>
            <RouteForm onCreated={onCreated} token={token} />
            {routeId && <p className="meta">Route ID: {routeId}</p>}
            {error && <p className="error">{error}</p>}
            <section className="panel">
              <h3>Filters</h3>
              <label>
                Min score: {minScore}
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={minScore}
                  onChange={(e) => setMinScore(Number(e.target.value))}
                />
              </label>
              <label>
                Corridor width
                <select value={corridor} onChange={(e) => onCorridorChange(Number(e.target.value))}>
                  <option value={805}>0.5 mi</option>
                  <option value={1609}>1.0 mi</option>
                  <option value={3218}>2.0 mi</option>
                </select>
              </label>
              <label>
                <input type="checkbox" checked={hasPhone === true} onChange={(e) => setHasPhone(e.target.checked ? true : undefined)} />
                Has phone
              </label>
              <label>
                <input type="checkbox" checked={hasWebsite === true} onChange={(e) => setHasWebsite(e.target.checked ? true : undefined)} />
                Has website
              </label>
              <button onClick={onApplyFilters}>Apply Filters</button>
            </section>
            <div className="route-grid">
              <LeadList leads={leads} onSave={onSaveLead} onSelect={setSelectedLead} />
              <MapPanel routeGeoJson={routeGeoJson} leads={leads} onSelectLead={setSelectedLead} />
            </div>
            <LeadDetail lead={selectedLead} routeId={routeId} token={token} onClose={() => setSelectedLead(null)} />
          </>
        )}

        {tab === "saved" && <SavedLeads token={token} currentRouteId={routeId} />}
      </SignedIn>
    </main>
  );
}
