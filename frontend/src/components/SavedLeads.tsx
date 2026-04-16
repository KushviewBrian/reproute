import { useEffect, useState } from "react";

import { deleteSavedLead, downloadRouteCsv, listNotes, listSavedLeads, type SavedLead } from "../api/client";
import { cacheSavedLeads, readCachedSavedLeads } from "../lib/savedLeadCache";

type Props = {
  token?: string;
  currentRouteId: string | null;
  onAddToRoute?: (lead: SavedLead) => void;
  onCountChange?: (count: number) => void;
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
  return [...items].sort((a, b) => {
    const pa = STATUS_PRIORITY[a.status] ?? 99;
    const pb = STATUS_PRIORITY[b.status] ?? 99;
    if (pa !== pb) return pa - pb;
    const sa = a.final_score ?? -1;
    const sb = b.final_score ?? -1;
    if (sa !== sb) return sb - sa;
    return (a.business_name ?? "").localeCompare(b.business_name ?? "");
  });
}

export function SavedLeads({ token, currentRouteId, onAddToRoute, onCountChange }: Props) {
  const [items, setItems] = useState<SavedLead[]>([]);
  const [status, setStatus] = useState<string>("");
  const [exporting, setExporting] = useState(false);
  const [cacheMeta, setCacheMeta] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadSavedLeads() {
      try {
        const base = await listSavedLeads(token, status || undefined);
        if (!token) {
          if (!cancelled) setItems(base);
          return;
        }

        // Fallback for environments where /saved-leads note preview fields are not populated yet:
        // hydrate missing preview from /notes per business.
        const hydrated = await Promise.all(
          base.map(async (item) => {
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
  }, [token, status]);

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

  return (
    <>
      <div className="saved-header">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h2>Saved Leads</h2>
          {currentRouteId && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={handleExport}
              disabled={exporting}
            >
              <IconDownload />
              {exporting ? "Exporting..." : "Export CSV"}
            </button>
          )}
        </div>

        <select
          className="form-select"
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
        {cacheMeta && (
          <p style={{ fontSize: "0.7rem", color: "var(--gray-400)", marginTop: "0.35rem" }}>{cacheMeta}</p>
        )}
      </div>

      {items.length === 0 ? (
        <div className="empty-state" style={{ marginTop: "2rem" }}>
          <IconBookmark />
          <p className="empty-state-title">No saved leads</p>
          <p className="empty-state-body">
            {status ? `No leads with status "${STATUS_LABELS[status] ?? status}".` : "Save prospects from the Route tab to see them here."}
          </p>
        </div>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {items.map((it) => (
            <li key={it.id} className="saved-card">
              <div className="saved-card-top">
                <span className="saved-business-name">{it.business_name ?? it.business_id.slice(0, 8) + "…"}</span>
                <span className={`status-pill status-${it.status}`}>
                  {STATUS_LABELS[it.status] ?? it.status}
                </span>
              </div>
              {it.address && (
                <p style={{ fontSize: "0.7rem", color: "var(--gray-500)", margin: "0.1rem 0 0" }}>{it.address}</p>
              )}
              {it.route_label && (
                <p style={{ fontSize: "0.68rem", color: "var(--gray-400)", margin: "0.15rem 0 0" }}>
                  Route: {it.route_label}
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
