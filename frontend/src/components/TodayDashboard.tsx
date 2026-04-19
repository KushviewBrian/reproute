import { useEffect, useState } from "react";

import { getSavedLeadsToday, type SavedLead, type SavedLeadsTodayResponse } from "../api/client";

type Props = {
  token?: string;
  onGoToRoute: () => void;
  onSelectLead?: (lead: SavedLead) => void;
};

function Section({ title, items, onSelectLead }: { title: string; items: SavedLead[]; onSelectLead?: (lead: SavedLead) => void }) {
  return (
    <div className="saved-header" style={{ marginBottom: "0.6rem" }}>
      <h2>{title}</h2>
      {items.length === 0 ? (
        <p style={{ fontSize: "0.75rem", color: "var(--gray-500)" }}>None</p>
      ) : (
        <ul style={{ listStyle: "none", margin: "0.45rem 0 0", padding: 0 }}>
          {items.map((item) => (
            <li key={item.id} className="saved-card" style={{ marginBottom: "0.45rem" }}>
              <div className="saved-card-top">
                <button
                  className="saved-business-name"
                  style={{ background: "none", border: "none", padding: 0, cursor: "pointer", textAlign: "left" }}
                  onClick={() => onSelectLead?.(item)}
                >
                  {item.business_name ?? "Unnamed business"}
                </button>
                <span className={`status-pill status-${item.status}`}>{item.status}</span>
              </div>
              {item.next_follow_up_at && (
                <p style={{ fontSize: "0.7rem", color: "var(--gray-500)", marginTop: "0.2rem" }}>
                  Follow-up: {new Date(item.next_follow_up_at).toLocaleDateString()}
                </p>
              )}
              {(item as any).owner_name && (
                <p style={{ fontSize: "0.7rem", color: "var(--gray-600)", marginTop: "0.2rem" }}>
                  Owner: <strong>{(item as any).owner_name}</strong>
                </p>
              )}
              {item.latest_note_text && (
                <p style={{ fontSize: "0.72rem", color: "var(--gray-700)", marginTop: "0.25rem" }}>
                  Note: {item.latest_note_text}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function TodayDashboard({ token, onGoToRoute, onSelectLead }: Props) {
  const [data, setData] = useState<SavedLeadsTodayResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await getSavedLeadsToday(token);
        if (!cancelled) setData(response);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load today view");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (loading) {
    return <p style={{ fontSize: "0.85rem", color: "var(--gray-500)" }}>Loading today view…</p>;
  }
  if (error) {
    return <p style={{ fontSize: "0.85rem", color: "#b42318" }}>{error}</p>;
  }
  if (!data) {
    return null;
  }

  const isEmpty =
    data.overdue.length === 0 &&
    data.due_today.length === 0 &&
    data.high_priority_untouched.length === 0 &&
    !data.recent_route;

  if (isEmpty) {
    return (
      <div className="empty-state" style={{ marginTop: "1rem" }}>
        <p className="empty-state-title">No tasks for today</p>
        <p className="empty-state-body">Create a route to start discovering leads.</p>
        <button className="btn btn-primary btn-sm" onClick={onGoToRoute}>
          Create route
        </button>
      </div>
    );
  }

  return (
    <>
      <Section title="Overdue follow-ups" items={data.overdue} onSelectLead={onSelectLead} />
      <Section title="Due today" items={data.due_today} onSelectLead={onSelectLead} />
      <Section title="High-priority untouched" items={data.high_priority_untouched} onSelectLead={onSelectLead} />
      {data.blue_collar_today && data.blue_collar_today.length > 0 && (
        <Section title="🔧 Blue-collar priorities" items={data.blue_collar_today} onSelectLead={onSelectLead} />
      )}
      {data.has_owner_name && data.has_owner_name.length > 0 && (
        <Section title="👤 Leads with owner name" items={data.has_owner_name} onSelectLead={onSelectLead} />
      )}
      <div className="saved-header">
        <h2>Recent route</h2>
        {data.recent_route ? (
          <p style={{ fontSize: "0.75rem", color: "var(--gray-600)", marginTop: "0.35rem" }}>
            {data.recent_route.label} · Unsaved leads: {data.recent_route.unsaved_lead_count}
          </p>
        ) : (
          <p style={{ fontSize: "0.75rem", color: "var(--gray-500)" }}>No recent route</p>
        )}
      </div>
    </>
  );
}
