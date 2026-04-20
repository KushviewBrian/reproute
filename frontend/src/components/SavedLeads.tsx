import { useEffect, useRef, useState } from "react";

import {
  deleteSavedLead,
  downloadRouteCsv,
  downloadSavedLeadsCsv,
  downloadSavedLeadsCsvGrouped,
  listNotes,
  listSavedLeads,
  type SavedLead,
  updateSavedLead,
} from "../api/client";
import { cacheSavedLeads, readCachedSavedLeads } from "../lib/savedLeadCache";
import { enqueueStatusChange } from "../lib/offlineQueue";

type Props = {
  token?: string;
  currentRouteId: string | null;
  onAddToRoute?: (lead: SavedLead) => void;
  onCountChange?: (count: number) => void;
  onSelectLead?: (lead: SavedLead) => void;
  isFirstRun?: boolean;
};

const STATUS_OPTIONS = [
  { value: "saved",          label: "Saved" },
  { value: "visited",        label: "Visited" },
  { value: "called",         label: "Called" },
  { value: "follow_up",      label: "Follow Up" },
  { value: "not_interested", label: "Not Interested" },
] as const;

type SortMode = "due_date" | "status" | "score" | "name" | "saved_date";

const SORT_LABELS: Record<SortMode, string> = {
  due_date:   "Due date",
  status:     "Status",
  score:      "Score",
  name:       "Name",
  saved_date: "Saved date",
};

const STATUS_PRIORITY: Record<string, number> = {
  follow_up: 0, saved: 1, called: 2, visited: 3, not_interested: 4,
};

function sortSavedLeads(items: SavedLead[], mode: SortMode = "due_date"): SavedLead[] {
  const now = Date.now();
  return [...items].sort((a, b) => {
    if (mode === "name") return (a.business_name ?? "").localeCompare(b.business_name ?? "");
    if (mode === "score") return (b.final_score ?? -1) - (a.final_score ?? -1);
    if (mode === "saved_date") return (b.id > a.id ? 1 : b.id < a.id ? -1 : 0);
    if (mode === "status") {
      const pa = STATUS_PRIORITY[a.status] ?? 99;
      const pb = STATUS_PRIORITY[b.status] ?? 99;
      if (pa !== pb) return pa - pb;
      return (b.final_score ?? -1) - (a.final_score ?? -1);
    }
    // due_date (default)
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
    return (b.final_score ?? -1) - (a.final_score ?? -1);
  });
}

function IconDownload() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  );
}

function IconSort() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="3" y1="6" x2="21" y2="6"/><line x1="7" y1="12" x2="17" y2="12"/><line x1="11" y1="18" x2="13" y2="18"/>
    </svg>
  );
}

function IconTrash() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
    </svg>
  );
}

function SkeletonCard() {
  return (
    <li className="saved-card saved-card--skeleton" style={{ gap: "0.5rem" }}>
      <div className="skeleton-line" style={{ height: "13px", width: "60%", borderRadius: 4 }} />
      <div className="skeleton-line" style={{ height: "11px", width: "35%", borderRadius: 4 }} />
    </li>
  );
}

function relativeDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const diff = new Date(iso).getTime() - Date.now();
  const days = Math.round(diff / 86400000);
  if (days < 0) return `${Math.abs(days)}d overdue`;
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  return `in ${days}d`;
}

export function SavedLeads({ token, currentRouteId, onAddToRoute, onCountChange, onSelectLead, isFirstRun }: Props) {
  const [items, setItems] = useState<SavedLead[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sortMode, setSortMode] = useState<SortMode>("due_date");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchVisible, setSearchVisible] = useState(false);
  const [cacheMeta, setCacheMeta] = useState<string | null>(null);
  const [flashIds, setFlashIds] = useState<Set<string>>(new Set());
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [sortOpen, setSortOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const sortRef = useRef<HTMLDivElement>(null);

  // Swipe tracking
  const touchStartRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load() {
      try {
        const base = await listSavedLeads(token, statusFilter || undefined);
        if (cancelled) return;
        const hydrated = token
          ? await Promise.all(
              base.map(async (item) => {
                if (item.latest_note_text) return item;
                try {
                  const notes = await listNotes(item.business_id, token);
                  return notes.length ? { ...item, latest_note_text: notes[0].note_text, latest_note_created_at: notes[0].created_at } : item;
                } catch { return item; }
              }),
            )
          : base;
        if (cancelled) return;
        const sorted = sortSavedLeads(hydrated, sortMode);
        cacheSavedLeads(statusFilter, sorted);
        setItems(sorted);
        setCacheMeta(null);
        onCountChange?.(sorted.length);
      } catch {
        const cached = readCachedSavedLeads(statusFilter);
        if (cancelled) return;
        if (cached) {
          const sorted = sortSavedLeads(cached.items, sortMode);
          setItems(sorted);
          setCacheMeta(`Cached ${new Date(cached.updatedAt).toLocaleString()}`);
          onCountChange?.(sorted.length);
        } else {
          setItems([]);
          onCountChange?.(0);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => { cancelled = true; };
  }, [token, statusFilter]);

  // Re-sort in-place when sort mode changes (no refetch)
  useEffect(() => {
    setItems((prev) => sortSavedLeads(prev, sortMode));
  }, [sortMode]);

  // Clear search when filter changes
  useEffect(() => { setSearchQuery(""); }, [statusFilter]);

  // Close menus on outside click
  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (exportMenuOpen && !exportMenuRef.current?.contains(e.target as Node)) setExportMenuOpen(false);
      if (sortOpen && !sortRef.current?.contains(e.target as Node)) setSortOpen(false);
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, [exportMenuOpen, sortOpen]);

  async function handleStatusChange(id: string, businessId: string, routeId: string | null, newStatus: string) {
    const item = items.find((it) => it.id === id);
    if (!item) return;

    setFlashIds((prev) => new Set([...prev, id]));
    setTimeout(() => setFlashIds((prev) => { const n = new Set(prev); n.delete(id); return n; }), 220);

    if (!navigator.onLine || !token) {
      enqueueStatusChange({ business_id: businessId, route_id: routeId, status: newStatus, next_follow_up_at: item.next_follow_up_at });
      setItems((prev) => sortSavedLeads(prev.map((it) => it.id === id ? { ...it, status: newStatus } : it), sortMode));
      return;
    }
    try {
      const updated = await updateSavedLead(id, { status: newStatus }, token);
      setItems((prev) => {
        const next = sortSavedLeads(prev.map((it) => it.id === id ? { ...it, status: updated.status } : it), sortMode);
        cacheSavedLeads(statusFilter, next);
        return next;
      });
    } catch {
      // revert
      setItems((prev) => [...prev]);
    }
  }

  async function handleFollowUpChange(id: string, value: string) {
    const iso = value ? `${value}T12:00:00Z` : null;
    const item = items.find((it) => it.id === id);
    if (!navigator.onLine || !token) {
      if (item) enqueueStatusChange({ business_id: item.business_id, route_id: item.route_id, status: item.status, next_follow_up_at: iso });
      setItems((prev) => {
        const next = sortSavedLeads(prev.map((it) => it.id === id ? { ...it, next_follow_up_at: iso } : it), sortMode);
        cacheSavedLeads(statusFilter, next);
        return next;
      });
      return;
    }
    const updated = await updateSavedLead(id, { next_follow_up_at: iso }, token);
    setItems((prev) => {
      const next = sortSavedLeads(prev.map((it) => it.id === id ? { ...it, next_follow_up_at: updated.next_follow_up_at } : it), sortMode);
      cacheSavedLeads(statusFilter, next);
      return next;
    });
  }

  async function handleDelete(id: string) {
    await deleteSavedLead(id, token);
    setItems((prev) => {
      const next = sortSavedLeads(prev.filter((it) => it.id !== id), sortMode);
      onCountChange?.(next.length);
      cacheSavedLeads(statusFilter, next);
      return next;
    });
  }

  async function handleExportAll() {
    setExporting(true);
    try { await downloadSavedLeadsCsv(token); } finally { setExporting(false); setExportMenuOpen(false); }
  }

  async function handleExportGrouped() {
    setExporting(true);
    try { await downloadSavedLeadsCsvGrouped("insurance_class", token); } finally { setExporting(false); setExportMenuOpen(false); }
  }

  async function handleExportRoute() {
    if (!currentRouteId) return;
    setExporting(true);
    try { await downloadRouteCsv(currentRouteId, token, true); } finally { setExporting(false); setExportMenuOpen(false); }
  }

  // Swipe handlers
  function onTouchStart(e: React.TouchEvent) {
    touchStartRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
  }

  function onTouchEnd(e: React.TouchEvent, item: SavedLead) {
    if (!touchStartRef.current) return;
    const dx = e.changedTouches[0].clientX - touchStartRef.current.x;
    const dy = e.changedTouches[0].clientY - touchStartRef.current.y;
    touchStartRef.current = null;
    if (Math.abs(dy) > 20) return; // vertical scroll
    if (dx > 60) {
      // Advance status
      const idx = STATUS_OPTIONS.findIndex((s) => s.value === item.status);
      const next = STATUS_OPTIONS[Math.min(idx + 1, STATUS_OPTIONS.length - 1)];
      if (next.value !== item.status) void handleStatusChange(item.id, item.business_id, item.route_id, next.value);
    } else if (dx < -60) {
      void handleStatusChange(item.id, item.business_id, item.route_id, "not_interested");
    }
  }

  // Filtered display items
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(searchQuery), 150);
    return () => clearTimeout(t);
  }, [searchQuery]);

  const displayItems = debouncedSearch
    ? items.filter((it) =>
        [it.business_name, it.address, (it as any).owner_name, it.latest_note_text, it.phone].some(
          (f) => typeof f === "string" && f.toLowerCase().includes(debouncedSearch.toLowerCase()),
        ),
      )
    : items;

  // Per-status counts
  const counts: Record<string, number> = {};
  for (const item of items) counts[item.status] = (counts[item.status] ?? 0) + 1;

  return (
    <>
      {/* Header */}
      <div className="saved-header">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h2>Saved Leads</h2>
          <div style={{ display: "flex", gap: "0.375rem" }}>
            {/* Sort */}
            <div className="sort-popover-wrap" ref={sortRef}>
              <button
                className="btn btn-icon btn-sm"
                aria-label="Sort leads"
                title="Sort"
                onClick={() => setSortOpen((v) => !v)}
              >
                <IconSort />
              </button>
              {sortOpen && (
                <div className="sort-popover">
                  {(Object.keys(SORT_LABELS) as SortMode[]).map((mode) => (
                    <button
                      key={mode}
                      className={`popover-radio-btn${sortMode === mode ? " selected" : ""}`}
                      onClick={() => { setSortMode(mode); setSortOpen(false); }}
                    >
                      <span className="popover-radio-dot" />
                      {SORT_LABELS[mode]}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Export */}
            <div className="export-menu-wrap" ref={exportMenuRef}>
              <button
                className="btn btn-icon btn-sm"
                aria-label="Export leads"
                title="Export"
                onClick={() => setExportMenuOpen((v) => !v)}
                disabled={exporting}
              >
                <IconDownload />
              </button>
              {exportMenuOpen && (
                <ul className="export-menu-popup" style={{ listStyle: "none", padding: "0.25rem 0" }}>
                  <li>
                    <button className="popover-radio-btn" style={{ width: "100%" }} onClick={handleExportAll}>
                      All leads CSV
                    </button>
                  </li>
                  <li>
                    <button className="popover-radio-btn" style={{ width: "100%" }} onClick={handleExportGrouped}>
                      By type CSV
                    </button>
                  </li>
                  {currentRouteId && (
                    <li>
                      <button className="popover-radio-btn" style={{ width: "100%" }} onClick={handleExportRoute}>
                        Route CSV
                      </button>
                    </li>
                  )}
                </ul>
              )}
            </div>
          </div>
        </div>

        {/* Search */}
        {searchVisible && (
          <input
            className="saved-search-input"
            type="search"
            placeholder="Search saved leads…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoFocus
          />
        )}

        {/* Status tabs */}
        <div className="status-tabs">
          <button
            className={`status-tab-btn${statusFilter === "" ? " active" : ""}`}
            onClick={() => { setStatusFilter(""); setSearchVisible(false); }}
          >
            All
            <span className="status-tab-count">{items.length}</span>
          </button>
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              className={`status-tab-btn${statusFilter === opt.value ? " active" : ""}`}
              onClick={() => setStatusFilter(opt.value)}
            >
              {opt.label}
              {counts[opt.value] ? <span className="status-tab-count">{counts[opt.value]}</span> : null}
            </button>
          ))}
        </div>

        {cacheMeta && (
          <p style={{ fontSize: "0.67rem", color: "var(--text-muted)" }}>{cacheMeta}</p>
        )}
      </div>

      {/* List controls row */}
      <div className="saved-list-controls">
        <span style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>
          {displayItems.length} lead{displayItems.length !== 1 ? "s" : ""}
          {debouncedSearch && ` for "${debouncedSearch}"`}
        </span>
        <div className="saved-list-right">
          <button
            className={`btn btn-icon btn-sm${searchVisible ? " active" : ""}`}
            aria-label="Search leads"
            title="Search"
            onClick={() => { setSearchVisible((v) => !v); if (searchVisible) setSearchQuery(""); }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          </button>
        </div>
      </div>

      {/* Loading skeletons */}
      {loading && displayItems.length === 0 && (
        <ul style={{ listStyle: "none", padding: 0 }}>
          <SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard />
        </ul>
      )}

      {/* Empty state */}
      {!loading && displayItems.length === 0 && (
        <div className="empty-state" style={{ marginTop: "2rem" }}>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
          <p className="empty-state-title">No saved leads</p>
          <p className="empty-state-body">
            {debouncedSearch
              ? `No results for "${debouncedSearch}"`
              : statusFilter
              ? `No leads with status "${STATUS_OPTIONS.find(s => s.value === statusFilter)?.label ?? statusFilter}"`
              : isFirstRun
              ? "Save prospects from the Route tab to track your follow-ups here."
              : "All caught up."}
          </p>
          {debouncedSearch && (
            <button className="btn btn-ghost btn-sm" onClick={() => setSearchQuery("")}>Clear search</button>
          )}
        </div>
      )}

      {/* Lead list */}
      {displayItems.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {displayItems.map((it) => {
            const overdue = it.next_follow_up_at && new Date(it.next_follow_up_at).getTime() < Date.now();
            const relDate = relativeDate(it.next_follow_up_at);
            return (
              <li
                key={it.id}
                className={`saved-card${overdue ? " saved-card--overdue" : ""}${flashIds.has(it.id) ? " saved-card--flash" : ""}`}
                style={{ cursor: "pointer" }}
                onClick={() => onSelectLead?.(it)}
                onTouchStart={onTouchStart}
                onTouchEnd={(e) => onTouchEnd(e, it)}
              >
                <div className="saved-card-top">
                  <button
                    className="saved-business-name"
                    onClick={(e) => { e.stopPropagation(); onSelectLead?.(it); }}
                  >
                    {it.business_name ?? it.business_id.slice(0, 8) + "…"}
                  </button>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.3rem", flexShrink: 0 }}>
                    {it.is_blue_collar && <span style={{ fontSize: "0.65rem" }}>🔧</span>}
                    <span className={`status-pill status-${it.status}`}>
                      {STATUS_OPTIONS.find(s => s.value === it.status)?.label ?? it.status}
                    </span>
                  </div>
                </div>

                {/* Inline status dots */}
                <div className="status-dots" onClick={(e) => e.stopPropagation()}>
                  {STATUS_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      className={`status-dot-btn dot-${opt.value}${it.status === opt.value ? " current" : ""}`}
                      title={opt.label}
                      aria-label={`Set status: ${opt.label}`}
                      onClick={() => void handleStatusChange(it.id, it.business_id, it.route_id, opt.value)}
                    />
                  ))}
                  {relDate && (
                    <span style={{ marginLeft: "0.375rem", fontSize: "0.62rem", color: overdue ? "var(--accent-danger)" : "var(--text-muted)" }}>
                      {relDate}
                    </span>
                  )}
                </div>

                {(it as any).owner_name && (
                  <p style={{ fontSize: "0.68rem", color: "var(--text-secondary)" }}>
                    Ask for: <strong>{(it as any).owner_name}</strong>
                  </p>
                )}

                {it.address && (
                  <p style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>{it.address}</p>
                )}

                {it.latest_note_text && (
                  <p style={{ fontSize: "0.68rem", color: "var(--text-secondary)", lineHeight: 1.4, overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as const }}>
                    {it.latest_note_text}
                  </p>
                )}

                {/* Follow-up date + actions */}
                <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", marginTop: "0.25rem" }} onClick={(e) => e.stopPropagation()}>
                  <input
                    type="date"
                    className="form-input"
                    style={{ flex: 1, fontSize: "0.68rem", padding: "0.25rem 0.4rem", maxWidth: "9rem" }}
                    value={it.next_follow_up_at ? new Date(it.next_follow_up_at).toISOString().slice(0, 10) : ""}
                    onChange={(e) => void handleFollowUpChange(it.id, e.target.value)}
                    title="Follow-up date"
                    aria-label="Follow-up date"
                  />
                  {onAddToRoute && (
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{ fontSize: "0.68rem", padding: "0.2rem 0.4rem" }}
                      onClick={() => onAddToRoute(it)}
                    >
                      + Stop
                    </button>
                  )}
                  <button
                    className="btn btn-icon btn-sm"
                    style={{ color: "var(--text-muted)" }}
                    aria-label="Delete lead"
                    onClick={() => void handleDelete(it.id)}
                  >
                    <IconTrash />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
