import type { SavedLead } from "../api/client";

type SavedLeadCacheEnvelope = {
  status: string;
  items: SavedLead[];
  updatedAt: string;
};

const KEY_PREFIX = "reproute_saved_leads_v1:";

export function cacheSavedLeads(status: string, items: SavedLead[]): void {
  const payload: SavedLeadCacheEnvelope = {
    status,
    items,
    updatedAt: new Date().toISOString(),
  };
  localStorage.setItem(`${KEY_PREFIX}${status || "all"}`, JSON.stringify(payload));
}

export function readCachedSavedLeads(status: string): SavedLeadCacheEnvelope | null {
  try {
    const raw = localStorage.getItem(`${KEY_PREFIX}${status || "all"}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SavedLeadCacheEnvelope;
    if (!Array.isArray(parsed.items)) return null;
    return parsed;
  } catch {
    return null;
  }
}
