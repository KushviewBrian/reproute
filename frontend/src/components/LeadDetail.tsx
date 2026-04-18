import { useEffect, useState } from "react";

import { createNote, listNotes, saveLead, type Lead, type SavedLead, updateSavedLead } from "../api/client";
import {
  enqueueNote,
  enqueueStatusChange,
  flushQueuedNotes,
  flushQueuedStatusChanges,
  getQueuedCount,
} from "../lib/offlineQueue";

export type DetailLead = {
  business_id: string;
  name: string;
  insurance_class: string | null;
  address: string | null;
  phone: string | null;
  website: string | null;
  final_score: number | null;
  fit_score: number | null;
  distance_score: number | null;
  actionability_score: number | null;
  explanation: { fit: string; distance: string; actionability: string } | null;
  lat?: number | null;
  lng?: number | null;
};

export function leadToDetail(l: Lead): DetailLead {
  return {
    business_id: l.business_id,
    name: l.name,
    insurance_class: l.insurance_class,
    address: l.address,
    phone: l.phone,
    website: l.website,
    final_score: l.final_score,
    fit_score: l.fit_score,
    distance_score: l.distance_score,
    actionability_score: l.actionability_score,
    explanation: l.explanation,
    lat: l.lat,
    lng: l.lng,
  };
}

export function savedLeadToDetail(s: SavedLead): DetailLead {
  return {
    business_id: s.business_id,
    name: s.business_name ?? s.business_id.slice(0, 8) + "…",
    insurance_class: null,
    address: s.address,
    phone: s.phone,
    website: null,
    final_score: s.final_score ?? null,
    fit_score: null,
    distance_score: null,
    actionability_score: null,
    explanation: null,
  };
}

type Props = {
  lead: DetailLead | null;
  routeId: string | null;
  token?: string;
  onClose: () => void;
};

const STATUS_OPTIONS = [
  { value: "saved",          label: "Saved" },
  { value: "visited",        label: "Visited" },
  { value: "called",         label: "Called" },
  { value: "follow_up",      label: "Follow Up" },
  { value: "not_interested", label: "Not Interested" },
];

function IconX() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  );
}

function IconPhone() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 13a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 9.91a16 16 0 0 0 6.29 6.29l.98-.98a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
    </svg>
  );
}

function IconGlobe() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
  );
}

function IconMapPin() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
    </svg>
  );
}

function IconWifi() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M10.71 5.05A16 16 0 0 1 22.56 9"/><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/>
    </svg>
  );
}

function IconSend() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
    </svg>
  );
}

function IconBookmark() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
    </svg>
  );
}

export function LeadDetail({ lead, routeId, token, onClose }: Props) {
  const [notes, setNotes] = useState<
    { id: string; note_text: string; created_at: string; outcome_status?: string | null; next_action?: string | null }[]
  >([]);
  const [noteText, setNoteText] = useState("");
  const [noteOutcome, setNoteOutcome] = useState("saved");
  const [nextAction, setNextAction] = useState("");
  const [status, setStatus] = useState("saved");
  const [queueCount, setQueueCount] = useState(0);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!lead) return;
    listNotes(lead.business_id, token)
      .then((rows) => setNotes(rows))
      .catch(() => setNotes([]));
    setNoteOutcome(status);
    setNextAction("");
    setQueueCount(getQueuedCount());
  }, [lead, token]);

  useEffect(() => {
    async function flushWhenOnline() {
      if (!navigator.onLine || !token) return;
      const [flushedNotes] = await Promise.all([
        flushQueuedNotes(token),
        flushQueuedStatusChanges(token),
      ]);
      if (flushedNotes.length > 0 && lead) {
        const latest = await listNotes(lead.business_id, token).catch(() => []);
        setNotes(latest);
      }
      setQueueCount(getQueuedCount());
    }
    flushWhenOnline();
    window.addEventListener("online", flushWhenOnline);
    return () => window.removeEventListener("online", flushWhenOnline);
  }, [lead, token]);

  if (!lead) return null;

  async function saveWithStatus() {
    if (!lead) return;
    setSaving(true);
    try {
      const nowIso = new Date().toISOString();
      const shouldSetContactAttempt = status !== "saved";
      if (!navigator.onLine || !token) {
        enqueueStatusChange({
          business_id: lead.business_id,
          route_id: routeId,
          status,
          last_contact_attempt_at: shouldSetContactAttempt ? nowIso : undefined,
        });
        setQueueCount(getQueuedCount());
        return;
      }
      const saved = await saveLead({ business_id: lead.business_id, route_id: routeId ?? undefined }, token);
      await updateSavedLead(
        saved.id,
        {
          status,
          last_contact_attempt_at: shouldSetContactAttempt ? nowIso : undefined,
        },
        token,
      );
    } finally {
      setSaving(false);
    }
  }

  async function addNote() {
    if (!lead) return;
    if (!noteText.trim()) return;
    if (!navigator.onLine || !token) {
      enqueueNote({
        business_id: lead.business_id,
        route_id: routeId,
        note_text: noteText,
        outcome_status: noteOutcome,
        next_action: nextAction || undefined,
      });
      setNotes((prev) => [
        {
          id: `queued-${Date.now()}`,
          note_text: `${noteText} (queued)`,
          created_at: new Date().toISOString(),
          outcome_status: noteOutcome,
          next_action: nextAction || null,
        },
        ...prev,
      ]);
      setNoteText("");
      setNextAction("");
      setQueueCount(getQueuedCount());
      return;
    }
    const created = await createNote(
      {
        business_id: lead.business_id,
        route_id: routeId,
        note_text: noteText,
        outcome_status: noteOutcome,
        next_action: nextAction || undefined,
      },
      token,
    );
    setNotes((prev) => [
      {
        id: created.id,
        note_text: created.note_text,
        created_at: created.created_at,
        outcome_status: created.outcome_status,
        next_action: created.next_action,
      },
      ...prev,
    ]);
    setNoteText("");
    setNextAction("");
  }

  const phoneHref = lead.phone ? `tel:${lead.phone.replace(/\D/g, "")}` : null;
  const websiteHref = lead.website
    ? lead.website.startsWith("http") ? lead.website : `https://${lead.website}`
    : null;

  return (
    <div className="detail-pane">
      {/* Header */}
      <div className="detail-header">
        <div className="detail-title-group">
          <h3 className="detail-title">{lead.name}</h3>
          <p className="detail-subtitle">{lead.insurance_class ?? "Unknown class"}</p>
        </div>
        <button className="btn btn-icon btn-sm" onClick={onClose} title="Close">
          <IconX />
        </button>
      </div>

      {/* Scrollable body */}
      <div className="detail-body">
        {/* Contact info */}
        <div className="detail-section">
          <p className="detail-section-title">Contact</p>
          <p style={{ fontSize: "0.72rem", color: "var(--gray-500)", marginBottom: "0.25rem" }}>
            Contact availability: {lead.phone ? "Phone found" : "Phone missing"} · {lead.website ? "Website found" : "Website missing"}
          </p>
          {lead.address && (
            <div className="detail-info-row">
              <IconMapPin />
              <span>{lead.address}</span>
            </div>
          )}
          {lead.phone && (
            <div className="detail-info-row">
              <IconPhone />
              {phoneHref ? (
                <a href={phoneHref}>{lead.phone}</a>
              ) : (
                <span>{lead.phone}</span>
              )}
            </div>
          )}
          {lead.website && (
            <div className="detail-info-row">
              <IconGlobe />
              {websiteHref ? (
                <a href={websiteHref} target="_blank" rel="noreferrer">{lead.website}</a>
              ) : (
                <span>{lead.website}</span>
              )}
            </div>
          )}
          {!lead.address && !lead.phone && !lead.website && (
            <p style={{ fontSize: "0.75rem", color: "var(--gray-400)" }}>No contact info available</p>
          )}
        </div>

        {/* Score breakdown */}
        <div className="detail-section">
          <p className="detail-section-title">Score breakdown</p>
          <p style={{ fontSize: "0.72rem", color: "var(--gray-500)", marginBottom: "0.25rem" }}>
            Confidence status: Unchecked
          </p>
          {lead.fit_score != null && lead.distance_score != null && lead.actionability_score != null ? (
            <>
              <div className="score-breakdown">
                <div className="score-mini">
                  <div className="score-mini-label">Fit</div>
                  <div className="score-mini-value">{lead.fit_score}</div>
                </div>
                <div className="score-mini">
                  <div className="score-mini-label">Distance</div>
                  <div className="score-mini-value">{lead.distance_score}</div>
                </div>
                <div className="score-mini">
                  <div className="score-mini-label">Action</div>
                  <div className="score-mini-value">{lead.actionability_score}</div>
                </div>
              </div>
              {lead.explanation && (
                <p style={{ fontSize: "0.7rem", color: "var(--gray-500)", lineHeight: 1.5, marginTop: "0.25rem" }}>
                  Why it ranked: {lead.explanation.fit} · {lead.explanation.distance} · {lead.explanation.actionability}
                </p>
              )}
            </>
          ) : (
            <p style={{ fontSize: "0.72rem", color: "var(--gray-400)" }}>
              {lead.final_score != null ? `Overall score: ${lead.final_score}` : "Score not available for this context"}
            </p>
          )}
        </div>

        {/* Save with status */}
        <div className="detail-section">
          <p className="detail-section-title">Status</p>
          <div className="status-select-row">
            <select
              className="form-select"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
            <button
              className="btn btn-primary btn-sm"
              style={{ whiteSpace: "nowrap" }}
              onClick={saveWithStatus}
              disabled={saving}
            >
              {saving ? <span className="spinner" /> : <IconBookmark />}
              Save
            </button>
          </div>
        </div>

        {/* Notes */}
        <div className="detail-section detail-full-col">
          <p className="detail-section-title">Notes</p>

          {queueCount > 0 && (
            <div className="offline-banner">
              <IconWifi />
              {queueCount} unsynced change{queueCount > 1 ? "s" : ""} queued — will sync when online
            </div>
          )}

          <div className="notes-input-row">
            <textarea
              className="notes-textarea"
              value={noteText}
              placeholder="Add a note…"
              rows={2}
              onChange={(e) => setNoteText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) addNote(); }}
            />
            <select
              className="form-select"
              style={{ minWidth: "9rem", alignSelf: "flex-end" }}
              value={noteOutcome}
              onChange={(e) => setNoteOutcome(e.target.value)}
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
            <input
              type="text"
              className="form-input"
              style={{ minWidth: "10rem", alignSelf: "flex-end" }}
              value={nextAction}
              placeholder="Next action (optional)"
              onChange={(e) => setNextAction(e.target.value)}
            />
            <button
              className="btn btn-primary btn-sm"
              style={{ alignSelf: "flex-end" }}
              disabled={!noteText.trim()}
              onClick={addNote}
            >
              <IconSend />
            </button>
          </div>

          <div className="notes-area">
            {notes.length === 0 && (
              <p style={{ fontSize: "0.75rem", color: "var(--gray-400)" }}>No notes yet.</p>
            )}
            {notes.map((n) => (
              <div key={n.id} className="note-item">
                <p className="note-timestamp">{new Date(n.created_at).toLocaleString()}</p>
                <p className="note-text">{n.note_text}</p>
                {(n.outcome_status || n.next_action) && (
                  <p className="note-timestamp" style={{ marginTop: "0.2rem" }}>
                    {n.outcome_status ? `Outcome: ${n.outcome_status}` : ""}
                    {n.outcome_status && n.next_action ? " · " : ""}
                    {n.next_action ? `Next: ${n.next_action}` : ""}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
