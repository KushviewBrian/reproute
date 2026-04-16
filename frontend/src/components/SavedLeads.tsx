import { useEffect, useState } from "react";

import { deleteSavedLead, downloadRouteCsv, listSavedLeads, type SavedLead } from "../api/client";

type Props = {
  token?: string;
  currentRouteId: string | null;
  onAddToRoute?: (lead: SavedLead) => void;
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

export function SavedLeads({ token, currentRouteId, onAddToRoute }: Props) {
  const [items, setItems] = useState<SavedLead[]>([]);
  const [status, setStatus] = useState<string>("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    listSavedLeads(token, status || undefined)
      .then(setItems)
      .catch(() => setItems([]));
  }, [token, status]);

  async function handleDelete(id: string) {
    await deleteSavedLead(id, token);
    setItems((prev) => prev.filter((it) => it.id !== id));
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
