import { useEffect, useState } from "react";

import { exportRouteCsvUrl, listSavedLeads, type SavedLead } from "../api/client";

type Props = {
  token?: string;
  currentRouteId: string | null;
};

export function SavedLeads({ token, currentRouteId }: Props) {
  const [items, setItems] = useState<SavedLead[]>([]);
  const [status, setStatus] = useState<string>("");

  useEffect(() => {
    listSavedLeads(token, status || undefined)
      .then(setItems)
      .catch(() => setItems([]));
  }, [token, status]);

  return (
    <section className="panel">
      <h2>Saved Leads</h2>
      <label>
        Filter status
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">all</option>
          <option value="saved">saved</option>
          <option value="visited">visited</option>
          <option value="called">called</option>
          <option value="not_interested">not interested</option>
          <option value="follow_up">follow up</option>
        </select>
      </label>
      {currentRouteId && (
        <a className="button-link" href={exportRouteCsvUrl(currentRouteId, true)} target="_blank" rel="noreferrer">
          Export CSV (saved only)
        </a>
      )}
      <ul className="lead-list">
        {items.map((it) => (
          <li key={it.id} className="lead-card">
            <div>ID: {it.business_id}</div>
            <div>Status: {it.status}</div>
            <div>Priority: {it.priority}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
