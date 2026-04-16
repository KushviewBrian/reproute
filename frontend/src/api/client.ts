export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function req<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (token) headers.Authorization = `Bearer ${token}`;

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status}: ${body}`);
  }
  if (resp.status === 204) return {} as T;
  return resp.json() as Promise<T>;
}

export type CreateRouteRequest = {
  origin_label: string;
  origin_lat: number;
  origin_lng: number;
  destination_label: string;
  destination_lat: number;
  destination_lng: number;
  corridor_width_meters: number;
  waypoints?: { label: string; lat: number; lng: number }[];
};

export type CreateRouteResponse = {
  route_id: string;
  route_distance_meters: number;
  route_duration_seconds: number;
  lead_count: number;
  route_geojson: GeoJSON.LineString;
};

export type Lead = {
  business_id: string;
  name: string;
  insurance_class: string | null;
  address: string | null;
  phone: string | null;
  website: string | null;
  final_score: number;
  fit_score: number;
  distance_score: number;
  actionability_score: number;
  distance_from_route_m: number;
  explanation: { fit: string; distance: string; actionability: string };
  lat?: number | null;
  lng?: number | null;
};

export type SavedLead = {
  id: string;
  user_id: string;
  route_id: string | null;
  business_id: string;
  status: string;
  priority: number;
  business_name: string | null;
  phone: string | null;
  address: string | null;
};

export type Note = {
  id: string;
  business_id: string;
  route_id: string | null;
  note_text: string;
  outcome_status: string | null;
  next_action: string | null;
  created_at: string;
};

export async function createRoute(payload: CreateRouteRequest, token?: string) {
  return req<CreateRouteResponse>("/routes", { method: "POST", body: JSON.stringify(payload) }, token);
}

export async function patchRoute(routeId: string, corridorWidthMeters: number, token?: string) {
  return req(`/routes/${routeId}`, {
    method: "PATCH",
    body: JSON.stringify({ corridor_width_meters: corridorWidthMeters }),
  }, token);
}

export async function fetchLeads(
  routeId: string,
  token?: string,
  opts?: { minScore?: number; hasPhone?: boolean; hasWebsite?: boolean; insuranceClass?: string[]; limit?: number },
) {
  const params = new URLSearchParams();
  params.set("min_score", String(opts?.minScore ?? 40));
  params.set("limit", String(opts?.limit ?? 50));
  if (opts?.hasPhone !== undefined) params.set("has_phone", String(opts.hasPhone));
  if (opts?.hasWebsite !== undefined) params.set("has_website", String(opts.hasWebsite));
  (opts?.insuranceClass ?? []).forEach((c) => params.append("insurance_class", c));

  return req<{ route_id: string; leads: Lead[]; total: number; filtered: number }>(
    `/routes/${routeId}/leads?${params.toString()}`,
    {},
    token,
  );
}

export async function geocode(query: string, token?: string) {
  return req<{ results: { label: string; lat: number; lng: number }[]; degraded: boolean }>(
    `/geocode?q=${encodeURIComponent(query)}`,
    {},
    token,
  );
}

export async function listSavedLeads(token?: string, status?: string) {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return req<SavedLead[]>(`/saved-leads${q}`, {}, token);
}

export async function saveLead(payload: { business_id: string; route_id?: string | null }, token?: string) {
  return req<SavedLead>("/saved-leads", { method: "POST", body: JSON.stringify(payload) }, token);
}

export async function updateSavedLead(id: string, payload: { status?: string; priority?: number }, token?: string) {
  return req<SavedLead>(`/saved-leads/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, token);
}

export async function deleteSavedLead(id: string, token?: string) {
  return req<{ message: string }>(`/saved-leads/${id}`, { method: "DELETE" }, token);
}

export async function listNotes(businessId: string, token?: string) {
  return req<Note[]>(`/notes?business_id=${encodeURIComponent(businessId)}`, {}, token);
}

export async function createNote(payload: {
  business_id: string;
  route_id?: string | null;
  note_text: string;
  outcome_status?: string | null;
  next_action?: string | null;
}, token?: string) {
  return req<Note>("/notes", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function exportRouteCsvUrl(routeId: string, savedOnly = false): string {
  return `${API_BASE}/export/routes/${routeId}/leads.csv?saved_only=${savedOnly}`;
}

export async function downloadRouteCsv(routeId: string, token?: string, savedOnly = false): Promise<void> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(exportRouteCsvUrl(routeId, savedOnly), { headers });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status}: ${body}`);
  }
  const blob = await resp.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = `route_${routeId}_leads.csv`;
  a.click();
  URL.revokeObjectURL(href);
}
