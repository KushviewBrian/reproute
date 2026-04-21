import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/clerk-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { createNote, fetchLeads, getValidationStatesBatch, patchRoute, saveLead, type Lead, type ValidationStateResponse } from "../api/client";
import { LeadDetail, leadToDetail, savedLeadToDetail, type DetailLead } from "../components/LeadDetail";
import { LeadList } from "../components/LeadList";
import { MapPanel } from "../components/MapPanel";
import { RouteForm } from "../components/RouteForm";
import { SavedLeads } from "../components/SavedLeads";
import { TodayDashboard } from "../components/TodayDashboard";
import { ToastContainer } from "../components/ToastContainer";
import { cacheRouteLeads, readCachedRouteLeads } from "../lib/leadCache";
import { flushQueuedNotes, flushQueuedStatusChanges, getQueuedCount, QUEUE_UPDATED_EVENT } from "../lib/offlineQueue";
import { toast } from "../lib/toast";

type Tab = "today" | "route" | "saved";

type RecentRoute = { routeId: string; label: string; leadCount: number; createdAt: string };

type AppProps = {
  token?: string;
  refreshToken?: () => Promise<string | undefined>;
};

function toUserMessage(err: unknown, fallback: string): string {
  const msg = err instanceof Error ? err.message : "";
  if (!msg) return fallback;
  if (msg.startsWith("401")) return "Your session has expired — please sign in again.";
  if (msg.startsWith("429")) return "Too many requests — wait a moment and try again.";
  if (msg.toLowerCase().startsWith("network error")) {
    return "Network error — check your connection. Changes made offline will sync automatically when you reconnect.";
  }
  return msg;
}

function haversineMeters(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371000;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ─── Icons ────────────────────────────────────────────────────────────────── //

function IconRoute() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/>
      <path d="M6 17V9a2 2 0 0 1 2-2h8"/>
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

function IconCalendar() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
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
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    </svg>
  );
}

function IconFit() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
    </svg>
  );
}

function IconLocation() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
    </svg>
  );
}

function IconSync() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
    </svg>
  );
}

const RECENT_ROUTES_KEY = "reproute_recent_routes_v1";
const INSTALL_DISMISSED_KEY = "reproute_install_hint_dismissed";
const ONBOARDING_KEY = "reproute_onboarding_seen_v1";

function readRecentRoutes(): RecentRoute[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_ROUTES_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function writeRecentRoute(r: RecentRoute) {
  const existing = readRecentRoutes().filter((x) => x.routeId !== r.routeId);
  localStorage.setItem(RECENT_ROUTES_KEY, JSON.stringify([r, ...existing].slice(0, 5)));
}

export function App({ token, refreshToken }: AppProps) {
  const [tab, setTab] = useState<Tab>("today");
  const [routeId, setRouteId] = useState<string | null>(null);
  const [routeGeoJson, setRouteGeoJson] = useState<GeoJSON.LineString | null>(null);
  const [routeLabel, setRouteLabel] = useState<string>("");
  const [leads, setLeads] = useState<Lead[]>([]);
  const [leadsLoading, setLeadsLoading] = useState(false);

  // Filters
  const [minScore, setMinScore] = useState(40);
  const [hasPhone, setHasPhone] = useState<boolean | undefined>(undefined);
  const [hasWebsite, setHasWebsite] = useState<boolean | undefined>(undefined);
  const [hasOwnerName, setHasOwnerName] = useState<boolean | undefined>(undefined);
  const [insuranceClass, setInsuranceClass] = useState<string>("");
  const [sortBy, setSortBy] = useState<"score" | "business_type">("score");
  const [corridor, setCorridor] = useState(1609);
  const [blueCollar, setBlueCollar] = useState<boolean | undefined>(undefined);

  const [selectedLead, setSelectedLead] = useState<DetailLead | null>(null);
  const [waypoints, setWaypoints] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [cacheMeta, setCacheMeta] = useState<string | null>(null);
  const [savedCount, setSavedCount] = useState(0);
  const [validationStates, setValidationStates] = useState<Record<string, ValidationStateResponse>>({});
  // Cache validation states per route — they change only on explicit validate action, not on filter changes
  const validationCacheRef = useRef<Map<string, Record<string, ValidationStateResponse>>>(new Map());

  // Queue
  const [queueCount, setQueueCount] = useState(0);

  // Install / onboarding
  const [showInstallHint, setShowInstallHint] = useState(false);
  const [installPromptEvent, setInstallPromptEvent] = useState<Event | null>(null);
  const isFirstRun = !localStorage.getItem(ONBOARDING_KEY);

  // Field session
  const [fieldSession, setFieldSession] = useState(false);
  const [currentPosition, setCurrentPosition] = useState<{ lat: number; lng: number } | null>(null);
  const watchIdRef = useRef<number | null>(null);

  // Map resize trigger
  const [mapResizeTrigger, setMapResizeTrigger] = useState(0);

  // Sync queue count
  useEffect(() => {
    setQueueCount(getQueuedCount());
    function onQueueUpdate() { setQueueCount(getQueuedCount()); }
    window.addEventListener(QUEUE_UPDATED_EVENT, onQueueUpdate);
    return () => window.removeEventListener(QUEUE_UPDATED_EVENT, onQueueUpdate);
  }, []);

  // Install hint
  useEffect(() => {
    if (!localStorage.getItem(INSTALL_DISMISSED_KEY)) setShowInstallHint(true);
    function onBeforeInstall(e: Event) {
      e.preventDefault();
      setInstallPromptEvent(e);
    }
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    return () => window.removeEventListener("beforeinstallprompt", onBeforeInstall);
  }, []);

  // Offline queue flush
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    let flushInFlight = false;

    async function flushOfflineQueues() {
      if (cancelled || flushInFlight || !navigator.onLine) return;
      flushInFlight = true;
      try {
        await Promise.allSettled([flushQueuedNotes(token), flushQueuedStatusChanges(token)]);
      } finally {
        flushInFlight = false;
      }
    }

    void flushOfflineQueues();
    const interval = window.setInterval(() => void flushOfflineQueues(), 30_000);
    window.addEventListener("online", flushOfflineQueues);
    return () => {
      cancelled = true;
      clearInterval(interval);
      window.removeEventListener("online", flushOfflineQueues);
    };
  }, [token]);

  // Field session watchPosition
  useEffect(() => {
    return () => {
      if (watchIdRef.current != null) navigator.geolocation.clearWatch(watchIdRef.current);
    };
  }, []);

  function toggleFieldSession() {
    if (fieldSession) {
      if (watchIdRef.current != null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
      setFieldSession(false);
      setCurrentPosition(null);
    } else {
      watchIdRef.current = navigator.geolocation.watchPosition(
        (pos) => setCurrentPosition({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        () => {
          toast.warn("Location access denied or unavailable");
          setFieldSession(false);
        },
        { maximumAge: 15000, timeout: 10000 },
      );
      setFieldSession(true);
    }
  }

  function sortLeads(input: Lead[], mode: "score" | "business_type"): Lead[] {
    const next = [...input];
    if (fieldSession && currentPosition) {
      next.sort((a, b) => {
        const distA = a.lat != null ? haversineMeters(currentPosition.lat, currentPosition.lng, a.lat, a.lng!) : Infinity;
        const distB = b.lat != null ? haversineMeters(currentPosition.lat, currentPosition.lng, b.lat, b.lng!) : Infinity;
        return distA - distB;
      });
      return next;
    }
    if (mode === "business_type") {
      next.sort((a, b) => {
        const c = (a.insurance_class ?? "ZZZ").localeCompare(b.insurance_class ?? "ZZZ");
        return c !== 0 ? c : b.final_score - a.final_score;
      });
      return next;
    }
    next.sort((a, b) => b.final_score - a.final_score);
    return next;
  }

  const loadLeads = useCallback(
    async (id: string) => {
      setLeadsLoading(true);
      try {
        const data = await fetchLeads(id, token, {
          minScore,
          hasPhone,
          hasWebsite,
          hasOwnerName,
          insuranceClass: insuranceClass ? [insuranceClass] : undefined,
          limit: 100,
          scoreVersion: "v2",
          blueCollar,
        });
        const sorted = sortLeads(data.leads, sortBy);
        setLeads(sorted);
        cacheRouteLeads(id, sorted);
        const hasV2 = sorted.some((l) => l.score_version === "v2");
        setCacheMeta(
          hasV2 ? null : "Using v1 fallback for this route. Recreate route to populate v2 scores.",
        );
        if (token) {
          const businessIds = Array.from(new Set(sorted.map((l) => l.business_id)));
          if (!businessIds.length) {
            setValidationStates({});
          } else {
            const cached = validationCacheRef.current.get(id);
            const uncachedIds = cached
              ? businessIds.filter((bid) => !(bid in cached))
              : businessIds;
            if (cached && uncachedIds.length === 0) {
              setValidationStates(cached);
            } else {
              getValidationStatesBatch(uncachedIds.length ? uncachedIds : businessIds, token)
                .then((map) => {
                  const merged = { ...(cached ?? {}), ...map };
                  validationCacheRef.current.set(id, merged);
                  setValidationStates(merged);
                })
                .catch(() => {
                  if (cached) setValidationStates(cached);
                });
            }
          }
        }
      } catch (err) {
        const cached = readCachedRouteLeads(id);
        if (cached) {
          setLeads(sortLeads(cached.leads, sortBy));
          setCacheMeta(`Cached ${new Date(cached.updatedAt).toLocaleString()}`);
          return;
        }
        throw err;
      } finally {
        setLeadsLoading(false);
      }
    },
    [token, minScore, hasPhone, hasWebsite, hasOwnerName, insuranceClass, sortBy, blueCollar],
  );

  async function onCreated(created: {
    routeId: string;
    routeGeoJson: GeoJSON.LineString;
    originLabel: string;
    destLabel: string;
  }) {
    const id = created.routeId;
    const label = `${created.originLabel} → ${created.destLabel}`;
    setRouteId(id);
    setRouteGeoJson(created.routeGeoJson);
    setRouteLabel(label);
    setError(null);
    localStorage.setItem(ONBOARDING_KEY, "1");
    try {
      await loadLeads(id);
      writeRecentRoute({ routeId: id, label, leadCount: leads.length, createdAt: new Date().toISOString() });
      toast.success("Route created");
    } catch (err) {
      setError(toUserMessage(err, "Failed to fetch leads"));
    }
  }

  function onReloadRoute(id: string) {
    setRouteId(id);
    setError(null);
    loadLeads(id).catch((err) => setError(toUserMessage(err, "Failed to load route")));
  }

  async function onSaveLead(lead: Lead) {
    try {
      await saveLead({ business_id: lead.business_id, route_id: routeId ?? undefined }, token);
      toast.success("Lead saved");
    } catch (err) {
      toast.error(toUserMessage(err, "Failed to save lead"));
    }
  }

  async function onSaveLeadWithNote(lead: Lead, noteText: string, initialStatus?: string) {
    let savedId: string | null = null;
    try {
      const saved = await saveLead({ business_id: lead.business_id, route_id: routeId ?? undefined }, token);
      savedId = saved.id;
      if (noteText) {
        await createNote(
          { business_id: lead.business_id, route_id: routeId ?? undefined, note_text: noteText },
          token,
        );
      }
      if (initialStatus && savedId) {
        const { updateSavedLead } = await import("../api/client");
        await updateSavedLead(savedId, { status: initialStatus }, token);
      }
      setError(null);
      toast.success(noteText ? "Saved with note" : "Lead saved");
    } catch (err) {
      if (savedId) {
        toast.warn("Lead saved, but note failed");
      } else {
        toast.error(toUserMessage(err, "Failed to save lead"));
      }
    }
  }

  async function onApplyFilters() {
    if (!routeId) return;
    try {
      await loadLeads(routeId);
    } catch (err) {
      setError(toUserMessage(err, "Failed to apply filters"));
    }
  }

  async function onCorridorChange(next: number) {
    setCorridor(next);
    if (!routeId) return;
    try {
      await patchRoute(routeId, next, token);
      await loadLeads(routeId);
    } catch (err) {
      setError(toUserMessage(err, "Failed to update corridor"));
    }
  }

  function onAddStop(lead: Lead) {
    if (lead.lat == null || lead.lng == null) return;
    const label = `${lead.name}, ${lead.lat.toFixed(5)}, ${lead.lng.toFixed(5)}`;
    setWaypoints((prev) => [...prev, label]);
    setTab("route");
  }

  // Trigger map resize when detail panel opens/closes
  useEffect(() => {
    const timer = setTimeout(() => setMapResizeTrigger((n) => n + 1), 190);
    return () => clearTimeout(timer);
  }, [selectedLead]);

  async function handleManualSync() {
    try {
      await Promise.allSettled([flushQueuedNotes(token), flushQueuedStatusChanges(token)]);
      toast.success("Synced");
    } catch {
      toast.error("Sync failed");
    }
  }

  const corridorMiles = (corridor / 1609).toFixed(1);
  const recentRoutes = readRecentRoutes();

  // ─── App content ───────────────────────────────────────────────────────────
  const appContent = (
    <div className={`app-body${selectedLead ? " detail-open" : ""}`}>
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        {/* Icon rail */}
        <nav className="sidebar-rail" role="navigation" aria-label="Main navigation">
          <button
            className={`rail-btn${tab === "today" ? " active" : ""}`}
            onClick={() => setTab("today")}
            aria-label="Today"
            data-tooltip="Today"
          >
            <IconCalendar />
          </button>
          <button
            className={`rail-btn${tab === "route" ? " active" : ""}`}
            onClick={() => setTab("route")}
            aria-label="Route"
            data-tooltip="Route"
          >
            <IconRoute />
          </button>
          <button
            className={`rail-btn${tab === "saved" ? " active" : ""}`}
            onClick={() => setTab("saved")}
            aria-label={`Saved leads${savedCount > 0 ? `, ${savedCount} saved` : ""}`}
            data-tooltip="Saved"
          >
            <IconBookmark />
            {savedCount > 0 && (
              <span className="rail-btn-badge" aria-hidden="true">{savedCount}</span>
            )}
          </button>
          {routeId && (
            <button
              className={`rail-btn${fieldSession ? " active" : ""}`}
              onClick={toggleFieldSession}
              aria-label={fieldSession ? "Stop field session" : "Start field session"}
              data-tooltip={fieldSession ? "Stop session" : "Field mode"}
              style={{ marginTop: "auto" }}
            >
              <IconLocation />
            </button>
          )}
        </nav>

        {/* Content panel */}
        <div className="sidebar-content">
          <div className="sidebar-scroll">
            {/* Offline sync banner */}
            {queueCount > 0 && (
              <div className="sidebar-offline-banner">
                <IconSync />
                <span>{queueCount} pending — will sync when online</span>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={handleManualSync}
                  style={{ padding: "0.15rem 0.4rem", fontSize: "0.65rem" }}
                >
                  Sync
                </button>
              </div>
            )}

            {/* Tab content */}
            {tab === "today" && (
              <TodayDashboard
                token={token}
                onGoToRoute={() => setTab("route")}
                onSelectLead={(sl) => setSelectedLead(savedLeadToDetail(sl))}
                onResumeRoute={(id) => {
                  setRouteId(id);
                  setTab("route");
                  loadLeads(id).catch((err) => setError(toUserMessage(err, "Failed to load route")));
                }}
                isFirstRun={isFirstRun}
              />
            )}

            {tab === "route" && (
              <>
                <RouteForm
                  onCreated={onCreated}
                  token={token}
                  corridor={corridor}
                  waypoints={waypoints}
                  onWaypointsChange={setWaypoints}
                  routeId={routeId}
                  routeLabel={routeLabel}
                  onEditRoute={() => { setRouteId(null); setRouteGeoJson(null); setLeads([]); setRouteLabel(""); }}
                  recentRoutes={recentRoutes}
                  onReloadRoute={onReloadRoute}
                />

                {/* Route active: filter chips */}
                {routeId && (
                  <FilterChipBar
                    minScore={minScore}
                    setMinScore={setMinScore}
                    hasPhone={hasPhone}
                    setHasPhone={setHasPhone}
                    hasWebsite={hasWebsite}
                    setHasWebsite={setHasWebsite}
                    hasOwnerName={hasOwnerName}
                    setHasOwnerName={setHasOwnerName}
                    blueCollar={blueCollar}
                    setBlueCollar={setBlueCollar}
                    insuranceClass={insuranceClass}
                    setInsuranceClass={setInsuranceClass}
                    sortBy={sortBy}
                    setSortBy={setSortBy}
                    onApply={onApplyFilters}
                    corridor={corridor}
                    onCorridorChange={onCorridorChange}
                  />
                )}

                {error && (
                  <div className="error-banner">
                    <IconAlert />
                    <span>{error}</span>
                    <button className="btn btn-ghost btn-sm" onClick={() => routeId && loadLeads(routeId).catch((e) => setError(toUserMessage(e, "Retry failed")))}>Retry</button>
                    <button className="btn btn-icon btn-sm" aria-label="Dismiss" onClick={() => setError(null)}>×</button>
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
                  loading={leadsLoading}
                  selectedLead={selectedLead}
                  onSave={onSaveLead}
                  onSaveWithNote={onSaveLeadWithNote}
                  onSelect={(l) => setSelectedLead(leadToDetail(l))}
                  onAddStop={onAddStop}
                  corridorMiles={corridorMiles}
                  validationStates={validationStates}
                  userLat={currentPosition?.lat}
                  userLng={currentPosition?.lng}
                  isFirstRun={isFirstRun}
                />
              </>
            )}

            {tab === "saved" && (
              <SavedLeads
                token={token}
                currentRouteId={routeId}
                onCountChange={setSavedCount}
                onSelectLead={(sl) => setSelectedLead(savedLeadToDetail(sl))}
                onAddToRoute={(lead) => {
                  if (!lead.business_name) return;
                  const label = lead.address
                    ? `${lead.business_name}, ${lead.address}`
                    : lead.business_name;
                  setWaypoints((prev) => [...prev, label]);
                  setTab("route");
                }}
                isFirstRun={isFirstRun}
              />
            )}
          </div>

          {/* Sidebar footer */}
          <div className="sidebar-footer">
            {showInstallHint && !installPromptEvent && (
              <span className="sidebar-install-hint">
                Add to home screen for faster access
              </span>
            )}
            {installPromptEvent && (
              <button
                className="btn btn-ghost btn-sm"
                style={{ fontSize: "0.68rem", padding: "0.2rem 0.5rem" }}
                onClick={() => {
                  (installPromptEvent as any).prompt?.();
                  setInstallPromptEvent(null);
                }}
              >
                Install App
              </button>
            )}
            {showInstallHint && (
              <button
                className="btn btn-icon btn-sm"
                aria-label="Dismiss install hint"
                style={{ marginLeft: "auto" }}
                onClick={() => {
                  localStorage.setItem(INSTALL_DISMISSED_KEY, "1");
                  setShowInstallHint(false);
                }}
              >
                ×
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* ── Map ── */}
      <div className="map-area">
        <MapPanel
          routeGeoJson={routeGeoJson}
          leads={leads}
          selectedLead={selectedLead}
          onSelectLead={(l) => setSelectedLead(leadToDetail(l))}
          userPosition={currentPosition}
          resizeTrigger={mapResizeTrigger}
        />
        {!routeId && (
          <div className="map-empty-state" aria-hidden="true">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2">
              <circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/>
              <path d="M6 17V9a2 2 0 0 1 2-2h8"/>
            </svg>
            <p>Plan a route to discover prospects</p>
          </div>
        )}
        {routeId && (
          <button
            className="map-fit-btn"
            aria-label="Fit route on map"
            onClick={() => setMapResizeTrigger((n) => n + 1)}
          >
            <IconFit /> Fit route
          </button>
        )}
      </div>

      {/* ── Detail panel ── */}
      {selectedLead && (
        <LeadDetail
          lead={selectedLead}
          routeId={routeId}
          token={token}
          refreshToken={refreshToken}
          onClose={() => setSelectedLead(null)}
          userPosition={currentPosition}
        />
      )}

      {/* ── Mobile bottom nav ── */}
      <nav className="mobile-nav" aria-label="Main navigation">
        <button
          className={`mobile-nav-btn${tab === "today" ? " active" : ""}`}
          onClick={() => setTab("today")}
        >
          <IconCalendar />
          Today
        </button>
        <button
          className={`mobile-nav-btn${tab === "route" ? " active" : ""}`}
          onClick={() => setTab("route")}
        >
          <IconRoute />
          Route
        </button>
        <button
          className={`mobile-nav-btn${tab === "saved" ? " active" : ""}`}
          onClick={() => setTab("saved")}
        >
          <span className={savedCount > 0 ? "mobile-nav-btn-badge" : ""} data-count={savedCount > 0 ? savedCount : undefined}>
            <IconBookmark />
          </span>
          Saved
        </button>
      </nav>
    </div>
  );

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/>
            <path d="M6 17V9a2 2 0 0 1 2-2h8"/>
          </svg>
          <div>
            Rep<span className="topbar-brand-accent">Route</span>
            <div className="topbar-brand-sub">by Kushview</div>
          </div>
        </div>

        <div className="topbar-route-status">
          {routeId && routeLabel ? (
            <>
              <strong>{routeLabel}</strong>
              {leads.length > 0 && <> · {leads.length} prospects</>}
            </>
          ) : (
            "No active route"
          )}
        </div>

        <div className="topbar-actions">
          {queueCount > 0 && (
            <span className="topbar-offline-dot" title={`${queueCount} changes pending sync`} />
          )}
          <SignedIn>
            <UserButton
              appearance={{
                variables: {
                  colorBackground: "var(--surface-1)",
                  colorText: "var(--text-primary)",
                  colorPrimary: "var(--accent)",
                },
              }}
            />
          </SignedIn>
        </div>
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

      <ToastContainer />
    </div>
  );
}

// ─── Filter Chip Bar ───────────────────────────────────────────────────────── //

type FilterChipBarProps = {
  minScore: number; setMinScore: (v: number) => void;
  hasPhone: boolean | undefined; setHasPhone: (v: boolean | undefined) => void;
  hasWebsite: boolean | undefined; setHasWebsite: (v: boolean | undefined) => void;
  hasOwnerName: boolean | undefined; setHasOwnerName: (v: boolean | undefined) => void;
  blueCollar: boolean | undefined; setBlueCollar: (v: boolean | undefined) => void;
  insuranceClass: string; setInsuranceClass: (v: string) => void;
  sortBy: "score" | "business_type"; setSortBy: (v: "score" | "business_type") => void;
  onApply: () => void;
  corridor: number; onCorridorChange: (v: number) => void;
};

const INSURANCE_CLASSES = [
  "", "Auto Service", "Contractor / Trades", "Retail", "Food & Beverage",
  "Personal Services", "Medical / Clinic", "Professional / Office", "Light Industrial", "Other Commercial",
];
const INSURANCE_LABELS: Record<string, string> = {
  "": "All types", "Auto Service": "Auto", "Contractor / Trades": "Trades", "Retail": "Retail",
  "Food & Beverage": "F&B", "Personal Services": "Services", "Medical / Clinic": "Medical",
  "Professional / Office": "Office", "Light Industrial": "Industrial", "Other Commercial": "Other",
};

const SORT_OPTIONS: { value: "score" | "business_type"; label: string }[] = [
  { value: "score", label: "Top score" },
  { value: "business_type", label: "Business type" },
];

function FilterChipBar({
  minScore, setMinScore, hasPhone, setHasPhone, hasWebsite, setHasWebsite,
  hasOwnerName, setHasOwnerName, blueCollar, setBlueCollar,
  insuranceClass, setInsuranceClass, sortBy, setSortBy, onApply,
}: FilterChipBarProps) {
  const [openPopover, setOpenPopover] = useState<string | null>(null);

  useEffect(() => {
    if (!openPopover) return;
    function onOutsideClick(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest(".filter-popover-wrap")) setOpenPopover(null);
    }
    document.addEventListener("mousedown", onOutsideClick);
    return () => document.removeEventListener("mousedown", onOutsideClick);
  }, [openPopover]);

  function toggle(key: string) {
    setOpenPopover((prev) => (prev === key ? null : key));
  }

  function applyAndClose() {
    setOpenPopover(null);
    onApply();
  }

  return (
    <div className="filter-chip-bar">
      {/* Score */}
      <div className="filter-popover-wrap">
        <button
          className={`filter-chip${minScore > 0 ? " active" : ""}`}
          onClick={() => toggle("score")}
        >
          Score {minScore}+ <span className="filter-chip-caret">▾</span>
        </button>
        {openPopover === "score" && (
          <div className="filter-popover">
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span className="filter-popover-label">Min score</span>
              <span className="filter-popover-value">{minScore}</span>
            </div>
            <input
              type="range" min={0} max={100} value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
            />
            <button className="btn btn-primary btn-sm" onClick={applyAndClose}>Apply</button>
          </div>
        )}
      </div>

      {/* Phone */}
      <button
        className={`filter-chip${hasPhone ? " active" : ""}`}
        onClick={() => { setHasPhone(hasPhone ? undefined : true); onApply(); }}
      >
        Phone
      </button>

      {/* Website */}
      <button
        className={`filter-chip${hasWebsite ? " active" : ""}`}
        onClick={() => { setHasWebsite(hasWebsite ? undefined : true); onApply(); }}
      >
        Website
      </button>

      {/* Owner */}
      <button
        className={`filter-chip${hasOwnerName ? " active" : ""}`}
        onClick={() => { setHasOwnerName(hasOwnerName ? undefined : true); onApply(); }}
      >
        Owner known
      </button>

      {/* Blue collar */}
      <button
        className={`filter-chip${blueCollar ? " active" : ""}`}
        onClick={() => { setBlueCollar(blueCollar ? undefined : true); onApply(); }}
      >
        🔧 Blue collar
      </button>

      {/* Type */}
      <div className="filter-popover-wrap">
        <button
          className={`filter-chip${insuranceClass ? " active" : ""}`}
          onClick={() => toggle("type")}
        >
          {INSURANCE_LABELS[insuranceClass] ?? "Type"} <span className="filter-chip-caret">▾</span>
        </button>
        {openPopover === "type" && (
          <div className="filter-popover">
            <span className="filter-popover-label">Business type</span>
            <div className="popover-radio-list">
              {INSURANCE_CLASSES.map((ic) => (
                <button
                  key={ic}
                  className={`popover-radio-btn${insuranceClass === ic ? " selected" : ""}`}
                  onClick={() => { setInsuranceClass(ic); applyAndClose(); }}
                >
                  <span className="popover-radio-dot" />
                  {INSURANCE_LABELS[ic]}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Sort */}
      <div className="filter-popover-wrap">
        <button
          className="filter-chip"
          onClick={() => toggle("sort")}
        >
          {sortBy === "score" ? "Top score" : "By type"} <span className="filter-chip-caret">▾</span>
        </button>
        {openPopover === "sort" && (
          <div className="filter-popover">
            <span className="filter-popover-label">Sort by</span>
            <div className="popover-radio-list">
              {SORT_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  className={`popover-radio-btn${sortBy === opt.value ? " selected" : ""}`}
                  onClick={() => { setSortBy(opt.value); applyAndClose(); }}
                >
                  <span className="popover-radio-dot" />
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
