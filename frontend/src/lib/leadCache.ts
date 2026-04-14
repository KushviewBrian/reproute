import type { Lead } from "../api/client";

type CacheEnvelope = {
  routeId: string;
  leads: Lead[];
  updatedAt: string;
};

const KEY_PREFIX = "reproute_route_leads_v1:";

export function cacheRouteLeads(routeId: string, leads: Lead[]): void {
  const payload: CacheEnvelope = { routeId, leads, updatedAt: new Date().toISOString() };
  localStorage.setItem(`${KEY_PREFIX}${routeId}`, JSON.stringify(payload));
}

export function readCachedRouteLeads(routeId: string): CacheEnvelope | null {
  try {
    const raw = localStorage.getItem(`${KEY_PREFIX}${routeId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CacheEnvelope;
    if (!Array.isArray(parsed.leads)) return null;
    return parsed;
  } catch {
    return null;
  }
}
