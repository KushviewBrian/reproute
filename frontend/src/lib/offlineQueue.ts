import { createNote, saveLead, updateSavedLead, type Note, type SavedLead } from "../api/client";

type QueuedNote = {
  business_id: string;
  route_id?: string | null;
  note_text: string;
  outcome_status?: string | null;
  next_action?: string | null;
  queued_at: string;
};

const KEY = "reproute_offline_note_queue_v1";
const STATUS_KEY = "reproute_offline_status_queue_v1";
export const QUEUE_UPDATED_EVENT = "reproute:queue-updated";

type QueuedStatusChange = {
  business_id: string;
  route_id?: string | null;
  status: string;
  next_follow_up_at?: string | null;
  last_contact_attempt_at?: string | null;
  queued_at: string;
};

function readQueue(): QueuedNote[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeQueue(queue: QueuedNote[]): void {
  localStorage.setItem(KEY, JSON.stringify(queue));
  window.dispatchEvent(new Event(QUEUE_UPDATED_EVENT));
}

function readStatusQueue(): QueuedStatusChange[] {
  try {
    const raw = localStorage.getItem(STATUS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeStatusQueue(queue: QueuedStatusChange[]): void {
  localStorage.setItem(STATUS_KEY, JSON.stringify(queue));
  window.dispatchEvent(new Event(QUEUE_UPDATED_EVENT));
}

export function enqueueNote(item: Omit<QueuedNote, "queued_at">): void {
  const queue = readQueue();
  queue.push({ ...item, queued_at: new Date().toISOString() });
  writeQueue(queue);
}

export function getQueuedCount(): number {
  return readQueue().length + readStatusQueue().length;
}

export async function flushQueuedNotes(token?: string): Promise<Note[]> {
  const queue = readQueue();
  if (!queue.length || !token) return [];

  const applied: Note[] = [];
  const remaining: QueuedNote[] = [];

  for (const item of queue) {
    try {
      const created = await createNote(
        {
          business_id: item.business_id,
          route_id: item.route_id,
          note_text: item.note_text,
          outcome_status: item.outcome_status,
          next_action: item.next_action,
        },
        token,
      );
      applied.push(created);
    } catch {
      remaining.push(item);
    }
  }

  writeQueue(remaining);
  return applied;
}

export function enqueueStatusChange(item: Omit<QueuedStatusChange, "queued_at">): void {
  const queue = readStatusQueue();
  queue.push({ ...item, queued_at: new Date().toISOString() });
  writeStatusQueue(queue);
}

export async function flushQueuedStatusChanges(token?: string): Promise<SavedLead[]> {
  const queue = readStatusQueue();
  if (!queue.length || !token) return [];

  const applied: SavedLead[] = [];
  const remaining: QueuedStatusChange[] = [];

  for (const item of queue) {
    try {
      const saved = await saveLead(
        { business_id: item.business_id, route_id: item.route_id },
        token,
      );
      const updated = await updateSavedLead(
        saved.id,
        {
          status: item.status,
          next_follow_up_at: item.next_follow_up_at,
          last_contact_attempt_at: item.last_contact_attempt_at,
        },
        token,
      );
      applied.push(updated);
    } catch {
      remaining.push(item);
    }
  }
  writeStatusQueue(remaining);
  return applied;
}
