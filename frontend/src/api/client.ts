function resolveApiBase(): string {
  const configured = (import.meta.env.VITE_API_BASE_URL ?? "").trim();
  if (configured) return configured;

  if (typeof window === "undefined") {
    return "";
  }
  return window.location.origin;
}

export const API_BASE = resolveApiBase();

async function req<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (token) headers.Authorization = `Bearer ${token}`;

  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    if (!API_BASE) {
      throw new Error("Network error: API base URL is not configured. Set VITE_API_BASE_URL.");
    }
    if (typeof window !== "undefined" && window.location.protocol === "https:" && API_BASE.startsWith("http://")) {
      throw new Error(`Network error: API is HTTP on an HTTPS page (${API_BASE}). Set VITE_API_BASE_URL to an HTTPS backend URL.`);
    }
    throw new Error(`Network error: unable to reach API at ${API_BASE}`);
  }

  if (!resp.ok) {
    let detail = "";
    const contentType = resp.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const data = await resp.json().catch(() => null);
      detail = data?.detail || data?.message || "";
    } else {
      detail = await resp.text();
    }

    if (resp.status === 401) {
      throw new Error("401: authentication expired, sign in again");
    }
    if (resp.status === 429) {
      throw new Error("429: rate limit exceeded, wait and retry");
    }
    throw new Error(`${resp.status}: ${detail || "request failed"}`);
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
  score_version?: "v1" | "v2";
  rank_reason_v2?: string[] | null;
  lat?: number | null;
  lng?: number | null;
  // Phase 10
  is_blue_collar: boolean;
  owner_name: string | null;
  owner_name_source: string | null;
  owner_name_confidence: number | null;
  employee_count_estimate: number | null;
  employee_count_band: string | null;
  employee_count_source: string | null;
  employee_count_confidence: number | null;
};

export type SavedLead = {
  id: string;
  user_id: string;
  route_id: string | null;
  business_id: string;
  status: string;
  priority: number;
  next_follow_up_at?: string | null;
  last_contact_attempt_at?: string | null;
  business_name: string | null;
  phone: string | null;
  website: string | null;
  address: string | null;
  route_label?: string | null;
  final_score?: number | null;
  latest_note_text?: string | null;
  latest_note_created_at?: string | null;
  // Phase 10
  is_blue_collar: boolean;
  owner_name: string | null;
  owner_name_source: string | null;
  owner_name_confidence: number | null;
  employee_count_estimate: number | null;
  employee_count_band: string | null;
  employee_count_source: string | null;
  employee_count_confidence: number | null;
  insurance_class: string | null;
  operating_status: string | null;
  validation_state?: string | null;
  saved_at?: string | null;
};

export type SavedLeadsTodayResponse = {
  overdue: SavedLead[];
  due_today: SavedLead[];
  high_priority_untouched: SavedLead[];
  recent_route: {
    route_id: string;
    label: string;
    unsaved_lead_count: number;
  } | null;
  // Phase 10
  blue_collar_today: SavedLead[];
  has_owner_name: SavedLead[];
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

export type LeadGroup = { key: string; label: string; count: number; leads: Lead[] };

export async function fetchLeads(
  routeId: string,
  token?: string,
  opts?: {
    minScore?: number;
    hasPhone?: boolean;
    hasWebsite?: boolean;
    insuranceClass?: string[];
    limit?: number;
    scoreVersion?: "v1" | "v2";
    // Phase 10
    sortBy?: "score" | "blue_collar_score" | "name" | "distance" | "validation_confidence" | "owner_name";
    sortDir?: "asc" | "desc";
    blueCollar?: boolean;
    hasOwnerName?: boolean;
    hasEmployeeCount?: boolean;
    employeeCountBand?: string;
    scoreBand?: "high" | "medium" | "low";
    minValidationConfidence?: number;
    validationState?: string;
    operatingStatus?: string;
    groupBy?: string;
  },
) {
  const params = new URLSearchParams();
  params.set("min_score", String(opts?.minScore ?? 40));
  params.set("limit", String(opts?.limit ?? 50));
  if (opts?.hasPhone !== undefined) params.set("has_phone", String(opts.hasPhone));
  if (opts?.hasWebsite !== undefined) params.set("has_website", String(opts.hasWebsite));
  if (opts?.scoreVersion) params.set("score_version", opts.scoreVersion);
  (opts?.insuranceClass ?? []).forEach((c) => params.append("insurance_class", c));
  if (opts?.sortBy) params.set("sort_by", opts.sortBy);
  if (opts?.sortDir) params.set("sort_dir", opts.sortDir);
  if (opts?.blueCollar !== undefined) params.set("blue_collar", String(opts.blueCollar));
  if (opts?.hasOwnerName !== undefined) params.set("has_owner_name", String(opts.hasOwnerName));
  if (opts?.hasEmployeeCount !== undefined) params.set("has_employee_count", String(opts.hasEmployeeCount));
  if (opts?.employeeCountBand) params.set("employee_count_band", opts.employeeCountBand);
  if (opts?.scoreBand) params.set("score_band", opts.scoreBand);
  if (opts?.minValidationConfidence != null) params.set("min_validation_confidence", String(opts.minValidationConfidence));
  if (opts?.validationState) params.set("validation_state", opts.validationState);
  if (opts?.operatingStatus) params.set("operating_status", opts.operatingStatus);
  if (opts?.groupBy) params.set("group_by", opts.groupBy);

  return req<{ route_id: string; leads: Lead[]; total: number; filtered: number; groups?: LeadGroup[] }>(
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

export async function reverseGeocode(lat: number, lng: number, token?: string) {
  return req<{ results: { label: string; lat: number; lng: number }[]; degraded: boolean }>(
    `/geocode?lat=${encodeURIComponent(String(lat))}&lng=${encodeURIComponent(String(lng))}`,
    {},
    token,
  );
}

export type ListSavedLeadsOptions = {
  status?: string;
  dueBefore?: string;
  limit?: number;
  offset?: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  blueCollar?: boolean;
  hasOwnerName?: boolean;
  hasEmployeeCount?: boolean;
  employeeCountBand?: string;
  operatingStatus?: string;
  scoreBand?: "high" | "medium" | "low";
  hasNotes?: boolean;
  savedAfter?: string;
  savedBefore?: string;
  overdueOnly?: boolean;
  untouchedOnly?: boolean;
  groupBy?: string;
};

export async function listSavedLeads(
  token?: string,
  statusOrOptions?: string | ListSavedLeadsOptions,
  dueBefore?: string,
): Promise<SavedLead[]> {
  const params = new URLSearchParams();
  if (typeof statusOrOptions === "string") {
    if (statusOrOptions) params.set("status", statusOrOptions);
    if (dueBefore) params.set("due_before", dueBefore);
  } else if (statusOrOptions != null) {
    const o = statusOrOptions;
    if (o.status) params.set("status", o.status);
    if (o.dueBefore) params.set("due_before", o.dueBefore);
    if (o.limit != null) params.set("limit", String(o.limit));
    if (o.offset != null) params.set("offset", String(o.offset));
    if (o.sortBy) params.set("sort_by", o.sortBy);
    if (o.sortDir) params.set("sort_dir", o.sortDir);
    if (o.blueCollar != null) params.set("blue_collar", String(o.blueCollar));
    if (o.hasOwnerName != null) params.set("has_owner_name", String(o.hasOwnerName));
    if (o.hasEmployeeCount != null) params.set("has_employee_count", String(o.hasEmployeeCount));
    if (o.employeeCountBand) params.set("employee_count_band", o.employeeCountBand);
    if (o.operatingStatus) params.set("operating_status", o.operatingStatus);
    if (o.scoreBand) params.set("score_band", o.scoreBand);
    if (o.hasNotes != null) params.set("has_notes", String(o.hasNotes));
    if (o.savedAfter) params.set("saved_after", o.savedAfter);
    if (o.savedBefore) params.set("saved_before", o.savedBefore);
    if (o.overdueOnly != null) params.set("overdue_only", String(o.overdueOnly));
    if (o.untouchedOnly != null) params.set("untouched_only", String(o.untouchedOnly));
    if (o.groupBy) params.set("group_by", o.groupBy);
  }
  const q = params.toString() ? `?${params.toString()}` : "";
  return req<SavedLead[]>(`/saved-leads${q}`, {}, token);
}

export async function getSavedLeadsToday(token?: string) {
  return req<SavedLeadsTodayResponse>("/saved-leads/today", {}, token);
}

export async function saveLead(payload: { business_id: string; route_id?: string | null }, token?: string) {
  return req<SavedLead>("/saved-leads", { method: "POST", body: JSON.stringify(payload) }, token);
}

export async function updateSavedLead(
  id: string,
  payload: {
    status?: string;
    priority?: number;
    next_follow_up_at?: string | null;
    last_contact_attempt_at?: string | null;
    owner_name?: string | null;
    employee_count_estimate?: number | null;
    employee_count_band?: string | null;
  },
  token?: string,
) {
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

// ── Validation ────────────────────────────────────────────────────────────────

export type ValidationFieldState = {
  field_name: string;
  state: string | null;
  confidence: number | null;
  failure_class: string | null;
  value_current: string | null;
  value_normalized: string | null;
  last_checked_at: string | null;
  next_check_at: string | null;
  evidence_json: Record<string, unknown> | null;
  pinned_by_user: boolean;
};

export type ValidationRunState = {
  run_id: string;
  business_id: string;
  status: string;
  requested_checks: string[] | null;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
};

export type ValidationStateResponse = {
  run: ValidationRunState | null;
  fields: ValidationFieldState[];
  overall_confidence: number | null;
  overall_label: string;
};

export async function getValidationState(businessId: string, token?: string): Promise<ValidationStateResponse> {
  return req<ValidationStateResponse>(`/leads/${encodeURIComponent(businessId)}/validation`, {}, token);
}

export async function getValidationStatesBatch(
  businessIds: string[],
  token?: string,
): Promise<Record<string, ValidationStateResponse>> {
  return req<Record<string, ValidationStateResponse>>(
    "/leads/validation/batch",
    { method: "POST", body: JSON.stringify({ business_ids: businessIds }) },
    token,
  );
}

export async function triggerValidation(businessId: string, token?: string): Promise<{ run_id: string; status: string }> {
  return req<{ run_id: string; status: string }>(
    `/leads/${encodeURIComponent(businessId)}/validate`,
    { method: "POST", body: JSON.stringify({ requested_checks: ["website", "phone", "owner_name"] }) },
    token,
  );
}

export async function pinValidationField(businessId: string, fieldName: string, pinned: boolean, token?: string): Promise<{ field_name: string; pinned_by_user: boolean }> {
  return req<{ field_name: string; pinned_by_user: boolean }>(
    `/leads/${encodeURIComponent(businessId)}/validation/${encodeURIComponent(fieldName)}`,
    { method: "PATCH", body: JSON.stringify({ pinned }) },
    token,
  );
}

export async function downloadSavedLeadsCsvGrouped(groupBy: string, token?: string): Promise<void> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(`${API_BASE}/export/saved-leads.csv?group_by=${encodeURIComponent(groupBy)}`, { headers });
  if (!resp.ok) { const body = await resp.text(); throw new Error(`${resp.status}: ${body}`); }
  const blob = await resp.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href; a.download = `saved_leads_by_${groupBy}.csv`; a.click();
  URL.revokeObjectURL(href);
}

export async function downloadSavedLeadsCsv(token?: string): Promise<void> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(`${API_BASE}/export/saved-leads.csv`, { headers });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status}: ${body}`);
  }
  const blob = await resp.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = "saved_leads_export.csv";
  a.click();
  URL.revokeObjectURL(href);
}
