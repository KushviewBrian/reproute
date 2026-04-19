import { useEffect, useState } from "react";

import {
  deleteSavedLead,
  downloadRouteCsv,
  downloadSavedLeadsCsv,
  downloadSavedLeadsCsvGrouped,
  getValidationState,
  listNotes,
  listSavedLeads,
  type SavedLead,
  type ValidationStateResponse,
  updateSavedLead,
} from "../api/client";
import { cacheSavedLeads, readCachedSavedLeads } from "../lib/savedLeadCache";
import { QUEUE_UPDATED_EVENT, enqueueStatusChange, getQueuedCount } from "../lib/offlineQueue";

type Props = {
  token?: string;
  currentRouteId: string | null;
  onAddToRoute?: (lead: SavedLead) => void;
  onCountChange?: (count: number) => void;
  onSelectLead?: (lead: SavedLead) => void;
};

const STATUS_LABELS: Record<string, string> = {
  saved: "Saved",
  visited: "Visited",
  called: "Called",
  follow_up: "Follow Up",
  not_interested: "Not Interested",
};

function IconDownload() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  );
}

function IconBookmark() {
  return (
    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
    </svg>
  );
}

function IconTrash() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
    </svg>
  );
}

const STATUS_PRIORITY: Record<string, number> = {
  follow_up: 0,
  saved: 1,
  called: 2,
  visited: 3,
  not_interested: 4,
};

function sortSavedLeads(items: SavedLead[]): SavedLead[] {
  const now = Date.now();
  return [...items].sort((a, b) => {
    const aDue = a.next_follow_up_at ? new Date(a.next_follow_up_at).getTime() : null;
    const bDue = b.next_follow_up_at ? new Date(b.next_follow_up_at).getTime() : null;
    const aOverdue = aDue != null && aDue < now;
    const bOverdue = bDue != null && bDue < now;
    if (aOverdue !== bOverdue) return aOverdue ? -1 : 1;
    if (aDue != null && bDue != null && aDue !== bDue) return aDue - bDue;
    if (aDue != null && bDue == null) return -1;
    if (aDue == null && bDue != null) return 1;
    const pa = STATUS_PRIORITY[a.status] ?? 99;
    const pb = STATUS_PRIORITY[b.status] ?? 99;
    if (pa !== pb) return pa - pb;
    const sa = a.final_score ?? -1;
    const sb = b.final_score ?? -1;
    if (sa !== sb) return sb - sa;
    return (a.business_name ?? "").localeCompare(b.business_name ?? "");
  });
}

export function SavedLeads({ token, currentRouteId, onAddToRoute, onCountChange, onSelectLead }: Props) {
  const [items, setItems] = useState<SavedLead[]>([]);
  const [status, setStatus] = useState<string>("");
  const [exporting, setExporting] = useState(false);
  const [exportingAll, setExportingAll] = useState(false);
  const [cacheMeta, setCacheMeta] = useState<string | null>(null);
  const [queueCount, setQueueCount] = useState(() => getQueuedCount());
  const [validationStates, setValidationStates] = useState<Record<string, ValidationStateResponse>>({});
  const [blueCollarOnly, setBlueCollarOnly] = useState(false);
  const [exportingGrouped, setExportingGrouped] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadSavedLeads() {
      try {
        const base = await listSavedLeads(token, status || undefined);
        if (!token) {
          if (!cancelled) setItems(blueCollarOnly ? base.filter((b) => b.is_blue_collar) : base);
          return;
        }

        // Fallback for environments where /saved-leads note preview fields are not populated yet:
        // hydrate missing preview from /notes per business.
        const base_filtered = blueCollarOnly ? base.filter((b) => b.is_blue_collar) : base;
        const hydrated = await Promise.all(
          base_filtered.map(async (item) => {
            if (item.latest_note_text) return item;
            try {
              const notes = await listNotes(item.business_id, token);
              if (!notes.length) return item;
              return {
                ...item,
                latest_note_text: notes[0].note_text,
                latest_note_created_at: notes[0].created_at,
              };
            } catch {
              return item;
            }
          }),
        );
        const sorted = sortSavedLeads(hydrated);
        cacheSavedLeads(status, sorted);
        if (!cancelled) {
          setItems(sorted);
          setCacheMeta(null);
          onCountChange?.(sorted.length);
          if (token) {
            Promise.allSettled(
              sorted.map((l) =>
                getValidationState(l.business_id, token).then((vs) => ({ id: l.business_id, vs })),
              ),
            ).then((results) => {
              if (cancelled) return;
              const map: Record<string, ValidationStateResponse> = {};
              for (const r of results) {
                if (r.status === "fulfilled") map[r.value.id] = r.value.vs;
              }
              setValidationStates(map);
            });
          }
        }
      } catch {
        const cached = readCachedSavedLeads(status);
        if (!cancelled) {
          if (cached) {
            const sorted = sortSavedLeads(cached.items);
            setItems(sorted);
            setCacheMeta(`Cached ${new Date(cached.updatedAt).toLocaleString()}`);
            onCountChange?.(sorted.length);
          } else {
            setItems([]);
            setCacheMeta(null);
            onCountChange?.(0);
          }
        }
      }
    }

    loadSavedLeads();
    return () => {
      cancelled = true;
    };
  }, [token, status, blueCollarOnly]);

  useEffect(() => {
    function refreshQueuedCount() {
      setQueueCount(getQueuedCount());
    }
    refreshQueuedCount();
    window.addEventListener("online", refreshQueuedCount);
    window.addEventListener("focus", refreshQueuedCount);
    window.addEventListener(QUEUE_UPDATED_EVENT, refreshQueuedCount);
    return () => {
      window.removeEventListener("online", refreshQueuedCount);
      window.removeEventListener("focus", refreshQueuedCount);
      window.removeEventListener(QUEUE_UPDATED_EVENT, refreshQueuedCount);
    };
  }, []);

  async function handleDelete(id: string) {
    await deleteSavedLead(id, token);
    setItems((prev) => {
      const next = sortSavedLeads(prev.filter((it) => it.id !== id));
      onCountChange?.(next.length);
      cacheSavedLeads(status, next);
      return next;
    });
  }

  async function handleExport() {
    if (!currentRouteId) return;
    setExporting(true);
    try {
      await downloadRouteCsv(currentRouteId, token, true);
    } finally {
      setExporting(false);
    }
  }

  async function handleExportAll() {
    setExportingAll(true);
    try {
      await downloadSavedLeadsCsv(token);
    } finally {
      setExportingAll(false);
    }
  }

  async function handleExportGrouped() {
    setExportingGrouped(true);
    try {
      await downloadSavedLeadsCsvGrouped("insurance_class", token);
    } finally {
      setExportingGrouped(false);
    }
  }

  async function handleFollowUpChange(id: string, value: string) {
    const iso = value ? `${value}T12:00:00Z` : null;
    const item = items.find((it) => it.id === id);
    if (!navigator.onLine || !token) {
      if (item) {
        enqueueStatusChange({
          business_id: item.business_id,
          route_id: item.route_id,
          status: item.status,
          next_follow_up_at: iso,
        });
        setQueueCount(getQueuedCount());
      }
      setItems((prev) => {
        const next = sortSavedLeads(prev.map((it) => (it.id === id ? { ...it, next_follow_up_at: iso } : it)));
        cacheSavedLeads(status, next);
        return next;
      });
      return;
    }
    const updated = await updateSavedLead(id, { next_follow_up_at: iso }, token);
    setItems((prev) => {
      const next = sortSavedLeads(prev.map((it) => (it.id === id ? { ...it, next_follow_up_at: updated.next_follow_up_at } : it)));
      cacheSavedLeads(status, next);
      return next;
    });
  }

  return (
    <>
      <div className="saved-header">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h2>Saved Leads</h2>
          <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
            <button className="btn btn-ghost btn-sm" onClick={handleExportAll} disabled={exportingAll}>
              <IconDownload />
              {exportingAll ? "Exporting..." : "Export CSV"}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={handleExportGrouped} disabled={exportingGrouped}>
              <IconDownload />
              {exportingGrouped ? "Exporting..." : "By Type CSV"}
            </button>
            {currentRouteId && (
              <button className="btn btn-ghost btn-sm" onClick={handleExport} disabled={exporting}>
                <IconDownload />
                {exporting ? "Exporting..." : "Route CSV"}
              </button>
            )}
          </div>
        </div>

        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginTop: "0.4rem", flexWrap: "wrap" }}>
          <select
            className="form-select"
            style={{ flex: 1 }}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="saved">Saved</option>
            <option value="visited">Visited</option>
            <option value="called">Called</option>
            <option value="follow_up">Follow Up</option>
            <option value="not_interested">Not Interested</option>
          </select>
          <button
            className={"toggle-chip" + (blueCollarOnly ? " active" : "")}
            style={{ whiteSpace: "nowrap" }}
            onClick={() => setBlueCollarOnly((v) => !v)}
            title="Show only blue-collar businesses"
          >
            🔧 Blue collar
          </button>
        </div>
        {cacheMeta && (
          <p style={{ fontSize: "0.7rem", color: "var(--gray-400)", marginTop: "0.35rem" }}>{cacheMeta}</p>
        )}
        {queueCount > 0 && (
          <p style={{ fontSize: "0.7rem", color: "#b45309", marginTop: "0.35rem" }}>
            {queueCount} unsynced change{queueCount > 1 ? "s" : ""} — will sync when online
          </p>
        )}
      </div>

      {items.length === 0 ? (
        <div className="empty-state" style={{ marginTop: "2rem" }}>
          <IconBookmark />
          <p className="empty-state-title">No saved leads</p>
          <p className="empty-state-body">
            {blueCollarOnly ? "No blue-collar leads saved." : status ? `No leads with status "${STATUS_LABELS[status] ?? status}".` : "Save prospects from the Route tab to see them here."}
          </p>
        </div>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {items.map((it) => (
            <li key={it.id} className="saved-card">
              <div className="saved-card-top">
                <button
                  className="saved-business-name"
                  style={{ background: "none", border: "none", padding: 0, cursor: "pointer", textAlign: "left" }}
                  onClick={() => onSelectLead?.(it)}
                >
                  {it.business_name ?? it.business_id.slice(0, 8) + "…"}
                </button>
                <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                  {it.is_blue_collar && (
                    <span style={{ fontSize: "0.62rem", background: "#eff6ff", color: "#1d4ed8", border: "1px solid #bfdbfe", borderRadius: "6px", padding: "0.1rem 0.35rem" }}>🔧</span>
                  )}
                  <span className={`status-pill status-${it.status}`}>
                    {STATUS_LABELS[it.status] ?? it.status}
                  </span>
                </div>
              </div>
              {it.owner_name && (
                <p style={{ fontSize: "0.7rem", color: "var(--gray-600)", margin: "0.1rem 0 0" }}>
                  Owner: <strong>{it.owner_name}</strong>
                  {it.owner_name_confidence != null && (
                    <span style={{ marginLeft: "0.3rem", fontSize: "0.63rem", color: "var(--gray-400)" }}>
                      {Math.round(it.owner_name_confidence * 100)}%
                    </span>
                  )}
                </p>
              )}
              {it.address && (
                <p style={{ fontSize: "0.7rem", color: "var(--gray-500)", margin: "0.1rem 0 0" }}>{it.address}</p>
              )}
              {(() => {
                const vs = validationStates[it.business_id];
                if (!vs) return null;
                const websiteField = vs.fields.find((f) => f.field_name === "website");
                const phoneField = vs.fields.find((f) => f.field_name === "phone");
                if (!websiteField && !phoneField) return null;
                function chipLabel(fieldName: string, state: string | null) {
                  const icon = state === "valid" ? "OK" : state === "warning" ? "⚠" : state === "invalid" ? "✗" : "?";
                  return `${fieldName.charAt(0).toUpperCase() + fieldName.slice(1)} ${icon}`;
                }
                function chipClass(state: string | null) {
                  if (state === "valid") return "val-state-chip val-state-chip--valid";
                  if (state === "warning") return "val-state-chip val-state-chip--warning";
                  if (state === "invalid") return "val-state-chip val-state-chip--invalid";
                  return "val-state-chip val-state-chip--unknown";
                }
                return (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", flexWrap: "wrap", marginTop: "0.25rem" }}>
                    {websiteField && <span className={chipClass(websiteField.state)}>{chipLabel("website", websiteField.state)}</span>}
                    {phoneField && <span className={chipClass(phoneField.state)}>{chipLabel("phone", phoneField.state)}</span>}
                    {vs.overall_confidence != null && (
                      <span style={{ fontSize: "0.65rem", color: "var(--gray-400)" }}>{Math.round(vs.overall_confidence)}% confidence</span>
                    )}
                  </div>
                );
              })()}
              {it.route_label && (
                <p style={{ fontSize: "0.68rem", color: "var(--gray-400)", margin: "0.15rem 0 0" }}>
                  Route: {it.route_label}
                </p>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.35rem" }}>
                <label style={{ fontSize: "0.7rem", color: "var(--gray-500)" }}>Follow-up:</label>
                <input
                  type="date"
                  className="form-input"
                  style={{ maxWidth: "11rem", fontSize: "0.72rem", padding: "0.3rem 0.45rem" }}
                  value={it.next_follow_up_at ? new Date(it.next_follow_up_at).toISOString().slice(0, 10) : ""}
                  onChange={(e) => void handleFollowUpChange(it.id, e.target.value)}
                />
              </div>
              {it.next_follow_up_at && new Date(it.next_follow_up_at).getTime() < Date.now() && (
                <p style={{ fontSize: "0.68rem", color: "#b42318", margin: "0.18rem 0 0" }}>
                  Overdue follow-up
                </p>
              )}
              {it.phone && (
                <a href={`tel:${it.phone.replace(/\D/g, "")}`} style={{ fontSize: "0.7rem", color: "var(--gray-500)", display: "block" }}>{it.phone}</a>
              )}
              {it.latest_note_text && (
                <p style={{ fontSize: "0.72rem", color: "var(--gray-700)", margin: "0.35rem 0 0", lineHeight: 1.35 }}>
                  Note: {it.latest_note_text}
                  {it.latest_note_created_at ? (
                    <span style={{ color: "var(--gray-400)" }}> ({new Date(it.latest_note_created_at).toLocaleString()})</span>
                  ) : null}
                </p>
              )}
              <div className="lead-card-actions" style={{ marginTop: "0.4rem" }}>
                {onAddToRoute && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => onAddToRoute(it)}
                  >
                    + Stop
                  </button>
                )}
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ color: "var(--gray-400)" }}
                  onClick={() => handleDelete(it.id)}
                >
                  <IconTrash />
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
