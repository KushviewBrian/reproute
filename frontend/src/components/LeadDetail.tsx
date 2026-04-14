import { useEffect, useState } from "react";

import { createNote, listNotes, saveLead, type Lead, updateSavedLead } from "../api/client";

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

  useEffect(() => {
    if (!lead) return;
    listNotes(lead.business_id, token)
      .then((rows) => setNotes(rows))
      .catch(() => setNotes([]));
  }, [lead, token]);

  if (!lead) return null;

  async function saveWithStatus() {
    const saved = await saveLead({ business_id: lead.business_id, route_id: routeId ?? undefined }, token);
    await updateSavedLead(saved.id, { status }, token);
  }

  async function addNote() {
    if (!noteText.trim()) return;
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
