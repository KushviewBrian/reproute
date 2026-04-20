# Data Usage Optimization Plan — RepRoute Deployment Servers

> **Goal**: Minimize egress bandwidth, external API calls, and redundant data transfer
> across backend ↔ external APIs, backend ↔ frontend, and frontend ↔ map tiles.

---

## Executive Summary

The current deployment has **13 actionable optimization opportunities** across four categories:
external API call reduction, frontend↔backend payload optimization, caching/CDN improvements,
and infrastructure-level compression. The three highest-impact items are:

1. **N+1 validation API calls** — up to 100 sequential HTTP requests per lead list load
2. **No geocode result caching** — every keystroke in origin/destination fields hits Photon API
3. **No response compression** — all API responses and static assets served uncompressed

Implementing all recommendations could reduce deployment egress by an estimated **60–80%**
and cut external API dependency calls by **50–70%**.

---

## Category 1: External API Call Reduction

### 1.1 Redis-cache geocode results ⭐ HIGH IMPACT

**Current state** (`geocode_service.py`):
- Every geocode call hits `https://photon.komoot.io/api/` with no caching.
- `RouteForm.tsx` fires geocode on every keystroke (300ms debounce) for **both** origin and
  destination fields — up to ~2 calls/second during typing.
- Rate limited to 30/min per user, but identical queries from different users are not shared.

**Recommendation**:
- Add Redis caching with key `geocode:<query_or_lat_lng>`, TTL ~7 days.
- Photon results for well-known locations rarely change.
- Estimated reduction: **70–90% of geocode API calls**.

**Implementation sketch** (`backend/app/services/geocode_service.py`):
```python
# Before calling _fetch_geocode():
cache_key = f"geocode:{hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()}"
cached = await redis_client.get(cache_key)
if cached:
    return json.loads(cached), False
# ... after successful fetch:
await redis_client.set(cache_key, json.dumps(payload), ex=604800)  # 7 days
```

### 1.2 Redis-cache OSM enrichment results ⭐ MEDIUM IMPACT

**Current state** (`osm_enrichment_service.py`):
- Overpass API is queried for each business enrichment; results are written to DB columns
  but the raw Overpass response is never cached.
- If enrichment fails and is retried, the full Overpass query runs again.

**Recommendation**:
- Cache Overpass responses in Redis with key `osm:<lat>:<lng>:<name_hash>`, TTL = freshness_days.
- This prevents redundant Overpass calls when the same business appears in multiple routes.

### 1.3 Reuse httpx.AsyncClient across requests ⭐ MEDIUM IMPACT

**Current state**:
- `_call_ors_with_retry`, `_fetch_geocode`, `_call_overpass_with_retry` each create a new
  `async with httpx.AsyncClient()` per request — meaning a fresh TCP+TLS handshake every time.

**Recommendation**:
- Create module-level singleton `httpx.AsyncClient` instances (or a shared client pool)
  that persist across requests.
- Use FastAPI lifespan to create/dispose.

```python
# backend/app/utils/http_clients.py
from httpx import AsyncClient

ors_client: AsyncClient | None = None
geocode_client: AsyncClient | None = None

async def init_http_clients():
    global ors_client, geocode_client
    ors_client = AsyncClient(timeout=10)
    geocode_client = AsyncClient(timeout=5)

async def close_http_clients():
    await ors_client.aclose()
    await geocode_client.aclose()
```

### 1.4 Cache website validation results by URL ⭐ LOW-MEDIUM IMPACT

**Current state** (`validation_service.py` → `_validate_website`):
- Every validation run downloads the full HTML of the business website.
- Same URL validated multiple times (different users, re-validation) re-downloads everything.

**Recommendation**:
- Cache HTTP validation results (status_code, content_length, owner extraction) in Redis
  with key `val_web:<url_hash>`, TTL = `next_check_days` from the FieldResult.
- Skip HTTP fetch if a fresh cache entry exists.

---

## Category 2: Frontend ↔ Backend Payload Optimization

### 2.1 Batch validation state endpoint ⭐⭐ HIGHEST IMPACT

**Current state** (`App.tsx` lines 191–201, `SavedLeads.tsx` lines 131–142):
```typescript
// Fires ONE getValidationState() call PER LEAD — 50-100 parallel requests!
Promise.allSettled(
  sorted.map((l) =>
    getValidationState(l.business_id, token).then((vs) => ({ id: l.business_id, vs })),
  ),
);
```
- With 100 leads, this creates **100 concurrent API requests**.
- Each request queries the DB for validation run + field validations.
- Same pattern repeated in `SavedLeads.tsx`.

**Recommendation**:
- Add a batch endpoint: `POST /leads/validation/batch` accepting `{ business_ids: string[] }`.
- Returns `Record<business_id, ValidationStateResponse>`.
- Frontend makes **1 request** instead of N.

**Implementation sketch**:
```python
# backend/app/api/routes/validation.py
@validation_batch_router.post("/batch")
async def batch_validation_state(
    payload: BatchValidationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, ValidationStateResponse]:
    # Single query for all businesses at once
    results = await batch_get_validation_states(db, payload.business_ids)
    return results
```

### 2.2 Batch notes endpoint for SavedLeads ⭐ HIGH IMPACT

**Current state** (`SavedLeads.tsx` lines 108–123):
```typescript
const hydrated = await Promise.all(
  base.map(async (item) => {
    if (item.latest_note_text) return item;
    const notes = await listNotes(item.business_id, token);  // N+1!
    // ...
  }),
);
```
- For each saved lead missing `latest_note_text`, fires individual `GET /notes?business_id=...`.

**Recommendation**:
- Add a batch notes endpoint: `GET /notes/batch?business_ids=id1,id2,id3`
- Or better: ensure the `GET /saved-leads` response **always includes** `latest_note_text`
  via a SQL JOIN/subquery, eliminating the need for the N+1 hydration entirely.

### 2.3 Add field selection to leads endpoint ⭐ MEDIUM IMPACT

**Current state** (`lead_service.py` → `fetch_leads`):
- Always queries 20+ columns including v1 AND v2 scores, both explanation JSONs, etc.
- Frontend's `Lead` type only uses a subset.

**Recommendation**:
- Add optional `fields` query parameter to `GET /routes/{id}/leads`.
- Default to the current full response for backward compatibility.
- Frontend can request minimal fields for list view, full fields for detail view.
- Estimated payload reduction: **30–50%** for list views.

### 2.4 Compress ORS response before DB storage ⭐ LOW-MEDIUM IMPACT

**Current state** (`Route.ors_response_json`):
- Stores the **entire ORS GeoJSON response** as JSONB.
- The route geometry is also stored separately as `route_geom` (Geography LINESTRING).
- ORS responses can be 10–100KB+ with full coordinate arrays.

**Recommendation**:
- Strip the geometry coordinates from `ors_response_json` before storage (they're redundant
  with `route_geom`).
- Only keep `properties.summary` and any metadata needed.
- Or remove `ors_response_json` entirely and reconstruct from `route_geom` + summary fields.

### 2.5 Add pagination metadata to avoid over-fetching ⭐ LOW IMPACT

**Current state**:
- Frontend requests `limit: 100` leads by default.
- No cursor-based pagination — always fetches from offset 0.

**Recommendation**:
- Implement cursor-based pagination for leads.
- Frontend initially loads page 1 (20 leads), then loads more on scroll.
- Reduces initial payload from ~100 leads to ~20.

---

## Category 3: Caching & CDN Improvements

### 3.1 Add gzip/brotli compression to API responses ⭐⭐ HIGH IMPACT

**Current state**:
- Backend (`main.py`) has **no compression middleware**.
- JSON API responses with 50–100 lead objects can be 50–200KB uncompressed.
- JSON compresses extremely well (typically 70–85% reduction).

**Recommendation**:
```python
# backend/app/main.py — add before other middleware
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=500)
```
- Estimated bandwidth reduction for API responses: **70–85%**.
- For even better results, consider `brotli` middleware.

### 3.2 Enable nginx gzip and caching headers ⭐ HIGH IMPACT

**Current state** (`frontend/nginx.conf`):
- Minimal config with no gzip, no cache headers, no asset versioning support.

**Recommendation**:
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml image/svg+xml;
    gzip_min_length 500;

    # Static assets with content hash — aggressive caching
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # HTML — short cache, must revalidate
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "public, max-age=300, must-revalidate";
    }
}
```

### 3.3 Switch from raster to vector map tiles ⭐⭐ HIGH IMPACT

**Current state** (`MapPanel.tsx`):
- Falls back to `https://tile.openstreetmap.org/{z}/{x}/{y}.png` raster tiles.
- Each raster tile is ~15–40KB; a typical map session loads 50–200 tiles = **1–8MB**.
- `VITE_MAP_PMTILES_URL` is **empty** in the Render deployment config.

**Recommendation**:
- Set `VITE_MAP_PMTILES_URL` to a Protomaps PMTiles archive on R2/S3.
- Protomaps vector tiles are ~80% smaller than raster.
- Alternatively, use a free Protomaps basemap from `https://build.protomaps.com/`.
- PWA service worker should cache tile requests.
- Estimated map bandwidth reduction: **60–80%**.

### 3.4 Extend PWA Workbox to cache API responses and map tiles ⭐ MEDIUM IMPACT

**Current state** (`vite.config.ts`):
- Workbox `globPatterns` only precaches `**/*.{js,css,html,svg,png}`.
- No runtime caching for API calls or map tiles.

**Recommendation**:
```typescript
workbox: {
    globPatterns: ["**/*.{js,css,html,svg,png}"],
    runtimeCaching: [
        {
            // Cache map tiles for 7 days
            urlPattern: /^https:\/\/tile\.openstreetmap\.org/,
            handler: "CacheFirst",
            options: {
                cacheName: "map-tiles",
                expiration: { maxEntries: 500, maxAgeSeconds: 7 * 24 * 60 * 60 },
            },
        },
        {
            // Cache geocode results for 1 hour (stale-while-revalidate)
            urlPattern: /\/api\/geocode\?/,
            handler: "StaleWhileRevalidate",
            options: {
                cacheName: "geocode-api",
                expiration: { maxEntries: 50, maxAgeSeconds: 3600 },
            },
        },
    ],
}
```

### 3.5 Add ETag/conditional request support for lead lists ⭐ LOW-MEDIUM IMPACT

**Current state**:
- No ETags or Last-Modified headers on API responses.
- Frontend always receives full response even if data hasn't changed.

**Recommendation**:
- For `GET /routes/{id}/leads`, compute an ETag from `(route_id, updated_at, filter_params)`.
- Return `304 Not Modified` when appropriate.
- Frontend `fetch` handles `ETag`/`If-None-Match` automatically.

---

## Category 4: Infrastructure & Query Optimization

### 4.1 Add Cache-Control headers to backend responses ⭐ MEDIUM IMPACT

**Current state**:
- Backend middleware adds security headers but no `Cache-Control`.
- All API responses treated as non-cacheable by browsers/CDNs.

**Recommendation**:
```python
# Add to _apply_security_headers()
if request.method == "GET" and response.status_code == 200:
    path = request.url.path
    if path.startswith("/health"):
        response.headers.setdefault("Cache-Control", "no-cache")
    elif "/leads" in path or "/routes" in path:
        response.headers.setdefault("Cache-Control", "private, max-age=30")
    elif path.startswith("/geocode"):
        response.headers.setdefault("Cache-Control", "private, max-age=3600")
```

### 4.2 Optimize the business search candidate query ⭐ LOW-MEDIUM IMPACT

**Current state** (`business_search_service.py` → `CANDIDATE_QUERY`):
- Always performs a LEFT JOIN on `lead_field_validation` with aggregation.
- This aggregation scans all validation records even when v2 scoring is disabled.

**Recommendation**:
- Make the validation subquery conditional: only join when v2 scoring is active.
- When v1 only: skip the validation subquery entirely.
- For v2: consider materializing the aggregation as a DB view or maintaining a summary column.

### 4.3 Add index for lead_score queries ⭐ LOW IMPACT

**Current state**:
- `fetch_leads` joins `LeadScore`, `RouteCandidate`, and `Business` with filters.
- The join on `(route_id, business_id)` for both tables may not be optimally indexed.

**Recommendation**:
- Verify composite indexes exist:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_lead_score_route_business
    ON lead_score (route_id, business_id);
  CREATE INDEX IF NOT EXISTS idx_route_candidate_route_business
    ON route_candidate (route_id, business_id);
  CREATE INDEX IF NOT EXISTS idx_lead_score_route_final
    ON lead_score (route_id, final_score DESC);
  ```

### 4.4 Stream CSV export instead of buffering ⭐ LOW IMPACT

**Current state** (`export.py`):
- Builds the entire CSV in a `StringIO` buffer, then streams it.
- For large exports (2000 leads), this buffers everything in memory.

**Recommendation**:
- Use a true streaming generator to yield CSV rows incrementally.
- This doesn't reduce bandwidth but reduces server memory pressure.

---

## Implementation Priority

| Priority | Item | Est. Impact | Effort |
|----------|------|-------------|--------|
| **P0** | 2.1 Batch validation endpoint | Eliminates N+1 API calls (up to 100→1) | Medium |
| **P0** | 3.1 API response compression | 70–85% API bandwidth reduction | Trivial |
| **P0** | 3.2 nginx gzip + caching | 70–85% static asset reduction | Trivial |
| **P1** | 1.1 Cache geocode results | 70–90% fewer Photon API calls | Small |
| **P1** | 2.2 Batch notes / inline latest_note | Eliminates N+1 for SavedLeads | Small |
| **P1** | 3.3 Enable PMTiles vector map | 60–80% map tile bandwidth | Small |
| **P2** | 1.3 Reuse httpx clients | Fewer TLS handshakes, lower latency | Small |
| **P2** | 3.4 PWA runtime caching | Offline + reduced repeat bandwidth | Small |
| **P2** | 4.1 Cache-Control headers | Better browser/CDN caching | Trivial |
| **P3** | 2.3 Field selection on leads | 30–50% smaller lead payloads | Medium |
| **P3** | 1.2 Cache Overpass responses | Fewer redundant enrichment calls | Small |
| **P3** | 1.4 Cache validation HTTP results | Fewer redundant website fetches | Small |
| **P3** | 2.4 Slim ORS JSONB storage | 50–90% less route JSONB | Small |
| **P3** | 3.5 ETag support | Conditional responses | Medium |
| **P3** | 4.2 Conditional validation JOIN | Faster candidate queries | Small |

---

## Quick Wins (Can ship in < 1 hour each)

1. **Add `GZipMiddleware`** to `backend/app/main.py` — 2 lines of code
2. **Enable nginx gzip + caching** in `frontend/nginx.conf` — ~15 lines
3. **Set `VITE_MAP_PMTILES_URL`** in Render config — config change only
4. **Add Redis caching to geocode_service** — ~10 lines
5. **Strip `ors_response_json` geometry** before DB insert — ~5 lines

---

## Estimated Total Impact

| Metric | Before | After (est.) | Reduction |
|--------|--------|--------------|-----------|
| API calls per lead page load | ~101 | ~2 | **98%** |
| Geocode API calls per session | ~20–40 | ~4–8 | **80%** |
| API response size (leads) | ~150KB | ~20KB (compressed) | **87%** |
| Map tile bandwidth per session | ~4MB | ~0.8MB | **80%** |
| Static asset repeat loads | Full | Cached | **95%** |
| External TLS handshakes/min | High | Low (pooled) | **70%** |
---

## Plan Audit — April 19, 2026

> Audited against current codebase. Items marked ✅ are correct and viable as written.
> Items marked ⚠️ have gaps or require correction before implementation.
> Items marked ❌ have a structural problem that makes them wrong or unviable as written.

---

### ❌ 2.5 — Pagination conflicts with map display

The plan assumes pagination is straightforwardly applicable to the lead list. It is not for
the Route tab. All leads must be loaded to render map pins — paginating the list would
silently leave most pins off the map. As written this recommendation is broken for the
Route tab.

**Fix:** Scope pagination explicitly to the **Saved tab only** (no map). For the Route tab,
the current `limit: 100` approach is appropriate; the real fix there is 3.1 (compression)
+ 2.3 (field selection) to shrink the payload rather than paginate it.

---

### ❌ 3.3 — PMTiles URL in `.env` is wrong format

`.env` currently has:
```
VITE_MAP_PMTILES_URL=https://protomaps.github.io/basemaps-assets/tiles/v3/{z}/{x}/{y}.mvt
```
That is an XYZ tile template URL, not a PMTiles archive. The `PMTiles` library expects a
single `.pmtiles` file URL (e.g. `https://example.com/basemap.pmtiles`). The `{z}/{x}/{y}`
template will silently fail — `MapPanel.tsx` will fall through to the raster fallback and
the "Quick Win" of setting this env var will appear to do nothing.

**Fix:** Obtain a real `.pmtiles` archive URL from `https://build.protomaps.com/` or host
one on R2/S3. Update `.env` and `render.yaml` together — do not update `render.yaml` first
or production will silently regress to raster. The plan's recommendation to use Protomaps
is correct; the existing `.env` value is not.

---

### ⚠️ 2.1 — Batch endpoint routing conflict risk

`POST /leads/validation/batch` — FastAPI will attempt to match `"validation"` against the
`{business_id}` path segment on `POST /leads/{business_id}/validate`. If the batch route
is registered after the parameterized route, it will never be reached.

**Fix:** Register the batch route before the parameterized route, or place it at a distinct
path such as `POST /validation/batch` at the router level.

---

### ⚠️ 1.4 — No cache invalidation on manual "Validate now"

The plan caches validation HTTP results with TTL = `next_check_days`. When a rep triggers
"Validate now," the expectation is a live fetch. Without explicit cache busting, the
endpoint will silently return the stale cached result.

**Fix:** Add a `force=true` parameter to the validation trigger path that deletes the Redis
key before fetching. The `force=true` freshness gate pattern already exists in the OSM
enrichment service — apply the same approach here.

---

### ⚠️ 2.4 — Audit ORS JSON consumers before stripping

"Strip geometry from `ors_response_json`" is technically sound since `route_geom` stores it
separately — but the plan does not require auditing all readers of that column first. If any
path reconstructs route display or degraded-mode geometry from the JSONB field, stripping
coordinates will silently break it.

**Fix:** Before implementing, run `grep -r "ors_response_json" backend/` and confirm every
read site only uses `properties.summary` or metadata — not coordinate arrays. Add this as
an explicit prerequisite step.

---

### ⚠️ 4.1 — `private, max-age=30` on leads risks stale UI

30 seconds of browser caching on `GET /leads` or `GET /routes` means a rep saves a lead,
navigates back, and may see it as unsaved for up to 30 seconds. The plan does not address
cache invalidation after mutations.

**Fix:** Use `no-cache` for mutable resources (validates every request but still benefits
from a future ETag/304 path). Reserve `max-age=30` for `/geocode` only, where the plan
already correctly applies it.

---

### ⚠️ 4.3 — Indexes must be an Alembic migration, not ad-hoc SQL

The plan presents the composite indexes as raw `CREATE INDEX` statements with no mention of
wrapping them in an Alembic migration. Running them ad-hoc works once but they will be
absent on fresh deploys and staging resets.

**Fix:** Add a new migration (e.g. `0009_perf_indexes.py`) with the three
`CREATE INDEX IF NOT EXISTS` statements. This is the established pattern in the codebase.

---

### ⚠️ 3.5 — ETag note is misleading

"Frontend `fetch` handles `ETag`/`If-None-Match` automatically" is incorrect for
programmatic `fetch()` calls in React. Automatic ETag handling only applies to browser
navigation requests. React `fetch()` calls require explicit code to store the ETag from one
response and attach it as `If-None-Match` on the next call.

**Fix:** Either document the required frontend changes or downgrade 3.5 to P4/deferred —
the effort is genuinely medium on both sides, not zero-effort on the frontend as implied.

---

### ⚠️ 3.4 — Workbox geocode URL pattern will not match

The `runtimeCaching` pattern uses `/api/geocode\?` but the actual geocode endpoint has no
`/api` prefix. The pattern will silently never fire.

**Fix:** Verify the actual geocode path (likely `/geocode?`) and correct the regex. Also:
if PMTiles is active, the `tile.openstreetmap.org` cache rule becomes irrelevant — keep
both rules and let the inactive one simply never fire, or gate on the env var.

---

### ✅ Items confirmed correct and viable as written

- **3.1 GZipMiddleware** — correct import, correct threshold, accurate impact. Two lines.
- **3.2 nginx config** — technically correct; `immutable` + 1y for hashed assets is right for Vite output.
- **2.1 Batch validation concept** — N+1 problem is real, batch approach is correct, 101→2 estimate is accurate. Fix routing conflict noted above before implementing.
- **1.3 httpx client pooling** — correct pattern with lifespan. Sketch omits `overpass_client`; add it.
- **1.1 Redis geocode caching** — implementation sketch is correct. 7-day TTL is appropriate.
- **2.2 Inline `latest_note_text` via SQL JOIN** — the "better" option (SQL subquery, not a new HTTP endpoint) is the right call.
- **Priority table** — P0/P1/P2/P3 ordering is sound.
- **Impact estimates** — conservative and defensible given the actual code patterns.

---

## Codex Audit Notes — April 19, 2026 (Pass 2)

This section is a second-pass audit against the live repo state on April 19, 2026.

### Current realism verdict

- The optimization plan is strong and mostly practical.
- The fastest, highest-confidence wins are still compression + N+1 request reduction.
- A few items need wording updates so the plan matches current repo facts and rollout risk.

### Confirmed repo-state deltas

- **Compression is still missing** in both layers:
  - Backend has no `GZipMiddleware` in `backend/app/main.py`.
  - Frontend `frontend/nginx.conf` is still minimal (no gzip/cache headers).
- **N+1 patterns are still present**:
  - Route lead validation hydration (`Promise.allSettled` per lead).
  - Saved leads note hydration (`listNotes` per item when `latest_note_text` absent).
- **PMTiles config mismatch still exists in local dev env**:
  - `frontend/.env` uses an XYZ template URL instead of a `.pmtiles` archive URL.
  - `frontend/.env.example` already uses the correct `.pmtiles` format.

### Scope corrections to keep

- Keep the existing warning that route-tab pagination is not a safe default (map needs full pin set).
- Keep ETag as medium effort requiring explicit frontend work (`If-None-Match` handling in API client).
- Keep index changes gated behind Alembic migration, not ad-hoc SQL.

### Recommended execution order (updated)

1. Ship backend gzip (`3.1`) and nginx gzip/cache headers (`3.2`) first.
2. Remove N+1 calls next (`2.1` batch validation + `2.2` latest note hydration fix).
3. Enable geocode cache (`1.1`) and PMTiles with valid archive URL (`3.3`).
4. Add httpx pooling (`1.3`) and Workbox runtime caching (`3.4`) after the above.
5. Defer ETag (`3.5`) and field-selection API (`2.3`) until the first optimization wave is measured.

### Measurement note

- Add a short before/after metrics capture per wave (request count per route load, API payload bytes, median route-screen load time). Without this, impact claims remain estimated and can drift from reality.
