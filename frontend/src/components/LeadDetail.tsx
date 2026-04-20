import { useEffect, useState } from "react";

import {
  createNote,
  getValidationState,
  listNotes,
  pinValidationField,
  saveLead,
  triggerValidation,
  type Lead,
  type SavedLead,
  type ValidationStateResponse,
  updateSavedLead,
} from "../api/client";
import {
  QUEUE_UPDATED_EVENT,
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
  // Phase 10
  is_blue_collar?: boolean;
  owner_name?: string | null;
  owner_name_source?: string | null;
  owner_name_confidence?: number | null;
  employee_count_estimate?: number | null;
  employee_count_band?: string | null;
  employee_count_source?: string | null;
  employee_count_confidence?: number | null;
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
    is_blue_collar: l.is_blue_collar,
    owner_name: l.owner_name,
    owner_name_source: l.owner_name_source,
    owner_name_confidence: l.owner_name_confidence,
    employee_count_estimate: l.employee_count_estimate,
    employee_count_band: l.employee_count_band,
    employee_count_source: l.employee_count_source,
    employee_count_confidence: l.employee_count_confidence,
  };
}

export function savedLeadToDetail(s: SavedLead): DetailLead {
  return {
    business_id: s.business_id,
    name: s.business_name ?? s.business_id.slice(0, 8) + "…",
    insurance_class: null,
    address: s.address,
    phone: s.phone,
    website: s.website,
    final_score: s.final_score ?? null,
    fit_score: null,
    distance_score: null,
    actionability_score: null,
    explanation: null,
    is_blue_collar: (s as any).is_blue_collar ?? false,
    owner_name: (s as any).owner_name ?? null,
    owner_name_source: (s as any).owner_name_source ?? null,
    owner_name_confidence: (s as any).owner_name_confidence ?? null,
    employee_count_estimate: (s as any).employee_count_estimate ?? null,
    employee_count_band: (s as any).employee_count_band ?? null,
    employee_count_source: (s as any).employee_count_source ?? null,
    employee_count_confidence: (s as any).employee_count_confidence ?? null,
  };
}

type Props = {
  lead: DetailLead | null;
  routeId: string | null;
  token?: string;
  refreshToken?: () => Promise<string | undefined>;
  onClose: () => void;
  userPosition?: { lat: number; lng: number } | null;
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

export function LeadDetail({ lead, routeId, token, refreshToken, onClose, userPosition: _userPosition }: Props) {
  const [notes, setNotes] = useState<
    { id: string; note_text: string; created_at: string; outcome_status?: string | null; next_action?: string | null }[]
  >([]);
  const [noteText, setNoteText] = useState("");
  const [noteOutcome, setNoteOutcome] = useState("saved");
  const [nextAction, setNextAction] = useState("");
  const [status, setStatus] = useState("saved");
  const [queueCount, setQueueCount] = useState(0);
  const [saving, setSaving] = useState(false);
  const [validation, setValidation] = useState<ValidationStateResponse | null>(null);
  const [validationLoading, setValidationLoading] = useState(false);
  const [validationTriggering, setValidationTriggering] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [callLogged, setCallLogged] = useState(false);
  const [ownerEditing, setOwnerEditing] = useState(false);
  const [ownerDraft, setOwnerDraft] = useState("");
  const [employeeEditing, setEmployeeEditing] = useState(false);
  const [employeeEstimateDraft, setEmployeeEstimateDraft] = useState("");
  const [employeeBandDraft, setEmployeeBandDraft] = useState("");

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
    function refreshQueuedCount() {
      setQueueCount(getQueuedCount());
    }
    window.addEventListener(QUEUE_UPDATED_EVENT, refreshQueuedCount);
    return () => window.removeEventListener(QUEUE_UPDATED_EVENT, refreshQueuedCount);
  }, []);

  useEffect(() => {
    if (!lead || !token) {
      setValidation(null);
      return;
    }
    let cancelled = false;
    setValidationLoading(true);
    setValidationError(null);
    getValidationState(lead.business_id, token)
      .then((data) => { if (!cancelled) setValidation(data); })
      .catch(() => {
        if (!cancelled) setValidation(null);
        // Silently ignore load errors — 404 (not in scope yet) and network errors
        // (Render cold start) both just show the placeholder
      })
      .finally(() => { if (!cancelled) setValidationLoading(false); });
    return () => { cancelled = true; };
  }, [lead?.business_id, token]);

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

  async function handleValidate() {
    if (!lead) return;
    setValidationTriggering(true);
    setValidationError(null);
    try {
      const freshToken = (refreshToken ? await refreshToken() : token) ?? token;
      if (!freshToken) return;
      // Wake Render before the heavy POST — cold starts can take 30s+
      try {
        await fetch(`${(await import("../api/client")).API_BASE}/health`, { signal: AbortSignal.timeout(35000) });
      } catch { /* ignore — POST will fail-fast with a clear error if still down */ }
      await triggerValidation(lead.business_id, freshToken);
      // Poll until run is done/failed or 10 attempts (~30s)
      for (let i = 0; i < 10; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        const data = await getValidationState(lead.business_id, freshToken);
        setValidation(data);
        if (data.run?.status === "done" || data.run?.status === "failed" || data.run?.status === "partial") break;
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Validation failed";
      if (msg.startsWith("404")) {
        // not in scope — shouldn't happen if lead is saved, ignore
      } else if (msg.startsWith("429")) {
        setValidationError("Validation rate limit reached — try again tomorrow.");
      } else if (msg.toLowerCase().includes("network error")) {
        setValidationError("Server is waking up — wait 30s and try again.");
      } else {
        setValidationError(msg);
      }
    } finally {
      setValidationTriggering(false);
    }
  }

  async function handlePin(fieldName: string, pinned: boolean) {
    if (!lead || !token) return;
    try {
      await pinValidationField(lead.business_id, fieldName, pinned, token);
      const data = await getValidationState(lead.business_id, token);
      setValidation(data);
    } catch {
      // pin failure is non-critical; silently ignore
    }
  }

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
  const geoHref = lead.lat != null && lead.lng != null
    ? `geo:${lead.lat},${lead.lng}?q=${encodeURIComponent(lead.address ?? `${lead.lat},${lead.lng}`)}`
    : null;

  const score = lead.final_score ?? 0;
  const scoreTier = score >= 70 ? "high" : score >= 45 ? "mid" : "low";

  async function saveOwnerName() {
    if (!lead || !token) return;
    try {
      const saved = await saveLead({ business_id: lead.business_id, route_id: routeId ?? undefined }, token);
      await updateSavedLead(saved.id, { owner_name: ownerDraft || undefined } as any, token);
    } catch { /* non-critical */ }
    setOwnerEditing(false);
  }

  async function clearOwnerName() {
    if (!lead || !token) return;
    try {
      const saved = await saveLead({ business_id: lead.business_id, route_id: routeId ?? undefined }, token);
      await updateSavedLead(saved.id, { owner_name: null }, token);
    } catch { /* non-critical */ }
    setOwnerEditing(false);
  }

  async function saveEmployeeCount() {
    if (!lead || !token) return;
    const parsed = employeeEstimateDraft.trim() ? Number(employeeEstimateDraft.trim()) : null;
    try {
      const saved = await saveLead({ business_id: lead.business_id, route_id: routeId ?? undefined }, token);
      await updateSavedLead(
        saved.id,
        {
          employee_count_estimate: Number.isFinite(parsed) ? parsed : null,
          employee_count_band: employeeBandDraft.trim() || null,
        },
        token,
      );
    } catch { /* non-critical */ }
    setEmployeeEditing(false);
  }

  async function clearEmployeeCount() {
    if (!lead || !token) return;
    try {
      const saved = await saveLead({ business_id: lead.business_id, route_id: routeId ?? undefined }, token);
      await updateSavedLead(saved.id, { employee_count_estimate: null, employee_count_band: null }, token);
    } catch { /* non-critical */ }
    setEmployeeEditing(false);
  }

  return (
    <div className="detail-pane">
      <div className="detail-drag-handle" />

      {/* Header: score + name + close */}
      <div className="detail-header">
        <div className="detail-header-main">
          <span className={`detail-score-badge score-badge ${scoreTier}`}>{lead.final_score ?? "—"}</span>
          <div className="detail-title-group">
            <h3 className="detail-title">{lead.name}</h3>
            <p className="detail-subtitle">
              {lead.insurance_class ?? "Unknown class"}
              {lead.is_blue_collar && (
                <span className="blue-collar-tag" style={{ marginLeft: "0.4rem" }}>🔧 Blue collar</span>
              )}
            </p>
          </div>
        </div>
        <button className="btn btn-icon btn-sm" onClick={onClose} title="Close" aria-label="Close detail panel">
          <IconX />
        </button>
      </div>

      {/* Status segmented control */}
      <div className="status-segmented">
        {STATUS_OPTIONS.map((s) => (
          <button
            key={s.value}
            type="button"
            className={`status-seg-btn${status === s.value ? ` active active-${s.value}` : ""}`}
            onClick={() => setStatus(s.value)}
            aria-pressed={status === s.value}
          >
            {s.label}
          </button>
        ))}
      </div>
      <div style={{ padding: "0 1rem 0.75rem" }}>
        <button
          className="btn btn-primary btn-sm"
          style={{ width: "100%" }}
          onClick={saveWithStatus}
          disabled={saving}
        >
          {saving ? <><span className="spinner" /> Saving…</> : <><IconBookmark /> Save &amp; set status</>}
        </button>
      </div>

      {/* Scrollable body */}
      <div className="detail-body">

        {/* Contact section */}
        <div className="detail-section detail-full-col">
          <p className="detail-section-title">Contact info</p>

          {lead.address && (
            <div className="detail-info-row">
              <IconMapPin />
              {geoHref ? (
                <a href={geoHref} className="detail-info-link">{lead.address}</a>
              ) : (
                <span>{lead.address}</span>
              )}
            </div>
          )}

          {lead.phone ? (
            <div className="detail-info-row detail-info-row--action">
              <IconPhone />
              <a href={phoneHref!} className="detail-info-link" style={{ flex: 1 }}>{lead.phone}</a>
              {!callLogged ? (
                <a
                  href={phoneHref!}
                  className="btn btn-ghost btn-sm detail-action-btn"
                  onClick={() => setCallLogged(true)}
                >
                  Call
                </a>
              ) : (
                <span className="detail-call-logged">Logged ✓</span>
              )}
            </div>
          ) : (
            <div className="detail-info-row detail-info-missing">
              <IconPhone />
              <span>No phone number</span>
            </div>
          )}

          {lead.website ? (
            <div className="detail-info-row detail-info-row--action">
              <IconGlobe />
              <a href={websiteHref!} target="_blank" rel="noreferrer" className="detail-info-link" style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {lead.website.replace(/^https?:\/\//, "").replace(/\/$/, "")}
              </a>
              <a
                href={websiteHref!}
                target="_blank"
                rel="noreferrer"
                className="btn btn-ghost btn-sm detail-action-btn"
              >
                Visit
              </a>
            </div>
          ) : (
            <div className="detail-info-row detail-info-missing">
              <IconGlobe />
              <span>No website</span>
            </div>
          )}

          {/* Owner row */}
          <div className="detail-info-row detail-owner-row">
            <span className="detail-owner-label">Owner</span>
            {ownerEditing ? (
              <div className="detail-owner-edit">
                <input
                  type="text"
                  className="form-input form-input--sm"
                  value={ownerDraft}
                  placeholder="Owner name"
                  autoFocus
                  onChange={(e) => setOwnerDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveOwnerName();
                    if (e.key === "Escape") setOwnerEditing(false);
                  }}
                />
                <button className="btn btn-primary btn-sm" onClick={saveOwnerName}>Save</button>
                <button className="btn btn-ghost btn-sm" onClick={clearOwnerName}>Clear</button>
                <button className="btn btn-ghost btn-sm" onClick={() => setOwnerEditing(false)}>Cancel</button>
              </div>
            ) : (
              <div className="detail-owner-value">
                {lead.owner_name ? (
                  <>
                    <strong style={{ color: "var(--text-primary)" }}>{lead.owner_name}</strong>
                    {lead.owner_name_source && lead.owner_name_source !== "manual" && (
                      <span className="detail-owner-source">via {lead.owner_name_source.replace(/_/g, " ")}</span>
                    )}
                    {lead.owner_name_confidence != null && (
                      <span className="detail-owner-conf">{Math.round(lead.owner_name_confidence * 100)}%</span>
                    )}
                  </>
                ) : (
                  <span style={{ color: "var(--text-muted)" }}>Unknown</span>
                )}
                {token && (
                  <button
                    className="btn-link detail-owner-edit-btn"
                    onClick={() => { setOwnerDraft(lead.owner_name ?? ""); setOwnerEditing(true); }}
                  >
                    Edit
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Employee count row */}
          <div className="detail-info-row detail-owner-row">
            <span className="detail-owner-label">Employees</span>
            {employeeEditing ? (
              <div className="detail-owner-edit">
                <input
                  type="number"
                  className="form-input form-input--sm"
                  value={employeeEstimateDraft}
                  placeholder="Estimate"
                  min={1}
                  onChange={(e) => setEmployeeEstimateDraft(e.target.value)}
                />
                <input
                  type="text"
                  className="form-input form-input--sm"
                  value={employeeBandDraft}
                  placeholder="Band (e.g. 11-50)"
                  onChange={(e) => setEmployeeBandDraft(e.target.value)}
                />
                <button className="btn btn-primary btn-sm" onClick={saveEmployeeCount}>Save</button>
                <button className="btn btn-ghost btn-sm" onClick={clearEmployeeCount}>Clear</button>
                <button className="btn btn-ghost btn-sm" onClick={() => setEmployeeEditing(false)}>Cancel</button>
              </div>
            ) : (
              <div className="detail-owner-value">
                {lead.employee_count_estimate != null || lead.employee_count_band ? (
                  <>
                    <strong style={{ color: "var(--text-primary)" }}>
                      {lead.employee_count_estimate != null ? `${lead.employee_count_estimate}` : "Estimate unavailable"}
                      {lead.employee_count_band ? ` (${lead.employee_count_band})` : ""}
                    </strong>
                    {lead.employee_count_source && (
                      <span className="detail-owner-source">via {lead.employee_count_source.replace(/_/g, " ")}</span>
                    )}
                    {lead.employee_count_confidence != null && (
                      <span className="detail-owner-conf">{Math.round(lead.employee_count_confidence * 100)}%</span>
                    )}
                  </>
                ) : (
                  <span style={{ color: "var(--text-muted)" }}>Unknown</span>
                )}
                {token && (
                  <button
                    className="btn-link detail-owner-edit-btn"
                    onClick={() => {
                      setEmployeeEstimateDraft(lead.employee_count_estimate != null ? String(lead.employee_count_estimate) : "");
                      setEmployeeBandDraft(lead.employee_count_band ?? "");
                      setEmployeeEditing(true);
                    }}
                  >
                    Edit
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Score breakdown */}
        {(lead.fit_score != null || lead.final_score != null) && (
          <div className="detail-section detail-full-col">
            <details className="score-breakdown-details">
              <summary className="detail-section-title score-breakdown-summary">
                Score breakdown
                <span className="score-breakdown-total">{lead.final_score ?? "—"}</span>
              </summary>
              {lead.fit_score != null && lead.distance_score != null && lead.actionability_score != null ? (
                <div className="score-bar-list">
                  {[
                    { label: "Fit", value: lead.fit_score, note: lead.explanation?.fit },
                    { label: "Distance", value: lead.distance_score, note: lead.explanation?.distance },
                    { label: "Actionability", value: lead.actionability_score, note: lead.explanation?.actionability },
                  ].map(({ label, value, note }) => (
                    <div key={label} className="score-bar-row">
                      <div className="score-bar-meta">
                        <span className="score-bar-label">{label}</span>
                        <span className="score-bar-value">{value}</span>
                      </div>
                      <div className="score-bar-track">
                        <div className="score-bar-fill" style={{ width: `${Math.min(value, 100)}%` }} />
                      </div>
                      {note && <p className="score-bar-note">{note}</p>}
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", padding: "0.5rem 0" }}>
                  Overall score: {lead.final_score ?? "—"}
                </p>
              )}
            </details>
          </div>
        )}

        {/* Data validation */}
        <div className="detail-section detail-full-col">
          <details className="validation-details" open={!!validation}>
            <summary style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer" }}>
              <span className="detail-section-title" style={{ pointerEvents: "none" }}>
                Data validation
                {validation?.overall_label && (
                  <span className="val-summary-chip" style={{ marginLeft: "0.5rem" }}>{validation.overall_label}</span>
                )}
              </span>
              {token && (
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={(e) => { e.preventDefault(); handleValidate(); }}
                  disabled={validationTriggering || !lead}
                  style={{ fontSize: "0.7rem", padding: "0.2rem 0.5rem", pointerEvents: "all" }}
                >
                  {validationTriggering ? <><span className="spinner" /> Checking…</> : "Validate now"}
                </button>
              )}
            </summary>

            {validationError && (
              <p style={{ fontSize: "0.7rem", color: "var(--accent-danger)", marginTop: "0.375rem" }}>{validationError}</p>
            )}

            {validation && validation.fields.length > 0 ? (
              <div className="val-field-list" style={{ marginTop: "0.5rem" }}>
                {validation.fields.map((f) => (
                  <div key={f.field_name} className="val-field-row">
                    <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
                      <span className="val-field-name">{f.field_name}</span>
                      <span className={`val-state-chip val-state-chip--${f.state ?? "unknown"}`}>
                        {f.state ?? "unknown"}
                      </span>
                      {f.confidence != null && (
                        <span style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>{Math.round(f.confidence)}%</span>
                      )}
                    </div>
                    {f.value_normalized && f.value_normalized !== f.value_current && (
                      <p style={{ fontSize: "0.67rem", color: "var(--text-muted)", marginTop: "0.15rem" }}>
                        Normalized: {f.value_normalized}
                      </p>
                    )}
                    {token && (
                      <details className="val-field-advanced">
                        <summary style={{ fontSize: "0.65rem", color: "var(--text-muted)", cursor: "pointer" }}>Advanced</summary>
                        {f.last_checked_at && (
                          <p style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>
                            Checked {new Date(f.last_checked_at).toLocaleDateString()}
                            {f.next_check_at ? ` · Next ${new Date(f.next_check_at).toLocaleDateString()}` : ""}
                          </p>
                        )}
                        {f.failure_class && (
                          <p style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>Failure: {f.failure_class}</p>
                        )}
                        <button
                          className="btn-link"
                          style={{ fontSize: "0.65rem", marginTop: "0.15rem" }}
                          onClick={() => handlePin(f.field_name, !f.pinned_by_user)}
                        >
                          {f.pinned_by_user ? "Unpin (auto-recheck enabled)" : "Pin (skip auto-recheck)"}
                        </button>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              !validationLoading && (
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.375rem" }}>
                  {token ? "No validation data yet. Save this lead first, then tap \"Validate now\"." : "Sign in to validate this lead."}
                </p>
              )
            )}
          </details>
        </div>

        {/* Notes */}
        <div className="detail-section detail-full-col">
          <p className="detail-section-title">Notes</p>

          {queueCount > 0 && (
            <div className="offline-banner">
              <IconWifi />
              {queueCount} unsynced change{queueCount > 1 ? "s" : ""} — will sync when online
            </div>
          )}

          <div className="notes-compose">
            <textarea
              className="notes-textarea"
              value={noteText}
              placeholder="Add a note… (⌘↵ to save)"
              rows={2}
              onChange={(e) => setNoteText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) addNote(); }}
            />
            <div className="notes-compose-footer">
              <select
                className="form-select form-select--sm"
                value={noteOutcome}
                onChange={(e) => setNoteOutcome(e.target.value)}
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
              <input
                type="text"
                className="form-input form-input--sm"
                style={{ flex: 1, minWidth: 0 }}
                value={nextAction}
                placeholder="Next action…"
                onChange={(e) => setNextAction(e.target.value)}
              />
              <button
                className="btn btn-primary btn-sm"
                disabled={!noteText.trim()}
                onClick={addNote}
                aria-label="Save note"
              >
                <IconSend />
              </button>
            </div>
          </div>

          <div className="notes-area">
            {notes.length === 0 && (
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>No notes yet.</p>
            )}
            {notes.map((n) => (
              <div key={n.id} className="note-item">
                <p className="note-timestamp">{new Date(n.created_at).toLocaleString()}</p>
                <p className="note-text">{n.note_text}</p>
                {(n.outcome_status || n.next_action) && (
                  <p className="note-meta">
                    {n.outcome_status && <span className="note-outcome-chip">{n.outcome_status.replace(/_/g, " ")}</span>}
                    {n.next_action && <span style={{ color: "var(--text-muted)", fontSize: "0.67rem" }}>Next: {n.next_action}</span>}
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
