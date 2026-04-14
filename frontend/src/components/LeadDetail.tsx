import { useEffect, useState } from "react";

import { createNote, listNotes, saveLead, type Lead, updateSavedLead } from "../api/client";
import { enqueueNote, flushQueuedNotes, getQueuedCount } from "../lib/offlineQueue";

type Props = {
  lead: Lead | null;
  routeId: string | null;
  token?: string;
  onClose: () => void;
};

const STATUS_OPTIONS = ["saved", "visited", "called", "not_interested", "follow_up"];

export function LeadDetail({ lead, routeId, token, onClose }: Props) {
  const [notes, setNotes] = useState<{ id: string; note_text: string; created_at: string }[]>([]);
  const [noteText, setNoteText] = useState("");
  const [status, setStatus] = useState("saved");
  const [queueCount, setQueueCount] = useState(0);

  useEffect(() => {
    if (!lead) return;
    listNotes(lead.business_id, token)
      .then((rows) => setNotes(rows))
      .catch(() => setNotes([]));
    setQueueCount(getQueuedCount());
  }, [lead, token]);

  useEffect(() => {
    async function flushWhenOnline() {
      if (!navigator.onLine || !token) return;
      const flushed = await flushQueuedNotes(token);
      if (flushed.length > 0 && lead) {
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
    const saved = await saveLead({ business_id: lead.business_id, route_id: routeId ?? undefined }, token);
    await updateSavedLead(saved.id, { status }, token);
  }

  async function addNote() {
    if (!noteText.trim()) return;
    if (!navigator.onLine || !token) {
      enqueueNote({ business_id: lead.business_id, route_id: routeId, note_text: noteText, outcome_status: status });
      setNotes((prev) => [{ id: `queued-${Date.now()}`, note_text: `${noteText} (queued offline)`, created_at: new Date().toISOString() }, ...prev]);
      setNoteText("");
      setQueueCount(getQueuedCount());
      return;
    }
    const created = await createNote(
      { business_id: lead.business_id, route_id: routeId, note_text: noteText, outcome_status: status },
      token,
    );
    setNotes((prev) => [{ id: created.id, note_text: created.note_text, created_at: created.created_at }, ...prev]);
    setNoteText("");
  }

  return (
    <section className="panel">
      <div className="lead-top">
        <h3>{lead.name}</h3>
        <button onClick={onClose}>Close</button>
      </div>
      <p>{lead.address ?? "No address"}</p>
      <p>{lead.phone ?? "No phone"}</p>
      <p>{lead.website ?? "No website"}</p>
      <p>{lead.explanation.fit}</p>
      <p>{lead.explanation.distance}</p>
      <p>{lead.explanation.actionability}</p>

      <label>
        Status
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </label>
      <button onClick={saveWithStatus}>Save Lead</button>

      <h4>Notes</h4>
      {queueCount > 0 && <p className="meta">{queueCount} queued note(s) waiting for connection</p>}
      <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={3} />
      <button onClick={addNote}>Add Note</button>
      <ul className="note-list">
        {notes.map((n) => (
          <li key={n.id}>
            <small>{new Date(n.created_at).toLocaleString()}</small>
            <div>{n.note_text}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
