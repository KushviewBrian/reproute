# Reproute — Complete Development Roadmap

> Build a route-aware prospecting PWA for field insurance agents.
> Turn a drive into a ranked list of stop-worthy small-commercial businesses.

---

## How to read this document

Each phase has:
- **Goal** — what the phase achieves and why it matters
- **Tasks** — everything that needs to happen, in order
- **Definition of done** — the specific, testable thing that must be true before moving on
- **Blockers** — what will stop the next phase if skipped

Phases are sequential. Do not start Phase N+1 until Phase N's definition of done is met.

---

## Current status (Updated April 16, 2026)

This section is the authoritative progress snapshot for the current codebase.  
The phase checklists below remain the original baseline spec.

### Progress summary

| Phase | Status | Completion |
|---|---|---|
| Phase 0 — Foundation | In progress | ~80% |
| Phase 1 — Data + routing foundation | In progress | ~95% |
| Phase 2 — Classification + scoring | In progress | ~90% |
| Phase 3 — Discovery UI | In progress | ~92% |
| Phase 4 — Save, notes, export | In progress | ~92% |
| Phase 5 — Pre-pilot hardening | Not started | ~20% |
| Phase 6 — Agent validation | Not started | 0% |
| Phase 7 — Polish + launch prep | Not started | ~10% |

### What is complete now

- Monorepo structure exists and is active (`backend/`, `frontend/`, `infra/`, `scripts/`, `docs/`).
- Backend FastAPI app, health endpoint, auth-protected core routes, and DB schema/migration exist.
- Core route flow works: create route, candidate query, score, retrieve leads.
- Overture ingestion + classification scripts exist and are wired.
- Discovery UI exists (route entry, lead list/map, lead detail, saved leads).
- Save, notes, and CSV export are implemented and working in current prototype flow.
- PWA build setup exists (`vite-plugin-pwa`) and frontend builds successfully.

### Remaining by phase (detailed)

### Phase 0 — Foundation (remaining)

- Finalize tiles strategy in production config:
  - Either complete Protomaps PMTiles on R2 path end-to-end, or explicitly lock to raster fallback in roadmap and envs.
- CI/CD deploy path:
  - CI currently builds/tests; production deploy steps are still placeholders.
  - Add deterministic deploy actions (Render + frontend host) with secrets and rollback notes.
- Validate local reproducibility from clean machine:
  - one-command bring-up, migration, and smoke flow.

### Phase 1 — Data + routing foundation (remaining)

- Run and commit `EXPLAIN ANALYZE` evidence for at least one real route.
- Run ingestion with real metro bbox and capture QA summary metrics in docs.

### Phase 2 — Classification + scoring (remaining)

- Complete data QA loop against real imported dataset:
  - measure and reduce `"Other Commercial"` toward roadmap threshold.
- Execute scoring validation harness on 5 real routes and archive results.
- Persist calibration procedure:
  - document score-weight tuning protocol from real save behavior.

### Phase 3 — Discovery UI (remaining)

- Final mobile UX pass:
  - one-thumb ergonomics, edge-case handling, and no-overlap checks across target devices.
- Optional but recommended:
  - add explicit corridor polygon overlay (not only route glow).
  - add mini-map inside lead detail drawer.

### Phase 4 — Save, notes, export (remaining)

- Robust offline behavior completeness:
  - ensure saved leads + note interactions degrade gracefully and sync predictably after reconnect.
- Optional enhancement:
  - export all saved leads across routes from Saved tab (in addition to per-route export).

### Phase 5 — Pre-pilot hardening (remaining, critical before pilot)

- Performance validation:
  - 20-route benchmark run, p95 target evidence, and regression baseline.
- Observability:
  - structured request logging + metrics for route/geocode/scoring/export paths.
- Security/ops hardening:
  - enforce documented retention policy and audit logs for note/status changes.
  - cap export size and ingestion bounds with tested guardrails.
- Compliance:
  - full attribution and `docs/licenses.md` completion.
- Contingency triggers:
  - explicit runbooks for ORS/Photon self-host and Supabase upgrade when thresholds are hit.

### Phase 6 — Agent validation (remaining)

- Recruit 3–5 real agents in target metro.
- Run structured sessions (3–5 routes each) with standardized evaluation form.
- Collect quantitative pass/fail metrics from roadmap section 6.4.
- Execute one targeted tuning loop if targets are missed.

### Phase 7 — Polish + launch prep (remaining)

- First-run onboarding overlay and complete empty/error state coverage.
- iOS install banner flow and onboarding docs.
- Full cross-device QA matrix pass (iOS Safari, Android Chrome, desktop browsers).
- Production monitoring activation:
  - Sentry frontend/backend
  - uptime checks + alerting on degraded `/health`.

### Next recommended execution order

1. Close remaining Phase 3/4 product gaps (offline saved leads, saved sorting, nav badge).
2. Run Phase 1/2 evidence scripts and commit artifacts (`docs/PHASE1_4_VALIDATION.md`).
3. Complete Phase 5 hardening and evidence capture.
4. Run Phase 6 agent validation before any launch commitments.

---

## Tech stack reference

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React + TypeScript + Tailwind | PWA via vite-plugin-pwa |
| Maps | MapLibre GL JS v5.x | PMTiles source from Cloudflare R2 |
| Tiles | Protomaps PMTiles on Cloudflare R2 | 10M reads/month free, zero egress |
| Backend | FastAPI (Python) | Dockerized, env-var config only |
| Database | PostgreSQL 16 + PostGIS | All geometry as `geography` type |
| Routing | ORS public API → self-hosted ORS | Self-host before pilot |
| Geocoding | Photon (proxied + cached) → self-hosted | Self-host before pilot |
| Geocode cache | Cloudflare Workers KV | Edge cache, 100K reads/day free |
| Auth | Clerk (50K MRU free) | JWT validated in FastAPI middleware |
| Redis | Upstash free tier | Rate limiting + route cache |
| CI/CD | GitHub Actions | Build → test → deploy on push to main |
| Hosting (backend) | Render free/paid | Docker container, env vars only |
| Hosting (frontend) | Cloudflare Pages | Unlimited static asset requests |
| Place data | Overture Maps Places | Monthly bulk GeoParquet, ingested to PostGIS |

---

## Phase 0 — Foundation

**Duration:** 3–5 days
**Goal:** Every tool, service, and pipeline is wired up and confirmed working end-to-end before a single line of product code is written. This phase has no product features. Its only job is to eliminate integration surprises from later phases.

### 0.1 Repository and project structure

- [ ] Create GitHub repo (`reproute` or chosen name)
- [ ] Set up monorepo structure:
  ```
  /backend        — FastAPI app
  /frontend       — React PWA
  /infra          — Docker Compose, deployment configs
  /scripts        — ingestion scripts, one-off tooling
  /docs           — licenses, architecture notes
  ```
- [ ] Add `.gitignore` (Python, Node, env files, secrets)
- [ ] Add `README.md` with local dev setup instructions
- [ ] Create `CLAUDE.md` if using Claude Code — project context and conventions

### 0.2 Local development environment

- [ ] Write `docker-compose.yml`:
  ```yaml
  services:
    db:       postgres:16 with postgis extension
    redis:    redis:7-alpine
    backend:  FastAPI via uvicorn --reload
    frontend: Vite dev server
  ```
- [ ] Confirm `docker compose up` starts all four services cleanly
- [ ] Add environment variable template (`.env.example`) — never commit `.env`
- [ ] Confirm PostGIS is enabled: `SELECT PostGIS_Version();` returns a version string

### 0.3 Database schema

- [ ] Install Alembic for migrations
- [ ] Create initial migration with all seven tables:
  - `user`
  - `business`
  - `route`
  - `route_candidate`
  - `lead_score`
  - `saved_lead`
  - `note`
- [ ] All geometry columns use `GEOGRAPHY(type, 4326)` — not `GEOMETRY`
- [ ] Create all indexes:
  - `GIST` on `business.geom`
  - `GIST` on `route.route_geom`
  - B-tree on `business.insurance_class`
  - B-tree on `business.operating_status`
  - B-tree on `route_candidate.route_id`
  - B-tree on `note.business_id`, `note.user_id`
- [ ] Run migration: `alembic upgrade head` completes without errors
- [ ] Confirm all tables exist with correct columns

### 0.4 FastAPI skeleton

- [ ] Install FastAPI, uvicorn, asyncpg, SQLAlchemy (async), GeoAlchemy2, Pydantic v2
- [ ] Create app with single `GET /health` endpoint returning `{"status": "ok"}`
- [ ] Database connection pool configured via env var (`DATABASE_URL`)
- [ ] `/health` endpoint confirms DB is reachable (runs a trivial query)
- [ ] App starts with `docker compose up` and `/health` returns 200

### 0.5 Authentication (Clerk)

- [ ] Create Clerk account, create application
- [ ] Install Clerk React SDK in frontend
- [ ] Implement login/logout in frontend (Clerk's prebuilt components are fine)
- [ ] Install `python-jose` or `PyJWT` in backend for JWT validation
- [ ] Write FastAPI dependency `get_current_user` that validates Clerk JWT on every protected route
- [ ] Write FastAPI startup hook: on first login, upsert user record from JWT claims (`email`, `full_name`)
- [ ] Confirm end-to-end: log in via frontend → JWT sent with API request → backend validates → user record created in DB

### 0.6 Map tiles (Protomaps + Cloudflare R2)

- [ ] Download Protomaps PMTiles extract for target metro from protomaps.com/downloads
- [ ] Create Cloudflare account, create R2 bucket
- [ ] Upload PMTiles file to R2
- [ ] Configure R2 bucket for public access (or signed URL — public is fine for map tiles)
- [ ] In frontend, configure MapLibre with PMTiles source:
  ```js
  import { PMTiles, Protocol } from "pmtiles";
  // add protocol, set map style source to R2 URL
  ```
- [ ] Confirm map renders in browser with correct basemap for target metro
- [ ] Confirm map renders on mobile browser (test on phone)

### 0.7 CI/CD pipeline (GitHub Actions)

- [ ] Create workflow file `.github/workflows/deploy.yml`
- [ ] Pipeline steps on push to `main`:
  1. Run Python tests (`pytest`)
  2. Run frontend build (`npm run build`)
  3. Build Docker image, push to `ghcr.io`
  4. Deploy backend to Render (trigger deploy or Render API)
  5. Deploy frontend to Cloudflare Pages (`wrangler pages deploy ./dist`)
- [ ] Store secrets in GitHub Actions secrets: `RENDER_API_KEY`, `RENDER_SERVICE_ID`, `CLOUDFLARE_API_TOKEN`, `CLERK_SECRET_KEY`, `DATABASE_URL`, etc.
- [ ] First pipeline run completes green end-to-end

### 0.8 Overture data validation

- [ ] Install `overturemaps` CLI: `pip install overturemaps`
- [ ] Run a small test download (tight bounding box, ~5km²):
  ```bash
  overturemaps download --bbox=-87.65,41.87,-87.62,41.90 \
    --type=place -f geoparquet -o test_places.parquet
  ```
- [ ] Confirm file downloads and contains records
- [ ] Open with DuckDB or geopandas, inspect schema — confirm fields: `names`, `addresses`, `phones`, `websites`, `basic_category`, `taxonomy`, `confidence`, `operating_status`, `geometry`
- [ ] Confirm `taxonomy.primary` and `basic_category` are present and populated
- [ ] Note actual row count and field null rates — baseline for QA

### Phase 0 — Definition of done

- [ ] `docker compose up` starts all services cleanly
- [ ] `/health` returns 200 and confirms DB connection
- [ ] Login/logout works end-to-end; user record created in DB
- [ ] Map renders in browser from R2 PMTiles
- [ ] CI/CD pipeline runs green on push to main
- [ ] Overture sample download validated with correct schema

**Do not proceed to Phase 1 until all six are true.**

---

## Phase 1 — Data and Routing Foundation

**Duration:** 5–7 days
**Goal:** Given any origin and destination within the target metro, the app can return a list of raw (unscored) businesses near the route. This is the data pipeline and spatial query engine — the foundation everything else sits on.

### 1.1 Overture ingestion script

- [ ] Write `scripts/ingest_overture.py`
- [ ] Accept CLI args: `--bbox`, `--label` (e.g., `chicago`)
- [ ] Download GeoParquet for bbox via `overturemaps` CLI or DuckDB S3 query
- [ ] Normalize fields from Overture schema to internal schema:
  - `names.primary` → `name` (required; skip record if null)
  - `addresses[0]` fields → `address_line1`, `city`, `state`, `postal_code`
  - `phones[0]` → `phone`
  - `websites[0]` → `website`
  - `basic_category` → `category_primary`
  - `taxonomy.primary` → `category_secondary`
  - `confidence` → `confidence_score`
  - `operating_status` → `operating_status`
  - `geometry` (GeoJSON Point) → `geom` (PostGIS geography)
  - `id` → `external_id`; `external_source` = `"overture"`
  - Full source record → `source_payload_json`
- [ ] Filter before insert:
  - Drop records with null `name`
  - Drop records with null `geometry`
  - Drop records where `operating_status = 'permanently_closed'`
- [ ] Upsert into `business` table on `(external_source, external_id)`
- [ ] Set `last_seen_at = now()` on every upsert
- [ ] Batch inserts (1,000 rows/batch) — do not insert row-by-row
- [ ] Print progress every 10,000 rows

### 1.2 Run ingestion for target metro

- [ ] Choose target metro (one city/metro area — where test agents work)
- [ ] Run full ingestion: `python scripts/ingest_overture.py --bbox=... --label=chicago`
- [ ] Log and verify QA metrics after import:
  - Total rows inserted (expect: tens of thousands for a metro)
  - Missing name rate (expect: < 1%)
  - Missing geometry rate (expect: 0%)
  - Missing `basic_category` rate (flag if > 30%)
  - Percent with phone
  - Percent with website
  - Percent `operating_status = 'open'`
- [ ] All QA checks pass or are understood and documented

### 1.3 Geocoding service

- [ ] Write `backend/services/geocode_service.py`
- [ ] `async def geocode(query: str) -> list[GeocodedResult]`
- [ ] Calls Photon public API: `https://photon.komoot.io/api/?q={query}&limit=5`
- [ ] Returns list of `{label, lat, lng, bbox}` — normalized, not raw Photon response
- [ ] Implement Cloudflare Workers KV cache:
  - Write a Cloudflare Worker that wraps Photon: check KV first, proxy if miss, write result to KV (TTL 24h)
  - Backend `/geocode` endpoint calls the Worker URL, not Photon directly
  - This puts the cache at the edge, reducing backend load and Photon quota usage
- [ ] Per-user rate limit on `/geocode` endpoint: max 30 requests/minute via Redis counter
- [ ] Circuit breaker: if upstream returns non-200, return empty results with `degraded: true` flag — do not retry in a loop

### 1.4 Routing service

- [ ] Write `backend/services/routing_service.py`
- [ ] `async def get_route(origin: LatLng, destination: LatLng) -> RouteResult`
- [ ] Calls ORS Directions API:
  ```
  POST https://api.openrouteservice.org/v2/directions/driving-car/geojson
  body: { coordinates: [[lng,lat], [lng,lat]] }
  ```
- [ ] Parses response: extracts LineString geometry, distance (meters), duration (seconds)
- [ ] Implements route cache: hash `(origin_lat, origin_lng, dest_lat, dest_lng)` → store result in Redis (TTL 24h)
- [ ] On cache hit: returns stored geometry, skips ORS call
- [ ] On ORS error: raises a clear exception — do not return partial results silently

### 1.5 Route creation endpoint

- [ ] Implement `POST /routes`:
  - Accepts: `origin_label`, `origin_lat`, `origin_lng`, `destination_label`, `destination_lat`, `destination_lng`, `corridor_width_meters` (default 1609)
  - Calls routing_service → gets route geometry
  - Stores route record in DB
  - Runs candidate spatial query (next task)
  - Returns: `route_id`, `route_distance_meters`, `route_duration_seconds`, `lead_count`, route GeoJSON
- [ ] Requires authentication (JWT)
- [ ] Per-user rate limit: max 60 route requests/hour (Redis counter)

### 1.6 Spatial candidate query

- [ ] Write `backend/services/business_search_service.py`
- [ ] `async def find_candidates(route_id: UUID, corridor_width_m: int) -> list[Candidate]`
- [ ] SQL query using `ST_DWithin` (index-aware, no buffer polygon materialization):
  ```sql
  SELECT b.*,
    ST_Distance(b.geom::geography, r.route_geom::geography) AS distance_from_route_m
  FROM business b
  CROSS JOIN route r
  WHERE r.id = :route_id
    AND b.insurance_class != 'Exclude'
    AND ST_DWithin(b.geom::geography, r.route_geom::geography, :corridor_width_m)
  ORDER BY distance_from_route_m ASC
  ```
- [ ] Confirm GIST index is being used: run `EXPLAIN ANALYZE` on the query, confirm index scan (not seq scan)
- [ ] Insert results into `route_candidate` table
- [ ] Return candidate list with distances

### 1.7 GET /routes/{route_id} endpoint

- [ ] Returns route metadata + candidate count
- [ ] Requires authentication
- [ ] Returns 404 if route not found or belongs to different user

### Phase 1 — Definition of done

- [ ] Run `python scripts/ingest_overture.py` for target metro — QA checks pass
- [ ] `POST /routes` with a real Chicago origin/destination returns a `route_id` and a non-zero `lead_count` within 5 seconds
- [ ] Route geometry appears correctly on map
- [ ] Spatial query uses GIST index (confirmed via EXPLAIN ANALYZE)
- [ ] ORS route is cached — second identical request does not call ORS

**Do not proceed to Phase 2 until all five are true.**

---

## Phase 2 — Classification and Scoring

**Duration:** 4–5 days
**Goal:** Every business in the database has an `insurance_class`. Every route produces a ranked, scored, explained list of leads. The scoring engine is the core product logic — it must be correct and trustworthy before any UI is built on top of it.

### 2.1 Classification service

- [ ] Write `backend/services/classification_service.py`
- [ ] Implement three-tier classification (in order):

  **Tier 1: `basic_category` direct map**
  ```python
  BASIC_CATEGORY_MAP = {
      "restaurant": "Food & Beverage",
      "bar": "Food & Beverage",
      "cafe": "Food & Beverage",
      "bakery": "Food & Beverage",
      "auto_repair": "Auto Service",
      "car_wash": "Auto Service",
      "tire_shop": "Auto Service",
      "beauty_salon": "Personal Services",
      "barber": "Personal Services",
      "nail_salon": "Personal Services",
      "dry_cleaning": "Personal Services",
      "lawyer": "Professional / Office",
      "accountant": "Professional / Office",
      "insurance_agency": "Professional / Office",
      "real_estate_agent": "Professional / Office",
      "plumber": "Contractor / Trades",
      "electrician": "Contractor / Trades",
      "hvac": "Contractor / Trades",
      "roofing_contractor": "Contractor / Trades",
      "dentist": "Medical / Clinic",
      "optometrist": "Medical / Clinic",
      "chiropractor": "Medical / Clinic",
      "physical_therapist": "Medical / Clinic",
      "gas_station": "Exclude",
      "hospital": "Exclude",
      "school": "Exclude",
      "place_of_worship": "Exclude",
      "park": "Exclude",
      "government_office": "Exclude",
      # ... extend as needed after QA
  }
  ```

  **Tier 2: `taxonomy.hierarchy` traversal**
  Check if any known parent token appears anywhere in the hierarchy array:
  ```python
  HIERARCHY_TOKEN_MAP = [
      ("eat_and_drink",            "Food & Beverage"),
      ("automotive",               "Auto Service"),
      ("personal_care",            "Personal Services"),
      ("professional_services",    "Professional / Office"),
      ("financial_services",       "Professional / Office"),
      ("legal_services",           "Professional / Office"),
      ("real_estate",              "Professional / Office"),
      ("home_improvement",         "Contractor / Trades"),
      ("construction",             "Contractor / Trades"),
      ("health_and_medical",       "Medical / Clinic"),
      ("retail",                   "Retail"),
      ("education",                "Exclude"),
      ("government_and_community", "Exclude"),
      ("parks_outdoors",           "Exclude"),
      ("religious",                "Exclude"),
  ]
  ```

  **Tier 3: business name keyword fallback**
  Used only when both category fields are null.

- [ ] Write `scripts/backfill_classification.py` — runs classification on all existing `business` records and updates `insurance_class`
- [ ] Run backfill on ingested metro data
- [ ] Log `insurance_class` distribution — review "Other Commercial" bucket manually
- [ ] Tune `BASIC_CATEGORY_MAP` based on what's in the "Other Commercial" bucket
- [ ] Re-run backfill until "Other Commercial" is < 20% of records

### 2.2 Apply classification at ingestion time

- [ ] Update `ingest_overture.py` to call `classification_service.classify()` on each record before insert
- [ ] Classification result stored in `insurance_class` column at ingest time
- [ ] Verify: after re-ingesting a sample, `insurance_class` is populated on all records

### 2.3 Scoring service

- [ ] Write `backend/services/scoring_service.py`
- [ ] `def score_candidate(candidate: Candidate, business: Business) -> LeadScore`

  **Fit score (40% weight):**
  ```python
  FIT_SCORES = {
      "Auto Service":          95,
      "Contractor / Trades":   90,
      "Retail":                85,
      "Food & Beverage":       75,
      "Personal Services":     75,
      "Medical / Clinic":      70,
      "Professional / Office": 65,
      "Light Industrial":      55,
      "Other Commercial":      40,
      "Exclude":               5,
  }
  ```

  **Distance score (30% weight):**
  ```python
  def distance_score(meters: float) -> int:
      if meters <= 250:   return 100
      if meters <= 750:   return 80
      if meters <= 1500:  return 60
      if meters <= 3000:  return 35
      return 10
  ```

  **Actionability score (30% weight):**
  ```python
  def actionability_score(business: Business) -> int:
      base = 10
      if business.has_address:  base += 40
      if business.has_phone:    base += 25
      if business.has_website:  base += 25
      # confidence modifier
      if business.confidence_score and business.confidence_score < 0.7:
          base = int(base * max(business.confidence_score, 0.5))
      return min(base, 100)
  ```

  **Final score:**
  ```python
  final = round(fit * 0.40 + distance * 0.30 + actionability * 0.30)
  ```

- [ ] Build score explanation generator:
  ```python
  def explain(business, fit, distance_m, actionability) -> dict:
      return {
          "fit": f"{'Strong' if fit >= 85 else 'Good' if fit >= 70 else 'Moderate'} fit: {business.insurance_class}",
          "distance": f"{'Very close' if distance_m <= 250 else 'Close' if distance_m <= 750 else 'Moderate distance'} ({int(distance_m)}m from route)",
          "actionability": _actionability_label(business),
      }
  ```
- [ ] Store scores in `lead_score` table with `score_version = "v1"`

### 2.4 Lead service and GET /routes/{id}/leads endpoint

- [ ] Write `backend/services/lead_service.py` — orchestrates search → score → store → return
- [ ] Implement `GET /routes/{route_id}/leads`:
  - Query params: `insurance_class` (multi), `min_score` (default 40), `has_phone`, `has_website`, `limit` (default 50, max 200), `offset`
  - Returns ranked list of leads with full score breakdown and explanation
  - Returns `total` (all candidates) and `filtered` (after query params applied)
- [ ] Response shape per lead:
  ```json
  {
    "business_id": "uuid",
    "name": "Ace Auto",
    "insurance_class": "Auto Service",
    "address": "789 Elm St, Chicago IL 60614",
    "phone": "312-555-0100",
    "website": "aceauto.com",
    "final_score": 87,
    "fit_score": 95,
    "distance_score": 90,
    "actionability_score": 80,
    "distance_from_route_m": 210,
    "explanation": {
      "fit": "Strong fit: Auto Service",
      "distance": "Very close (210m from route)",
      "actionability": "Has phone and website"
    },
    "lat": 41.92,
    "lng": -87.65
  }
  ```

### 2.5 Scoring validation

- [ ] Run 5 real test routes across the target metro
- [ ] Manually inspect top 20 leads per route
- [ ] Verify: top results are recognizable commercial businesses, not parks/schools/gas stations
- [ ] Verify: score explanations make sense for each result
- [ ] Verify: results return in under 3 seconds
- [ ] Adjust `FIT_SCORES` weights if obvious mismatches are found

### Phase 2 — Definition of done

- [ ] `insurance_class` is populated on all business records; "Other Commercial" < 20%
- [ ] `GET /routes/{id}/leads` returns a ranked list for any route in the metro
- [ ] Score explanations are present and accurate on all leads
- [ ] Top 10 results on 5 test routes are all recognizable commercial businesses
- [ ] Response time < 3 seconds for a 1-mile corridor route

**Do not proceed to Phase 3 until all five are true.**

---

## Phase 3 — Discovery UI

**Duration:** 5–7 days
**Goal:** A working, mobile-first PWA that an agent can actually use. Route entry → ranked leads → lead detail. Everything fits on a phone screen. The map works. The list is readable. Scores and explanations are visible at a glance.

### 3.1 PWA configuration

- [ ] Install and configure `vite-plugin-pwa`
- [ ] Create `manifest.json`:
  - `name`: app name
  - `display`: `standalone`
  - `start_url`: `/`
  - `background_color`, `theme_color`
  - Icons: 192×192 and 512×512 PNG
- [ ] Configure service worker:
  - Cache shell (HTML/JS/CSS) on install
  - Cache last route results in IndexedDB for offline access
  - Queue note writes when offline; sync when connection restores
- [ ] Test install on Android Chrome: install prompt appears, app installs to home screen
- [ ] Test install on iOS Safari: "Add to Home Screen" works, app opens in standalone mode
- [ ] Confirm app is usable without network for saved leads (offline cache works)

### 3.2 API client

- [ ] Write typed API client (`frontend/src/api/client.ts`)
- [ ] All requests include Clerk JWT as `Authorization: Bearer {token}`
- [ ] Handle 401 (re-auth), 429 (rate limited — show user message), network errors (show offline message)
- [ ] Typed response shapes matching backend response schema

### 3.3 Screen 1: Route Entry

- [ ] Origin input with geocode autocomplete:
  - Debounce: 300ms after last keystroke
  - Calls `GET /geocode?q=...`
  - Shows dropdown of up to 5 candidates with label
  - Selecting a candidate stores `{label, lat, lng}` in component state
  - Input shows selected label; coordinates stored separately (not visible)
- [ ] Destination input — same as origin
- [ ] "Use my location" button on origin field:
  - Calls `navigator.geolocation.getCurrentPosition()`
  - On success: reverse-geocodes via `/geocode` (Photon supports reverse), fills origin field
  - On denied: shows friendly message, does not break form
- [ ] Corridor width selector: three buttons (0.5 mi / 1 mi / 2 mi), default 1 mi
- [ ] Category filter: multi-select dropdown of insurance classes (optional, defaults to all)
- [ ] "Find Prospects" button:
  - Disabled until both origin and destination have resolved coordinates
  - On click: calls `POST /routes`, navigates to Lead Discovery on success
  - Shows loading spinner during request
  - Shows error message on failure (not a blank screen)
- [ ] Mobile layout: full-width single column, large tap targets (min 44px), readable at arm's length

### 3.4 Screen 2: Lead Discovery

- [ ] Split layout:
  - Mobile: list view by default, map toggle button to switch to map view
  - Desktop: left panel (list) + right panel (map), side by side
- [ ] **Lead list panel:**
  - Sorted by `final_score` descending by default
  - Each card shows:
    - Business name (large, bold)
    - Insurance class badge (colored by class)
    - Final score (large number, color-coded: green ≥ 70, amber 50–69, red < 50)
    - Distance from route (e.g., "210m from route")
    - Phone indicator (phone icon, filled if has phone)
    - Website indicator (globe icon, filled if has website)
    - Score explanation (3 short lines: fit / distance / actionability)
    - Quick save button (star/bookmark icon)
  - Infinite scroll or "load more" — do not paginate with numbered pages on mobile
- [ ] **Filter controls** (collapsible on mobile, always visible on desktop):
  - Insurance class filter (multi-select chips)
  - Min score slider (0–100, default 40)
  - "Has phone" toggle
  - "Has website" toggle
  - Corridor width (re-queries without new ORS call — calls `PATCH /routes/{id}` then refetches leads)
  - Result count display ("Showing 22 of 47 leads")
- [ ] **Map panel:**
  - Route line (blue, 3px)
  - Business pins colored by insurance class
  - Corridor boundary shown as a faded polygon
  - Clicking a pin opens the lead detail drawer for that business
  - Map fits to route bounds on load

### 3.5 Screen 3: Lead Detail (drawer/modal)

- [ ] Opens as a bottom sheet on mobile, side drawer on desktop
- [ ] Contents:
  - Business name (h1)
  - Insurance class badge
  - Full address (tappable → opens maps app)
  - Phone number (tappable → initiates call via `tel:` link)
  - Website (tappable → opens browser)
  - Score breakdown: three rows (fit / distance / actionability), each with label, score bar, and explanation text
  - Mini map showing business location relative to route
  - Save button with status selector (New / Saved / Visited / Called / Not Interested / Follow Up)
  - Notes section (inline — see Phase 4)
- [ ] Accessible via: pin click on map, card click in list

### 3.6 Screen 4: Saved Leads

- [ ] Navigation: accessible from main nav (bottom tab bar on mobile)
- [ ] List of all saved businesses across all routes
- [ ] Each item shows: name, class badge, status, notes preview, route it was saved from
- [ ] Filter by status (chips)
- [ ] Tap item → Lead Detail drawer
- [ ] Export CSV button (calls `GET /export/routes/{id}/leads.csv` — Phase 4)

### 3.7 Navigation and shell

- [ ] Bottom tab bar (mobile): Route Entry | Saved Leads | (Settings placeholder)
- [ ] Top nav (desktop): same sections
- [ ] Clerk user menu: avatar, sign out
- [ ] Attribution footer: "© OpenStreetMap contributors | Overture Maps | Protomaps"

### Phase 3 — Definition of done

- [ ] Route entry → geocode → route → leads flow works end-to-end on a phone
- [ ] Lead cards show name, class, score, explanation, distance — all readable on mobile
- [ ] Map renders route + pins correctly
- [ ] Clicking a pin opens the correct lead detail
- [ ] "Use my location" works on Android Chrome (iOS is optional at this stage)
- [ ] App installs as PWA on Android
- [ ] Filters update the lead list without a full page reload
- [ ] No blank screen or uncaught error on any user action

**Do not proceed to Phase 4 until all eight are true.**

---

## Phase 4 — Save, Notes, and Export

**Duration:** 3–4 days
**Goal:** Close the sales workflow loop. An agent can find a lead, save it, add a note, track status, and export their list. This is what makes the tool sticky between sessions.

### 4.1 Save lead

- [ ] `POST /saved-leads`: creates saved lead record; returns saved lead with status = "saved"
- [ ] `PATCH /saved-leads/{id}`: update status and/or priority
- [ ] `DELETE /saved-leads/{id}`: remove saved lead
- [ ] `GET /saved-leads`: return all saved leads for current user; filter by status
- [ ] Quick save button on lead card (star/bookmark):
  - Tap once: saves lead, icon fills
  - Tap again: opens status selector
- [ ] Status selector in Lead Detail: dropdown with all statuses; updates immediately via PATCH
- [ ] Saved count badge on Saved Leads tab in nav

### 4.2 Notes

- [ ] `POST /notes`: create note (business_id, route_id, note_text, outcome_status, next_action)
- [ ] `GET /notes?business_id={id}`: return all notes for a business, newest first
- [ ] `PATCH /notes/{id}`: edit a note
- [ ] Notes UI inside Lead Detail:
  - Notes list (append-only log — newest at top)
  - Each note shows: text, outcome status badge, next action, timestamp
  - "Add note" button → inline form (text area + outcome status dropdown + next action field + save)
  - Notes visible whether or not the lead is saved
- [ ] Offline note queue: if user adds a note while offline, queue it and sync when connection restores (service worker background sync)

### 4.3 Export

- [ ] `GET /export/routes/{route_id}/leads.csv`: streams CSV, no temp file
- [ ] CSV columns: `name, address, phone, website, insurance_class, final_score, distance_m, status, notes`
- [ ] For `notes` column: join all notes for that business as semicolon-separated text
- [ ] Optional query param: `?saved_only=true` — include only saved leads
- [ ] Export button in Saved Leads screen:
  - Triggers download of CSV for all saved leads
  - Shows "Exporting..." state during request
  - On complete: browser download dialog appears

### 4.4 Lead status workflow

- [ ] Status transitions are unrestricted — agent can set any status at any time
- [ ] Status displayed as colored badge: Saved (grey) / Visited (blue) / Called (yellow) / Not Interested (red) / Follow Up (green)
- [ ] "Follow Up" leads appear first in Saved Leads list (sorted by status priority, then by final_score)

### Phase 4 — Definition of done

- [ ] Save a lead → status persists across sessions (refresh, re-open app)
- [ ] Add a note → appears in lead detail; persists across sessions
- [ ] Change status → updates immediately; reflected in Saved Leads list
- [ ] Export CSV → downloads file with correct columns and data
- [ ] Offline note queue → note created offline syncs when back online

**Do not proceed to Phase 5 until all five are true.**

---

## Phase 5 — Pre-Pilot Hardening

**Duration:** 3–4 days
**Goal:** The app is reliable enough to put in front of real agents without embarrassment. Performance is confirmed. Rate limits and quota protections are in place. The free stack stays in place — contingency upgrades are only triggered if specific problems actually occur, not preemptively.

### 5.1 Self-host ORS and Photon (contingency — do only if triggered)

**Trigger:** ORS public API rate limits are actually being hit during testing, or Photon public endpoint is unreliable.

If the trigger has not occurred, skip this task and proceed with cached public APIs through the pilot.

If triggered:
- [ ] Provision a VPS with 8+ GB RAM (Hetzner CAX21 or equivalent, ~$10–15/mo)
- [ ] Deploy ORS via Docker:
  ```bash
  docker run -p 8080:8080 \
    -v /data/ors:/home/ors \
    openrouteservice/openrouteservice:latest
  ```
- [ ] Download OSM extract for target region (Geofabrik), load into ORS
- [ ] Confirm ORS returns routes for target metro
- [ ] Update `routing_service.py` ORS base URL to point to self-hosted instance
- [ ] Deploy Photon on the same VPS (Docker image: `komoot/photon`)
- [ ] Update `geocode_service.py` to use self-hosted Photon URL
- [ ] Update Cloudflare Worker to proxy to self-hosted Photon instead of public endpoint
- [ ] Confirm geocode autocomplete works against self-hosted Photon

### 5.2 Upgrade Supabase (contingency — do only if triggered)

**Trigger:** Supabase free tier actually pauses during active use, or storage approaches 500 MB limit.

If the trigger has not occurred, stay on the free tier through the pilot. Daily use by agents prevents the inactivity pause from firing.

If triggered:
- [ ] Upgrade Supabase to Pro ($25/mo)
- [ ] Confirm inactivity pause is disabled
- [ ] Confirm daily backups are enabled
- [ ] Run `VACUUM ANALYZE` on `business` table after upgrade

### 5.3 Performance testing

- [ ] Run 20 test routes across the metro (vary origin/destination, corridor width, category filters)
- [ ] Record: response time for `POST /routes` + `GET /routes/{id}/leads`
- [ ] Target: p95 response time < 5 seconds for the combined flow
- [ ] If slow: run `EXPLAIN ANALYZE` on the spatial query; confirm GIST index is used; check for missing indexes
- [ ] Load test: simulate 5 concurrent route requests; confirm no DB connection pool exhaustion

### 5.4 Rate limit and quota audit

- [ ] Confirm per-user rate limits are active on `/routes` (60/hr) and `/geocode` (30/min)
- [ ] Confirm route geometry cache is working (Redis hit rate > 0 after repeated routes)
- [ ] Confirm Workers KV geocode cache is working (check KV metrics in Cloudflare dashboard)
- [ ] Confirm ORS is no longer being called for cached routes
- [ ] Test: exhaust rate limit on `/geocode` — confirm 429 is returned with a user-friendly message, not a 500

### 5.5 Non-functional controls

**Logging and observability:**
- [ ] Structured logging: every request logs `request_id`, `user_id`, `route_id` (where applicable), duration, status code
- [ ] Add metrics instrumentation: request latency, geocoder errors, ORS errors, DB query latency, import job duration
- [ ] `/health` endpoint checks DB, Redis connectivity — returns degraded status if either is down
- [ ] Error responses never expose stack traces or internal details to the frontend

**Security:**
- [ ] All secrets loaded from environment variables — no hardcoded credentials (`grep -r "sk_" .` returns nothing)
- [ ] Reject oversized bounding boxes on import; enforce max CSV export row limit
- [ ] Minimize stored PII — only email and user-authored notes; no unnecessary personal data retained

**Data retention and privacy:**
- [ ] Define and document data retention policy: how long notes, exports, and routes are kept
- [ ] Add audit logging for lead status changes and note edits (who changed what, when)

**Backup:**
- [ ] Confirm DB backup is running (Supabase free tier has point-in-time backups; verify they are enabled and a restore has been tested at least once before pilot)

**Attribution and compliance:**
- [ ] Attribution visible in app footer on all map screens: "© OpenStreetMap contributors | Overture Maps | Protomaps"
- [ ] `docs/licenses.md` created with CDLA-Permissive-2.0 (Overture), ODbL (OSM/Protomaps), Apache-2.0 (ORS), linked from app footer

### 5.6 Category mapping QA

- [ ] Query: `SELECT insurance_class, COUNT(*) FROM business GROUP BY 1 ORDER BY 2 DESC`
- [ ] Review "Other Commercial" records — pull 50 random samples, identify any that should be classified
- [ ] Update `BASIC_CATEGORY_MAP` or `HIERARCHY_TOKEN_MAP` for any obvious gaps
- [ ] Re-run `scripts/backfill_classification.py`
- [ ] Target: "Other Commercial" < 15% of total records

### Phase 5 — Definition of done

**Performance:**
- [ ] p95 response time < 5s confirmed across 20 test routes
- [ ] Route geometry cache confirmed working (Redis hit rate > 0)
- [ ] Workers KV geocode cache confirmed working

**Rate limits and quotas:**
- [ ] Rate limits active on `/routes` and `/geocode`; 429 returns user-friendly message
- [ ] ORS not called for cached routes (confirmed in logs)

**Security and ops:**
- [ ] No hardcoded secrets in codebase
- [ ] Structured logging active; no stack traces exposed to frontend
- [ ] Data retention policy documented
- [ ] Audit logging active for lead status and note changes
- [ ] DB backup verified with at least one test restore

**Attribution and compliance:**
- [ ] Attribution visible on all map screens
- [ ] `docs/licenses.md` present and linked from app footer

**Data quality:**
- [ ] "Other Commercial" < 15% of business records

**Contingency:**
- [ ] Any contingency upgrades (5.1, 5.2) completed if their triggers were hit

**Do not proceed to Phase 6 (agent testing) until all items above are true.**

---

## Phase 6 — Agent Validation

**Duration:** 5–7 days
**Goal:** Real insurance agents use the app on real routes in the target metro and give structured feedback. This phase produces the evidence needed to decide whether to continue, pivot, or adjust scoring and classification. Nothing gets built in this phase — only tested and measured.

### 6.1 Recruit test agents

- [ ] Identify 3–5 field insurance agents who work the target metro
- [ ] Brief them on what the app does and what you're measuring
- [ ] Provide: app URL, install instructions (PWA), test account credentials
- [ ] Document their typical routes and territory (for comparing test routes to real-world patterns)

### 6.2 Test session structure

Each agent runs 3–5 routes they would actually drive:

- [ ] Agent enters their real origin and destination
- [ ] Agent reviews the lead list and rates each lead: "Would stop" / "Maybe" / "Would not stop"
- [ ] Agent saves any leads they find genuinely useful
- [ ] Agent adds a note to at least one lead
- [ ] Agent exports their saved leads
- [ ] Agent answers the evaluation questions (see 6.3)

### 6.3 Evaluation questions (per session)

Collect answers after each test session:

1. Were the results relevant? (1–5)
2. Were there enough choices? (1–5)
3. Were they close enough to your route? (1–5)
4. Did the score feel trustworthy? (1–5)
5. Would you use this instead of manually scanning maps? (yes / maybe / no)
6. What was missing?
7. What would you remove?
8. Any businesses shown that felt obviously wrong?

### 6.4 Quantitative success targets

- [ ] At least 60% of shown leads rated "Would stop" or "Maybe" by test agents
- [ ] At least 40% of test routes produce 5+ leads rated "Would stop"
- [ ] Average of 3+ leads saved per route
- [ ] At least 3 of 5 agents answer "yes" or "maybe" to "Would you use this instead of maps?"

### 6.5 If targets are not met

| Problem | Response |
|---|---|
| Too many irrelevant businesses | Tighten exclusion list; raise minimum score threshold |
| Right businesses but wrong score order | Adjust fit score weights by class |
| Not enough businesses | Widen corridor default; check Overture coverage gaps |
| Businesses too far from route | Lower default corridor width; raise distance score weight |
| Score doesn't feel trustworthy | Improve explanation text; make score breakdown more visible |
| Data clearly stale/wrong | Accept as a known limitation; add user-facing disclaimer |

Run a targeted fix iteration (2–3 days), then repeat with same agents.

---

## Phase 7 — Polish and Launch Prep

**Duration:** 3–5 days
**Goal:** The product is ready for real use. Edge cases are handled. The onboarding experience is clear. The app is stable. Known limitations are documented honestly.

### 7.1 Onboarding

- [ ] First-run experience: brief overlay or tooltip explaining the three-step flow (enter route → review leads → save and export)
- [ ] Empty states: if no leads found for a route, show a helpful message (try wider corridor, try different route) — not a blank list
- [ ] Error states: every failure path shows a user-readable message — no raw errors, no blank screens

### 7.2 Edge case handling

- [ ] Route too short (< 1km): warn user, proceed anyway
- [ ] Route outside ingested metro: show "No data for this area" message, not an empty list
- [ ] Geocode returns no results: show "Address not found — try a different format" message
- [ ] ORS returns no route (e.g., ferry crossing, bad coordinates): show "Route could not be calculated" message
- [ ] DB returns 0 candidates: show empty state, not an error

### 7.3 iOS PWA install flow

- [ ] Add in-app banner on first load in iOS Safari: "Install this app — tap Share → Add to Home Screen"
- [ ] Banner dismissible and does not reappear after dismissal
- [ ] Document iOS install process in agent onboarding

### 7.4 Final QA pass

- [ ] Test full flow on: iOS Safari, Android Chrome, Chrome desktop, Firefox desktop
- [ ] Test offline: save a lead, kill network, open app — saved leads are accessible
- [ ] Test slow network (Chrome DevTools throttling): app degrades gracefully, no timeouts without user feedback
- [ ] Check attribution is visible on all map screens
- [ ] Run `npm run build` — no TypeScript errors, no build warnings

### 7.5 Monitoring

- [ ] Set up Sentry (free tier) on frontend — JS errors reported automatically
- [ ] Set up Sentry on backend — unhandled exceptions reported with request context
- [ ] Set up a simple uptime check (Better Uptime free tier or similar) on `/health`
- [ ] Get paged (email/Slack) if `/health` returns non-200 for 3 consecutive checks

### Phase 7 — Definition of done

- [ ] No blank screens or unhandled errors on any tested user path
- [ ] App installs and works on iOS and Android
- [ ] Offline mode confirmed: saved leads accessible without network
- [ ] Error monitoring active (Sentry)
- [ ] Uptime monitoring active
- [ ] Attribution visible on all map screens

**Launch when all six are true.**

---

## Post-Launch: Phase 8+ (Post-MVP Backlog)

Not scheduled. Prioritize based on agent feedback after Phase 6–7.

### Phase 8 candidates (do after launch, in rough priority order)

1. **Saved routes** — re-run a previous route with fresh data; agents reuse the same drives weekly
2. **Repeat territory mode** — flag businesses previously visited or saved; avoid showing them as new leads
3. **Improved scoring weights** — recalibrate fit/distance/actionability weights based on real save rates
4. **Chain/brand detection** — flag or deprioritize franchises and large chains; independent businesses are better prospects
5. **OSM gap fill** — supplement Overture with OSM records to improve coverage in areas with thin Overture data
6. **Monthly data refresh automation** — automate the Overture re-import and classification backfill as a scheduled job

### Phase 9 candidates (only after clear product-market fit)

1. **Stop-order optimization** — reorder saved leads by drive efficiency (TSP approximation)
2. **CRM export** — structured export to HubSpot, Salesforce, or generic CSV with field mapping
3. **Agency/team workspace** — shared territories, shared saved leads, per-agent assignment
4. **Website enrichment** — fetch and analyze business websites to improve actionability scoring
5. **Google Places validation** — optional premium enrichment for confidence and recency

### Phase 10 candidates (at scale)

1. **React Native companion app** — background GPS, push notifications for nearby prospects while driving
2. **Multi-region data** — expand Overture ingestion beyond the initial metro
3. **Underwriting fit scoring** — integrate real appetite data to score fit more accurately than class-based rules

---

## Milestone summary

| Phase | Duration | Weekly target |
|---|---|---|
| Phase 0: Foundation | 3–5 days | End of Week 1 |
| Phase 1: Data + routing | 5–7 days | End of Week 2 |
| Phase 2: Classification + scoring | 4–5 days | Mid Week 3 |
| Phase 3: Discovery UI | 5–7 days | End of Week 4 |
| Phase 4: Save / notes / export | 3–4 days | Mid Week 5 |
| Phase 5: Pre-pilot hardening | 3–4 days | End of Week 5 |
| Phase 6: Agent validation | 5–7 days | End of Week 6 |
| Phase 7: Polish + launch | 3–5 days | End of Week 7 |

**Total: ~6–7 weeks solo, 4–5 weeks with a two-person team.**

Week 5–6 budget includes buffer for integration issues, data quality work, and feedback iteration. The full MVP — including agent validation and launch — is a 6–7 week solo build. A stripped scope (no auth, no save/notes/export, minimal UI) could reach a testable state in 3 weeks but would not be pilot-ready.

---

## Cost at each milestone

| Stage | Monthly cost | Notes |
|---|---|---|
| Phases 0–4 (dev + free stack) | $0–25/mo | Render free can be $0; paid tier may be needed for always-on prod |
| Phase 5–7 (pilot + launch, no triggers hit) | ~$2–5/mo | Stay on free stack; contingency upgrades not needed |
| Phase 5–7 (if all contingency triggers hit) | ~$35–45/mo | Supabase Pro + Hetzner VPS |
| Post-launch growth | ~$55–110/mo | Full production stack at real user scale |

**The goal is to reach launch on ~$2–5/mo.** Contingency upgrades are triggered by real problems — rate limits actually hit, DB actually pausing — not by a phase gate.
