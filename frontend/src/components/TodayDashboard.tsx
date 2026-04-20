import { useEffect, useRef, useState } from "react";

import { getSavedLeadsToday, type SavedLead, type SavedLeadsTodayResponse } from "../api/client";

type Props = {
  token?: string;
  onGoToRoute: () => void;
  onSelectLead?: (lead: SavedLead) => void;
  onResumeRoute?: (routeId: string) => void;
  isFirstRun?: boolean;
};

function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  return `${days} days ago`;
}

function isOverdue(dateStr: string | null | undefined): boolean {
  if (!dateStr) return false;
  return new Date(dateStr).getTime() < Date.now();
}

function SectionHeader({ title, count }: { title: string; count: number }) {
  return (
    <div className="today-section-header">
      <h3>{title}</h3>
      {count > 0 && <span className="section-badge">{count}</span>}
    </div>
  );
}

function TodayCard({ item, onSelectLead }: { item: SavedLead; onSelectLead?: (lead: SavedLead) => void }) {
  const overdue = isOverdue(item.next_follow_up_at);
  return (
    <div
      className={`saved-card${overdue ? " saved-card--overdue" : ""}`}
      style={{ cursor: "pointer" }}
      onClick={() => onSelectLead?.(item)}
    >
      <div className="saved-card-top">
        <span className="saved-business-name">{item.business_name ?? "Unnamed business"}</span>
        <span className={`status-pill status-${item.status}`}>{item.status?.replace("_", " ")}</span>
      </div>
      {item.next_follow_up_at && (
        <p style={{ fontSize: "0.68rem", color: overdue ? "var(--accent-danger)" : "var(--text-muted)", marginTop: "0.1rem" }}>
          {overdue ? "Overdue: " : "Due: "}
          {relativeTime(item.next_follow_up_at)}
        </p>
      )}
      {(item as any).owner_name && (
        <p style={{ fontSize: "0.68rem", color: "var(--text-secondary)", marginTop: "0.1rem" }}>
          Ask for: <strong>{(item as any).owner_name}</strong>
        </p>
      )}
      {((item as any).employee_count_estimate != null || (item as any).employee_count_band) && (
        <p style={{ fontSize: "0.68rem", color: "var(--text-secondary)", marginTop: "0.1rem" }}>
          Team size: <strong>
            {(item as any).employee_count_estimate ?? "—"}
            {(item as any).employee_count_band ? ` (${(item as any).employee_count_band})` : ""}
          </strong>
        </p>
      )}
      {item.latest_note_text && (
        <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "0.1rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {item.latest_note_text}
        </p>
      )}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="saved-card saved-card--skeleton" style={{ gap: "0.5rem" }}>
      <div className="skeleton-line" style={{ height: "14px", width: "65%", borderRadius: 4 }} />
      <div className="skeleton-line" style={{ height: "11px", width: "40%", borderRadius: 4 }} />
    </div>
  );
}

export function TodayDashboard({ token, onGoToRoute, onSelectLead, onResumeRoute, isFirstRun }: Props) {
  const [data, setData] = useState<SavedLeadsTodayResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [showSkeleton, setShowSkeleton] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const retryRef = useRef<() => void>(() => {});

  useEffect(() => {
    let cancelled = false;
    const skeletonTimer = setTimeout(() => { if (!cancelled) setShowSkeleton(true); }, 200);

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await getSavedLeadsToday(token);
        if (!cancelled) { setData(response); setShowSkeleton(false); }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load today view");
          setShowSkeleton(false);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    retryRef.current = () => { setData(null); void load(); };
    void load();
    return () => {
      cancelled = true;
      clearTimeout(skeletonTimer);
    };
  }, [token]);

  if (loading && showSkeleton && !data) {
    return (
      <div>
        <div style={{ padding: "0.75rem 0.875rem 0.25rem" }}>
          <div className="skeleton-line" style={{ height: "18px", width: "55%", borderRadius: 4 }} />
        </div>
        <div className="today-section-header"><div className="skeleton-line" style={{ height: "11px", width: "30%", borderRadius: 4 }} /></div>
        <SkeletonCard /><SkeletonCard />
        <div className="today-section-header"><div className="skeleton-line" style={{ height: "11px", width: "25%", borderRadius: 4 }} /></div>
        <SkeletonCard /><SkeletonCard />
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-banner" style={{ margin: "0.75rem" }}>
        <span>{error}</span>
        <button className="btn btn-ghost btn-sm" onClick={() => retryRef.current()}>Retry</button>
      </div>
    );
  }

  if (!data) return null;

  const needsAttention = (data.overdue?.length ?? 0) + (data.due_today?.length ?? 0);

  const isEmpty =
    (data.overdue?.length ?? 0) === 0 &&
    (data.due_today?.length ?? 0) === 0 &&
    (data.high_priority_untouched?.length ?? 0) === 0 &&
    !data.recent_route;

  if (isEmpty) {
    return (
      <div className="empty-state" style={{ marginTop: "1rem" }}>
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
        </svg>
        <p className="empty-state-title">You're clear for today</p>
        <p className="empty-state-body">
          {isFirstRun
            ? "Create a route to start finding prospects along your drive."
            : "No overdue follow-ups or urgent leads."}
        </p>
        <button className="btn btn-primary btn-sm" onClick={onGoToRoute}>
          Plan a route
        </button>
      </div>
    );
  }

  return (
    <div>
      <p className="today-headline">
        {needsAttention > 0
          ? <><span>{needsAttention}</span> {needsAttention === 1 ? "thing needs" : "things need"} attention</>
          : "You're on top of it"
        }
      </p>

      {(data.overdue?.length ?? 0) > 0 && (
        <>
          <SectionHeader title="Overdue" count={data.overdue.length} />
          {data.overdue.map((item) => (
            <TodayCard key={item.id} item={item} onSelectLead={onSelectLead} />
          ))}
        </>
      )}

      {(data.due_today?.length ?? 0) > 0 && (
        <>
          <SectionHeader title="Due today" count={data.due_today.length} />
          {data.due_today.map((item) => (
            <TodayCard key={item.id} item={item} onSelectLead={onSelectLead} />
          ))}
        </>
      )}

      {(data.high_priority_untouched?.length ?? 0) > 0 && (
        <>
          <SectionHeader title="High priority untouched" count={data.high_priority_untouched.length} />
          {data.high_priority_untouched.map((item) => (
            <TodayCard key={item.id} item={item} onSelectLead={onSelectLead} />
          ))}
        </>
      )}

      {(data.blue_collar_today?.length ?? 0) > 0 && (
        <>
          <SectionHeader title="🔧 Blue-collar priorities" count={data.blue_collar_today.length} />
          {data.blue_collar_today.map((item) => (
            <TodayCard key={item.id} item={item} onSelectLead={onSelectLead} />
          ))}
        </>
      )}

      {(data.has_owner_name?.length ?? 0) > 0 && (
        <>
          <SectionHeader title="Owner name known" count={data.has_owner_name.length} />
          {data.has_owner_name.map((item) => (
            <TodayCard key={item.id} item={item} onSelectLead={onSelectLead} />
          ))}
        </>
      )}

      {data.recent_route && (
        <div className="route-resume-card">
          <div>
            <div className="route-resume-label">{data.recent_route.label}</div>
            <div className="route-resume-meta">{data.recent_route.unsaved_lead_count} unsaved leads</div>
          </div>
          {onResumeRoute && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => onResumeRoute(data.recent_route!.route_id)}
            >
              Resume
            </button>
          )}
        </div>
      )}
    </div>
  );
}
