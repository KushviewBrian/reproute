import type { Lead } from "../api/client";
import { useState } from "react";

type Props = {
  leads: Lead[];
  selectedLead: Lead | null;
  onSave: (lead: Lead) => void;
  onSaveWithNote: (lead: Lead, noteText: string) => void;
  onSelect: (lead: Lead) => void;
  onAddStop: (lead: Lead) => void;
  corridorMiles: string;
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

function IconBookmarkPlus() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/><line x1="12" y1="9" x2="12" y2="15"/><line x1="9" y1="12" x2="15" y2="12"/>
    </svg>
  );
}

function IconNavigation() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="3 11 22 2 13 21 11 13 3 11"/>
    </svg>
  );
}

export function LeadList({ leads, selectedLead, onSave, onSaveWithNote, onSelect, onAddStop, corridorMiles }: Props) {
  const [draftNotes, setDraftNotes] = useState<Record<string, string>>({});

  function setDraft(businessId: string, value: string) {
    setDraftNotes((prev) => ({ ...prev, [businessId]: value }));
  }

  function submitDraft(lead: Lead) {
    const noteText = (draftNotes[lead.business_id] ?? "").trim();
    if (!noteText) return;
    onSaveWithNote(lead, noteText);
    setDraft(lead.business_id, "");
  }

  if (leads.length === 0) {
    return (
      <div className="empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <p className="empty-state-title">No prospects yet</p>
        <p className="empty-state-body">Plan a route to discover businesses within {corridorMiles} mi.</p>
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
        {leads.map((lead) => (
          <li
            key={lead.business_id}
            className={`lead-card${selectedLead?.business_id === lead.business_id ? " selected" : ""}`}
            onClick={() => onSelect(lead)}
          >
            <div className="lead-card-top">
              <span className="lead-name">{lead.name}</span>
              <span className={scoreBadgeClass(lead.final_score)}>{lead.final_score}</span>
            </div>

            <div className="lead-meta-row">
              <span className="ins-class-tag">{lead.insurance_class ?? "Unknown"}</span>
              <span className="distance-tag">
                <IconNavigation />
                {metersToFeet(lead.distance_from_route_m)}
              </span>
            </div>

            <p className="lead-explanation">
              Why it ranked: {lead.explanation.fit} · {lead.explanation.distance}
            </p>

            <p className="lead-explanation" style={{ marginTop: "-0.1rem" }}>
              Contact data: {lead.phone ? "Phone" : "No phone"} · {lead.website ? "Website" : "No website"} · Confidence: Unchecked
            </p>

            <p className="lead-explanation" style={{ marginTop: "-0.1rem" }}>
              {lead.address ?? "Address unavailable"}
            </p>

            {(lead.phone || lead.website) && (
              <div className="lead-contact-row">
                {lead.phone && <span className="lead-contact-item">{lead.phone}</span>}
                {lead.website && (
                  <a
                    className="lead-contact-item lead-contact-link"
                    href={lead.website.startsWith("http") ? lead.website : `https://${lead.website}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {lead.website.replace(/^https?:\/\//, "").replace(/\/$/, "")}
                  </a>
                )}
              </div>
            )}

            <div className="lead-card-actions">
              <div className="lead-note-row">
              <input
                type="text"
                placeholder="Quick note..."
                className="form-input lead-note-input"
                value={draftNotes[lead.business_id] ?? ""}
                onChange={(e) => setDraft(lead.business_id, e.target.value)}
                onClick={(e) => e.stopPropagation()}
                onKeyDown={(e) => {
                  if (e.key !== "Enter") return;
                  e.stopPropagation();
                  submitDraft(lead);
                }}
              />
              </div>
              <div className="lead-actions-row">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onSave(lead);
                }}
              >
                <IconBookmarkPlus />
                Save
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  submitDraft(lead);
                }}
              >
                Save + Note
              </button>
              {lead.lat != null && lead.lng != null && (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  title="Add as route stop"
                  onClick={(e) => {
                    e.stopPropagation();
                    onAddStop(lead);
                  }}
                >
                  + Stop
                </button>
              )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
