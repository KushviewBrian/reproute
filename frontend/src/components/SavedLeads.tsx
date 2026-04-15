import { useEffect, useState } from "react";

import { exportRouteCsvUrl, listSavedLeads, type SavedLead } from "../api/client";

type Props = {
  token?: string;
  currentRouteId: string | null;
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

export function SavedLeads({ token, currentRouteId }: Props) {
  const [items, setItems] = useState<SavedLead[]>([]);
  const [status, setStatus] = useState<string>("");

  useEffect(() => {
    listSavedLeads(token, status || undefined)
      .then(setItems)
      .catch(() => setItems([]));
  }, [token, status]);

  return (
    <>
      <div className="saved-header">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h2>Saved Leads</h2>
          {currentRouteId && (
            <a
              className="btn btn-ghost btn-sm"
              href={exportRouteCsvUrl(currentRouteId, true)}
              target="_blank"
              rel="noreferrer"
            >
              <IconDownload />
              Export CSV
            </a>
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
                <span className="saved-business-id">{it.business_id.slice(0, 8)}…</span>
                <span className={`status-pill status-${it.status}`}>
                  {STATUS_LABELS[it.status] ?? it.status}
                </span>
              </div>
              {it.priority != null && (
                <span style={{ fontSize: "0.7rem", color: "var(--gray-400)" }}>
                  Priority {it.priority}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
