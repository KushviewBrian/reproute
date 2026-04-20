import React, { useEffect, useRef, useState } from "react";
import type { Lead, ValidationStateResponse } from "../api/client";

type Props = {
  leads: Lead[];
  loading?: boolean;
  selectedLead: { business_id: string } | null;
  onSave: (lead: Lead) => void;
  onSaveWithNote: (lead: Lead, noteText: string, initialStatus?: string) => void;
  onSelect: (lead: Lead) => void;
  onAddStop: (lead: Lead) => void;
  corridorMiles: string;
  validationStates?: Record<string, ValidationStateResponse>;
  userLat?: number;
  userLng?: number;
  isFirstRun?: boolean;
};

function scoreBadgeClass(score: number) {
  if (score >= 70) return "score-badge high";
  if (score >= 45) return "score-badge mid";
  return "score-badge low";
}

function metersToFeet(m: number) {
  const ft = Math.round(m * 3.281);
  if (ft >= 5280) return `${(ft / 5280).toFixed(1)} mi`;
  return `${ft.toLocaleString()} ft`;
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

function validationBadgeProps(label: string): { className: string; text: string } {
  switch (label) {
    case "Validated":      return { className: "val-badge val-badge--validated", text: "✓ Valid" };
    case "Mostly valid":   return { className: "val-badge val-badge--mostly",    text: "~ Mostly" };
    case "Needs review":   return { className: "val-badge val-badge--review",    text: "~ Review" };
    case "Low confidence": return { className: "val-badge val-badge--low",       text: "✗ Low" };
    default:               return { className: "val-badge val-badge--unchecked", text: "· Uncheck" };
  }
}

function IconNavigation() {
  return (
    <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="3 11 22 2 13 21 11 13 3 11"/>
    </svg>
  );
}

function IconBookmarkPlus() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/><line x1="12" y1="9" x2="12" y2="15"/><line x1="9" y1="12" x2="15" y2="12"/>
    </svg>
  );
}

function SkeletonCard() {
  return (
    <li className="lead-card lead-card--skeleton" style={{ gap: "0.5rem" }}>
      <div style={{ display: "grid", gridTemplateColumns: "44px 1fr", gap: "0.625rem", alignItems: "flex-start" }}>
        <div className="skeleton-circle" style={{ width: 44, height: 44 }} />
        <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem", paddingTop: "0.25rem" }}>
          <div className="skeleton-line" style={{ height: "13px", width: "70%", borderRadius: 4 }} />
          <div className="skeleton-line" style={{ height: "11px", width: "45%", borderRadius: 4 }} />
        </div>
      </div>
      <div className="skeleton-line" style={{ height: "10px", width: "90%", borderRadius: 4 }} />
      <div className="skeleton-line" style={{ height: "10px", width: "60%", borderRadius: 4 }} />
    </li>
  );
}

export function LeadList({
  leads, loading, selectedLead, onSave, onSaveWithNote, onSelect, onAddStop,
  corridorMiles, validationStates, userLat, userLng, isFirstRun,
}: Props) {
  const [draftNotes, setDraftNotes] = useState<Record<string, string>>({});
  const [tooltipLeadId, setTooltipLeadId] = useState<string | null>(null);
  const [overflowOpenId, setOverflowOpenId] = useState<string | null>(null);
  const [expandedNoteId, setExpandedNoteId] = useState<string | null>(null);
  const animatedRef = useRef<Set<string>>(new Set());

  // Close overflow on outside click
  useEffect(() => {
    if (!overflowOpenId) return;
    function onOutside(e: MouseEvent) {
      if (!(e.target as HTMLElement).closest(".overflow-menu-wrap")) setOverflowOpenId(null);
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, [overflowOpenId]);

  function setDraft(businessId: string, value: string) {
    setDraftNotes((prev) => ({ ...prev, [businessId]: value }));
  }

  function submitDraft(lead: Lead, status?: string) {
    const noteText = (draftNotes[lead.business_id] ?? "").trim();
    onSaveWithNote(lead, noteText, status);
    setDraft(lead.business_id, "");
    setExpandedNoteId(null);
  }

  function handleScoreBadgeClick(lead: Lead, e: React.MouseEvent) {
    e.stopPropagation();
    onSelect(lead);
    if (typeof window === "undefined") return;
    const key = "reproute_score_tooltip_seen_v1";
    if (!window.localStorage.getItem(key)) {
      setTooltipLeadId(lead.business_id);
      window.localStorage.setItem(key, "1");
    }
  }

  if (loading && leads.length === 0) {
    return (
      <>
        <div className="lead-list-header">
          <h2>Prospects</h2>
        </div>
        <ul className="lead-list">
          <SkeletonCard /><SkeletonCard /><SkeletonCard />
        </ul>
      </>
    );
  }

  if (leads.length === 0) {
    return (
      <div className="empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <p className="empty-state-title">No prospects found</p>
        <p className="empty-state-body">
          {isFirstRun
            ? "Enter a route above to discover businesses near your drive."
            : `Try widening the corridor or lowering the minimum score (currently within ${corridorMiles} mi).`}
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="lead-list-header">
        <h2>Prospects</h2>
        <span className="lead-count">{leads.length}</span>
      </div>
      <ul className="lead-list">
        {leads.map((lead) => {
          const isNearby =
            userLat != null && userLng != null && lead.lat != null && lead.lng != null &&
            haversineMeters(userLat, userLng, lead.lat, lead.lng) < 402;

          const isSelected = selectedLead?.business_id === lead.business_id;
          const vs = validationStates?.[lead.business_id];
          const { className: valClass, text: valText } = validationBadgeProps(vs?.overall_label ?? "Unchecked");

          // Score badge animation — only first time this business_id is rendered
          const shouldAnimate = !animatedRef.current.has(lead.business_id);
          if (shouldAnimate) animatedRef.current.add(lead.business_id);

          const noteExpanded = expandedNoteId === lead.business_id;

          return (
            <li
              key={lead.business_id}
              className={`lead-card${isSelected ? " selected" : ""}`}
              onClick={() => onSelect(lead)}
            >
              {/* Top row: score circle + info */}
              <div className="lead-card-top">
                <div className="score-circle-wrap">
                  <span
                    className={`${scoreBadgeClass(lead.final_score)}${shouldAnimate ? " animate-in" : ""}`}
                    onClick={(e) => handleScoreBadgeClick(lead, e)}
                    title="Tap for score explanation"
                    role="button"
                    aria-label={`Score ${lead.final_score}, tap for explanation`}
                  >
                    {lead.final_score}
                  </span>
                </div>

                <div className="lead-card-info">
                  <span className="lead-name">{lead.name}</span>
                  <div className="lead-meta-row">
                    <span className="ins-class-tag">{lead.insurance_class ?? "Unknown"}</span>
                    {lead.is_blue_collar && (
                      <span className="blue-collar-tag">🔧 Blue collar</span>
                    )}
                    <span className="distance-tag">
                      <IconNavigation />
                      {metersToFeet(lead.distance_from_route_m)}
                    </span>
                    {isNearby && <span className="nearby-badge">Nearby</span>}
                  </div>
                </div>
              </div>

              {/* Score tooltip (shows once) */}
              {tooltipLeadId === lead.business_id && (
                <div className="score-tooltip">
                  Score combines fit, distance, and actionability. Higher = better route priority.
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ marginLeft: "0.5rem", padding: "0.1rem 0.35rem", fontSize: "0.65rem" }}
                    onClick={(e) => { e.stopPropagation(); setTooltipLeadId(null); }}
                  >
                    Dismiss
                  </button>
                </div>
              )}

              {/* Explanation */}
              <p className="lead-explanation">
                {lead.explanation.fit} · {lead.explanation.distance}
              </p>

              {/* Address */}
              {lead.address && (
                <p className="lead-explanation">{lead.address}</p>
              )}

              {/* Contact row: phone, website, validation */}
              <div className="lead-contact-row">
                {lead.phone && (
                  <a
                    className="lead-contact-item"
                    href={`tel:${lead.phone}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {lead.phone}
                  </a>
                )}
                {lead.website && (
                  <a
                    className="lead-contact-link"
                    href={lead.website.startsWith("http") ? lead.website : `https://${lead.website}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {lead.website.replace(/^https?:\/\//, "").replace(/\/$/, "")}
                  </a>
                )}
                <span
                  className={valClass}
                  title={vs?.overall_confidence != null ? `Confidence: ${Math.round(vs.overall_confidence)}%` : undefined}
                >
                  {valText}
                </span>
              </div>

              {/* Owner */}
              {lead.owner_name && (
                <p className="lead-explanation">
                  Ask for: <strong style={{ color: "var(--text-primary)" }}>{lead.owner_name}</strong>
                  {lead.owner_name_confidence != null && (
                    <span style={{ marginLeft: "0.3rem", fontSize: "0.62rem", color: "var(--text-muted)" }}>
                      {Math.round(lead.owner_name_confidence * 100)}%
                    </span>
                  )}
                </p>
              )}
              {(lead.employee_count_estimate != null || lead.employee_count_band) && (
                <p className="lead-explanation">
                  Team size: <strong style={{ color: "var(--text-primary)" }}>
                    {lead.employee_count_estimate != null ? lead.employee_count_estimate : "—"}
                    {lead.employee_count_band ? ` (${lead.employee_count_band})` : ""}
                  </strong>
                </p>
              )}

              {/* Note expansion area */}
              <div className={`lead-note-expand${noteExpanded ? " open" : ""}`}>
                <input
                  type="text"
                  placeholder="Quick note… (Enter to save)"
                  className="lead-note-input"
                  value={draftNotes[lead.business_id] ?? ""}
                  onChange={(e) => { e.stopPropagation(); setDraft(lead.business_id, e.target.value); }}
                  onClick={(e) => e.stopPropagation()}
                  onKeyDown={(e) => {
                    if (e.key !== "Enter") return;
                    e.stopPropagation();
                    submitDraft(lead);
                  }}
                />
              </div>

              {/* Actions */}
              <div className="lead-card-actions" onClick={(e) => e.stopPropagation()}>
                <button
                  type="button"
                  className="lead-save-btn"
                  onClick={() => onSave(lead)}
                >
                  <IconBookmarkPlus />
                  Save
                </button>

                <div className="overflow-menu-wrap">
                  <button
                    type="button"
                    className="lead-overflow-btn"
                    aria-label="More actions"
                    aria-expanded={overflowOpenId === lead.business_id}
                    onClick={() => setOverflowOpenId((prev) => prev === lead.business_id ? null : lead.business_id)}
                  >
                    ···
                  </button>
                  {overflowOpenId === lead.business_id && (
                    <ul className="overflow-menu" role="menu">
                      <li role="none">
                        <button
                          role="menuitem"
                          onClick={() => {
                            setExpandedNoteId(noteExpanded ? null : lead.business_id);
                            setOverflowOpenId(null);
                          }}
                        >
                          {noteExpanded ? "Hide note" : "Save + Note"}
                        </button>
                      </li>
                      {lead.lat != null && lead.lng != null && (
                        <li role="none">
                          <button
                            role="menuitem"
                            onClick={() => { onAddStop(lead); setOverflowOpenId(null); }}
                          >
                            + Add as stop
                          </button>
                        </li>
                      )}
                      <li role="none">
                        <button
                          role="menuitem"
                          style={{ color: "var(--accent-danger)" }}
                          onClick={() => { submitDraft(lead, "not_interested"); setOverflowOpenId(null); }}
                        >
                          Not interested
                        </button>
                      </li>
                    </ul>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </>
  );
}
