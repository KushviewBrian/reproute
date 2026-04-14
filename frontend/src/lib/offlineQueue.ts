import { createNote, type Note } from "../api/client";

type QueuedNote = {
  business_id: string;
  route_id?: string | null;
  note_text: string;
  outcome_status?: string | null;
  next_action?: string | null;
  queued_at: string;
};

const KEY = "reproute_offline_note_queue_v1";

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
}

export function enqueueNote(item: Omit<QueuedNote, "queued_at">): void {
  const queue = readQueue();
  queue.push({ ...item, queued_at: new Date().toISOString() });
  writeQueue(queue);
}

export function getQueuedCount(): number {
  return readQueue().length;
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
