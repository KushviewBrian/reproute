# Route-Based Prospecting App

## Full Design and Development Plan (v4 — PWA-first, Free-stack, Migration-safe)

---

# 1. Product Definition

## 1.1 Product purpose

This product is a **route-aware prospecting tool for field insurance agents**.

Its job is simple:

> Turn an agent's existing drive into a ranked list of local small-commercial businesses that are worth stopping for.

This is not:

* a full CRM
* an underwriting engine
* a generic business directory
* an AI lead oracle
* a maps browser

It is:

> **A spatial filtering engine for physical-world sales decisions**

The product succeeds if an agent can enter a route, glance at the results, and say:

> "Yes, these look like businesses I would actually stop at."

That is the north star.

---

# 2. Product Scope and Strategy

## 2.1 Core strategic principle

Build the **smallest system that reliably produces good stops**.

That means the first version should optimize for:

* usefulness
* clarity
* speed
* trust
* low operational complexity

It should not optimize for:

* maximum data completeness
* rich AI features
* full business intelligence
* perfect routing sophistication
* full sales workflow automation

---

## 2.2 MVP promise

> "Show me the best stop-worthy small-commercial businesses along my route."

That is specific, testable, and realistic.

---

## 2.3 User

Primary user:

* field-oriented insurance agent
* small commercial focus
* already driving between appointments, territories, home, and office
* wants local businesses that are physically visitable and commercially relevant

Secondary future users:

* agency producers
* territory managers
* other route-based field sales reps

---

# 3. Product Boundaries

## 3.1 What the MVP does

The MVP will:

* accept a route (origin + destination, typed as addresses or place names)
* geocode those inputs to coordinates
* generate a route geometry via open routing service
* create a spatial corridor around the route
* find businesses near that corridor from a local PostGIS database
* score them on three dimensions (fit, distance, actionability)
* show them on a map and ranked list
* let the user save leads
* let the user add notes
* let the user export selected leads as CSV

---

## 3.2 What the MVP does not do

The MVP will not:

* scrape the web at large
* run deep enrichment pipelines
* predict underwriting fit
* optimize full route stop sequences
* sync with CRMs
* act as a team collaboration platform
* require a native app install (PWA handles mobile — see Section 4.1)
* use Google APIs for routing or place data

---

# 4. Technical Stack

## 4.1 Frontend — PWA (Progressive Web App)

* React (with TypeScript)
* MapLibre GL JS (v5.x — actively maintained, AWS-sponsored, BSD-3-Clause)
* Tailwind CSS
* **Built as a PWA from day one** — this is the mobile strategy (see Section 4.10)

**Why PWA instead of native app or plain web:**
* Installable on iOS and Android home screen — no App Store or Play Store required
* Works offline for saved leads and notes (service worker caches last results)
* GPS/location access for "use my current location" as route origin
* Click-to-call works natively on mobile
* One codebase — deploys like a website, feels like an app
* No Apple/Google review process or review delays
* Agents can use it on desktop too

**Design mobile-first.** The primary use case is an agent on their phone, between stops.

---

## 4.2 Backend

* **FastAPI** (Python)

Reasons:
* fast API development with async support
* strong geospatial ecosystem (GeoAlchemy2, Shapely, asyncpg)
* Pydantic v2 for GeoJSON validation and serialization
* easy integration with PostGIS
* packaged as a standard Docker container — platform-agnostic, trivial to migrate

---

## 4.3 Database

* **PostgreSQL** with **PostGIS** extension
* All geometries stored as `geography` type (SRID 4326) to ensure distance calculations use meters, not degrees
* GIST indexes on all geography columns
* **Treat the database as standard Postgres throughout** — avoid Supabase-specific features (RLS magic, Supabase Functions, etc.) so the DB can be migrated with `pg_dump` / `pg_restore` in under an hour

---

## 4.4 Routing

* **openrouteservice (ORS)** — public API for development and testing; stay on it through pilot unless rate limits are actually hit
  * Free tier limits are subject to change — **verify current plan limits at [openrouteservice.org/plans](https://openrouteservice.org/plans) before building SLO assumptions**
  * Returns GeoJSON route geometry
  * No native corridor query — corridor is built in PostGIS from route geometry (correct pattern)
  * Self-host ORS when (and only when) rate limits are actually hit under real load — see roadmap.md Phase 5 for the self-hosting procedure

**Self-hosting ORS (contingency):**
* Docker image available (GIScience/openrouteservice on GitHub)
* Requires ~8 GB RAM for a US regional road graph
* Runs on a $10–15/mo Hetzner VPS; same box hosts Photon and optionally the backend
* Alternative: **Valhalla** (lower memory footprint, also open source, also self-hostable)

Rate limit mitigation on public API: cache route geometries by origin+destination hash — do not re-request the same route twice. With aggressive caching a small pilot will not hit limits.

---

## 4.5 Geocoding

Users type origin and destination as strings. These must be converted to coordinates before routing.

**MVP: Photon** (Komoot) via backend proxy — OSM-backed, suited for autocomplete/typeahead
* Public endpoint is fair-use only (no SLA, can throttle)
* Self-host Photon on the same VPS as ORS if the public endpoint becomes unreliable — lightweight, negligible RAM overhead; see roadmap.md Phase 5 for procedure
* Returns GeoJSON with bounding box and coordinates

**Do not use Nominatim for autocomplete** — it is not designed for typeahead use cases.

**Geocoding cache via Cloudflare Workers KV** — cache responses at the edge (100K reads/day free):
* User types address → Workers KV checked first
* Cache hit: returns instantly, zero upstream call
* Cache miss: proxies to Photon, stores result (TTL: 24h)
* This is the primary quota protection mechanism

**Rate limit controls required before pilot** — the `/geocode` proxy must also enforce:
* Per-user rate limit: max 30 requests/minute (Redis counter)
* Circuit breaker: on upstream errors, return degraded "type full address" fallback — do not retry in a loop
* Never expose upstream geocoder URL to the frontend — all calls through backend proxy

For production scale beyond pilot: self-host Photon (free) or switch to a managed geocoder (OpenCage, Geoapify) — keep provider abstraction in place so this is a one-line config change.

---

## 4.6 Map tiles

**Protomaps / PMTiles on Cloudflare R2** — the correct free, commercial-use solution.

* Protomaps produces a single static PMTiles file (regional US extract: ~2–10 GB)
* Hosted on Cloudflare R2: 10 GB storage free, **10M read ops/month** free, **zero egress fees**
* MapLibre GL JS supports PMTiles natively
* Fully open, commercially usable, no per-request cost, no vendor lock-in
* No tile server to maintain — MapLibre reads the file directly via HTTP range requests

**Do not use MapTiler free tier for anything commercial** — it is explicitly non-commercial only. MapTiler paid plans (~$25/mo+) are an option if you want a managed fallback, but Protomaps + R2 is strictly better for this use case.

**Fallback options if R2 is unavailable:** Stadia Maps (has a commercial free tier), or self-host Martin tile server on the same VPS as ORS.

---

## 4.7 Place data

* **Overture Maps Places** as the primary and only business data source in MVP

**Important: Overture is a bulk data product, not a real-time API.** There is no REST endpoint for individual place lookups. Data is distributed as GeoParquet files on AWS S3 and accessed via:

* `pip install overturemaps` CLI (bounding box download)
* DuckDB queries against `s3://overturemaps-us-west-2/release/...` (most efficient for targeted pulls)
* Direct S3 download

Data is imported once into PostGIS and queried locally. This is an ingestion pipeline, not a live lookup.

---

## 4.8 Background jobs

* **RQ** (Redis Queue) — simpler than Celery for periodic import jobs, Redis-only, minimal config

For MVP the ingestion job may also be run manually as a script. A job queue becomes more important once refreshes need to be scheduled or monitored.

---

## 4.9 Authentication

Save leads, notes, and user identity require authentication.

**MVP choice: Clerk** (preferred) or Auth0
* Clerk Hobby tier: **50,000 MRU** free — covers MVP through early traction; verify current limits at clerk.com/pricing
* JWT-based, integrates with FastAPI middleware in ~1 day
* Frontend: Clerk React SDK for login/signup UI
* Backend: FastAPI dependency validates JWT on protected routes
* User record created on first login (email + name from JWT claims)

Do not roll your own auth in MVP.

---

## 4.10 PWA implementation requirements

These are the specific additions that make a React app a PWA — none are complex:

* **Web App Manifest** (`manifest.json`) — app name, icons, display mode (`standalone`), theme color
* **Service Worker** — use Vite PWA plugin (`vite-plugin-pwa`) which generates this automatically
* **Offline cache strategy:**
  * Cache shell (HTML/JS/CSS) — always available
  * Cache last route results and saved leads — agent can review while offline
  * Queue note writes when offline — sync when connection restores
* **GPS integration** — `navigator.geolocation.getCurrentPosition()` for "use my location" button on route entry screen
* **Icons** — provide 192x192 and 512x512 PNG icons for home screen install prompt

iOS note: iOS requires Safari for PWA install (no install prompt API, user must use "Add to Home Screen" manually). This is a known limitation; document it for agents.

---

## 4.11 Storage

* PostgreSQL for all structured data
* Cloudflare R2 for map tiles (PMTiles file)
* No additional object storage needed in MVP — exports stream directly from the API

---

# 5. Architecture Principles

## 5.1 Future-friendly, not feature-heavy

* Only one active data source in MVP: Overture
* Schema preserves source provenance and confidence fields
* API designed so more sources can be added later without rewrites
* Geography type used throughout (not geometry in degrees)
* Geocoding and tile provider are swappable behind a thin abstraction

## 5.2 Migration-safe by default (three rules)

Building on free tiers is fine. Moving off them later should take 1–2 days, not a rewrite. These three rules guarantee that:

**Rule 1: Treat Supabase as plain Postgres.**
Use only standard PostgreSQL + PostGIS. No Supabase RLS in application logic, no Supabase Edge Functions, no Supabase-specific extensions. The database migrates with `pg_dump` / `pg_restore` — one command.

**Rule 2: Cloudflare Workers is a cache and proxy layer only.**
No business logic in Workers. Workers does: geocode caching, rate limiting, static asset serving. All real logic stays in FastAPI. Removing Workers means updating one config value, not rewriting code.

**Rule 3: The backend is a Docker container with environment variables.**
No platform-specific env vars (`FLY_APP_NAME` etc.) in application code. No platform-specific health check formats. The Docker image runs identically on Fly.io, Railway, a VPS, or AWS ECS. Migrating the backend = redeploy the same image somewhere else.

## 5.3 Thin abstraction points to keep providers swappable

Wrap each external provider behind a single module:
* `geocode_service` — swap Photon → self-hosted Photon → managed geocoder by changing one config value
* `routing_service` — swap ORS public API → self-hosted ORS → Valhalla by changing one config value
* Tile URL — one constant in frontend config; changing tile provider = changing one string

---

# 6. Core Functional Flow

## Step 1 — Route input

User enters origin and destination as text strings.
Frontend calls geocoding API (Photon) to resolve each to coordinates.
Optional: typeahead autocomplete on each field.

## Step 2 — Route geometry

Backend calls ORS Directions API with origin/destination coordinates.
Returns GeoJSON LineString representing the driving route.
Route geometry + metadata stored in `route` table.

## Step 3 — Corridor generation

Backend calls PostGIS: `ST_Buffer(route_geom::geography, corridor_width_meters)` → returns corridor polygon.
Default corridor: 1 mile (1,609 meters).
User can adjust: 0.5 mi / 1 mi / 2 mi.

**Critical note:** Always buffer the `geography` type (or cast to it), never bare `geometry` in SRID 4326. Buffering raw WGS84 geometry uses degrees, not meters, producing wildly incorrect results.

## Step 4 — Business spatial query

PostGIS query: find all businesses where `ST_DWithin(business.geom, route_geom, corridor_width_meters)`.
GIST index on `business.geom` makes this fast.
Apply category pre-filter if user has selected specific insurance classes.

## Step 5 — Scoring

For each candidate:
* compute fit score (insurance class quality)
* compute distance score (meters from route line)
* compute actionability score (data completeness)
* compute final weighted score

Store results in `lead_score` table.

## Step 6 — Response

Return ranked list + summary stats to frontend.
Frontend renders list panel + map with pins.

## Step 7 — User actions

User saves businesses, adds notes, exports CSV.

---

# 7. Data Source: Overture Maps Places

## 7.1 What Overture provides

Overture Places is a free, open dataset (CDLA-Permissive-2.0) of global place records sourced from multiple providers (including Meta, Microsoft, Foursquare, and others listed in Overture attribution docs).

**Actual schema fields** (note: some names differ from naive assumptions):

| Field | Actual Overture name | Notes |
|---|---|---|
| name | `names` (object) | Sub-fields: primary, common, rule-based |
| coordinates | `geometry` (GeoJSON Point) | Standard GeoJSON |
| categories | `categories` + `taxonomy.primary` + `basic_category` | Use taxonomy primary value for fine-grained class mapping |
| address | `addresses` (array) | Structured object, plural |
| phone | `phones` (array) | Plural |
| website | `websites` (array) | Plural |
| brand | `brand` | Direct field |
| operating status | `operating_status` | Values: `open`, `temporarily_closed`, `permanently_closed` |
| confidence | `confidence` | 0.0–1.0 float |
| source provenance | `sources` (array) | Data lineage |

Additional fields: `socials`, `emails`, `bbox`, GERS `id`, `version`.

## 7.2 Access and ingestion

```bash
# Install CLI
pip install overturemaps

# Download places for a bounding box (returns GeoParquet)
overturemaps download --bbox=-87.94,41.64,-87.52,42.02 \
  --type=place -f geoparquet -o chicago_places.parquet

# Or query directly with DuckDB (most efficient for targeted pulls)
# duckdb query against s3://overturemaps-us-west-2/release/2026-03-18.0/...
```

Data releases are **monthly**. As of **April 14, 2026**, latest current release is `2026-03-18.0`.

## 7.3 Data quality expectations

* Strong coverage of US commercial businesses, especially those with social media presence
* Weaker coverage of: micro-businesses, cash-only operations, businesses without social profiles
* `operating_status` and `confidence` fields help filter stale records but do not eliminate them
* Some closed or moved businesses will appear in results — this is acceptable for a prospecting tool
* Users should treat results as "worth investigating" not "guaranteed current"

## 7.4 Why not OSM-first

* OSM uses flat untyped `key=value` tags with no enforced schema
* Phone/address fields may be `phone`, `contact:phone`, `telephone`, or absent
* No confidence score
* Inconsistent category tagging

Overture's advantage is structural normalization, not necessarily higher accuracy. OSM may be added as a supplemental source in Phase 2.

---

# 8. Data Model

## 8.1 user

```sql
CREATE TABLE "user" (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT NOT NULL UNIQUE,
  full_name     TEXT,
  organization  TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
);
```

---

## 8.2 business

Canonical business record. Ingested from Overture; schema supports future sources.

```sql
CREATE TABLE business (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_source      TEXT NOT NULL,          -- 'overture'
  external_id          TEXT NOT NULL,
  name                 TEXT NOT NULL,
  normalized_name      TEXT,
  brand_name           TEXT,
  category_primary     TEXT,
  category_secondary   TEXT,
  insurance_class      TEXT,
  address_line1        TEXT,
  city                 TEXT,
  state                TEXT,
  postal_code          TEXT,
  country              TEXT DEFAULT 'US',
  phone                TEXT,
  website              TEXT,
  operating_status     TEXT,                   -- open / temporarily_closed / permanently_closed / unknown
  confidence_score     NUMERIC(4,3),           -- 0.000–1.000
  geom                 GEOGRAPHY(Point, 4326) NOT NULL,
  has_phone            BOOLEAN GENERATED ALWAYS AS (phone IS NOT NULL) STORED,
  has_website          BOOLEAN GENERATED ALWAYS AS (website IS NOT NULL) STORED,
  has_address          BOOLEAN GENERATED ALWAYS AS (address_line1 IS NOT NULL) STORED,
  source_payload_json  JSONB,
  created_at           TIMESTAMPTZ DEFAULT now(),
  updated_at           TIMESTAMPTZ DEFAULT now(),
  last_seen_at         TIMESTAMPTZ,
  last_validated_at    TIMESTAMPTZ,

  UNIQUE (external_source, external_id)
);

CREATE INDEX idx_business_geom ON business USING GIST (geom);
CREATE INDEX idx_business_insurance_class ON business (insurance_class);
CREATE INDEX idx_business_operating_status ON business (operating_status);
```

---

## 8.3 route

```sql
CREATE TABLE route (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                 UUID REFERENCES "user"(id),
  origin_label            TEXT,
  destination_label       TEXT,
  origin_lat              NUMERIC(10,7) NOT NULL,
  origin_lng              NUMERIC(10,7) NOT NULL,
  destination_lat         NUMERIC(10,7) NOT NULL,
  destination_lng         NUMERIC(10,7) NOT NULL,
  route_geom              GEOGRAPHY(LineString, 4326),
  route_distance_meters   INTEGER,
  route_duration_seconds  INTEGER,
  corridor_width_meters   INTEGER DEFAULT 1609,
  ors_response_json       JSONB,
  created_at              TIMESTAMPTZ DEFAULT now(),
  updated_at              TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_route_geom ON route USING GIST (route_geom);
CREATE INDEX idx_route_user ON route (user_id);
```

---

## 8.4 route_candidate

Businesses matched to a route after spatial query.

```sql
CREATE TABLE route_candidate (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  route_id                  UUID NOT NULL REFERENCES route(id) ON DELETE CASCADE,
  business_id               UUID NOT NULL REFERENCES business(id),
  distance_from_route_m     NUMERIC(10,2),
  within_corridor           BOOLEAN DEFAULT TRUE,
  created_at                TIMESTAMPTZ DEFAULT now(),

  UNIQUE (route_id, business_id)
);

CREATE INDEX idx_route_candidate_route ON route_candidate (route_id);
```

---

## 8.5 lead_score

Score breakdown per business per route.

```sql
CREATE TABLE lead_score (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  route_id                UUID NOT NULL REFERENCES route(id) ON DELETE CASCADE,
  business_id             UUID NOT NULL REFERENCES business(id),
  fit_score               SMALLINT CHECK (fit_score BETWEEN 0 AND 100),
  distance_score          SMALLINT CHECK (distance_score BETWEEN 0 AND 100),
  actionability_score     SMALLINT CHECK (actionability_score BETWEEN 0 AND 100),
  final_score             SMALLINT CHECK (final_score BETWEEN 0 AND 100),
  score_version           TEXT DEFAULT 'v1',
  score_explanation_json  JSONB,
  created_at              TIMESTAMPTZ DEFAULT now(),

  UNIQUE (route_id, business_id)
);
```

---

## 8.6 saved_lead

```sql
CREATE TABLE saved_lead (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES "user"(id),
  route_id    UUID REFERENCES route(id),
  business_id UUID NOT NULL REFERENCES business(id),
  status      TEXT DEFAULT 'saved',   -- saved / visited / called / not_interested / follow_up
  priority    SMALLINT DEFAULT 0,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now(),

  UNIQUE (user_id, business_id)
);
```

---

## 8.7 note

```sql
CREATE TABLE note (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES "user"(id),
  business_id     UUID NOT NULL REFERENCES business(id),
  route_id        UUID REFERENCES route(id),
  note_text       TEXT NOT NULL,
  outcome_status  TEXT,
  next_action     TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_note_business ON note (business_id);
CREATE INDEX idx_note_user ON note (user_id);
```

---

# 9. Business Classification

## 9.1 Insurance class taxonomy

| Class | Description |
|---|---|
| Retail | Shops, hardware, clothing, electronics, gifts |
| Food & Beverage | Restaurants, cafes, bars, bakeries, food trucks |
| Auto Service | Auto repair, tires, oil change, car wash, body shop |
| Personal Services | Salon, barber, nail, spa, dry cleaning, alterations |
| Professional / Office | Attorney, accounting, insurance agency, real estate, consulting |
| Contractor / Trades | Plumbing, HVAC, electrical, roofing, landscaping |
| Medical / Clinic | Dentist, optometrist, chiro, urgent care, physical therapy |
| Light Industrial | Small manufacturing, fabrication, storage units |
| Other Commercial | Legitimate commercial that doesn't fit above |
| Exclude | Schools, churches, parks, government, residential, hospitals |

## 9.2 Classification method (MVP: rule-based only)

**Important: do not hardcode `taxonomy.primary` keys — they change between releases.**

The Overture taxonomy has 2,100+ values and has been significantly renamed/reparented across recent releases (407 renames, 482 reparentings between schema v1.13 and v1.15 alone). A hardcoded key lookup will silently misclassify large numbers of records after any Overture update.

### Use `basic_category` as the stable mapping target

Overture introduced `basic_category` in October 2025 — approximately 280 "cognitively basic" labels (e.g., `restaurant`, `museum`, `auto_repair`) designed to be more stable across releases than the full `taxonomy.primary` values. **Map against `basic_category` first**, fall back to `taxonomy.primary` only for values not covered.

### Generate the mapping from the official taxonomy CSV

The canonical taxonomy source is:

```
https://raw.githubusercontent.com/OvertureMaps/schema/main/docs/schema/concepts/by-theme/places/overture_categories.csv
```

This CSV has 2,117+ rows with columns: `category_code` (the `taxonomy.primary` value) and `hierarchy` (the ordered parent chain as a bracket-enclosed list, e.g., `[eat_and_drink,restaurant]`).

**The correct workflow:**

1. At ingestion time, download this CSV fresh (pin to a specific schema release tag to match your data release)
2. Parse it into a dict of `{category_code: hierarchy_list}`
3. Use `basic_category` as the primary classification key, with `taxonomy.hierarchy` as the fallback
4. Map by traversing the hierarchy array — check if a known parent appears **anywhere** in the hierarchy (do not rely on array index positions, which change between releases)

**Example hierarchy-based classification logic:**

```python
# Map hierarchy parent tokens → insurance class
# These are stable L0/L1 hierarchy values, not leaf taxonomy keys
HIERARCHY_CLASS_MAP = [
    # (hierarchy_token, insurance_class)   — checked in order, first match wins
    ("eat_and_drink",        "Food & Beverage"),
    ("automotive",           "Auto Service"),        # includes auto_repair, car_wash, tire_shop
    ("personal_care",        "Personal Services"),   # salon, barber, nail, spa
    ("professional_services","Professional / Office"),
    ("financial_services",   "Professional / Office"),
    ("legal_services",       "Professional / Office"),
    ("real_estate",          "Professional / Office"),
    ("home_improvement",     "Contractor / Trades"),
    ("construction",         "Contractor / Trades"),
    ("health_and_medical",   "Medical / Clinic"),
    ("retail",               "Retail"),
    ("education",            "Exclude"),
    ("government_and_community", "Exclude"),
    ("parks_outdoors",       "Exclude"),
    ("religious",            "Exclude"),
    ("hospital",             "Exclude"),             # specific leaf under health_and_medical
]

BASIC_CATEGORY_CLASS_MAP = {
    # direct basic_category → insurance_class overrides
    "restaurant": "Food & Beverage",
    "bar": "Food & Beverage",
    "cafe": "Food & Beverage",
    "auto_repair": "Auto Service",
    "car_wash": "Auto Service",
    "gas_station": "Exclude",        # not a commercial prospect
    "insurance_agency": "Professional / Office",
    "dentist": "Medical / Clinic",
    "hospital": "Exclude",
    "school": "Exclude",
    "place_of_worship": "Exclude",
    "park": "Exclude",
}

def classify(basic_category: str, hierarchy: list[str]) -> str:
    # 1. Try basic_category direct map first
    if basic_category in BASIC_CATEGORY_CLASS_MAP:
        return BASIC_CATEGORY_CLASS_MAP[basic_category]
    # 2. Traverse hierarchy for a known parent token
    hierarchy_set = set(h.lower() for h in hierarchy)
    for token, ins_class in HIERARCHY_CLASS_MAP:
        if token in hierarchy_set:
            return ins_class
    # 3. Fallback
    return "Other Commercial"
```

This approach:
* stays correct across Overture releases (hierarchy parent tokens are stable even when leaf values rename)
* degrades gracefully to "Other Commercial" instead of silent misclassification
* can be audited by logging the distribution of `basic_category` values that fell through to "Other Commercial"

### Refresh the mapping at each Overture data update

After each monthly Overture import, run a QA check on the `insurance_class` distribution. Any unusual spike in "Other Commercial" indicates new taxonomy values that need to be mapped. Consult the release notes at the Overture schema GitHub releases page for category changes.

### Fallback: keyword matching on business name

If both `basic_category` and `taxonomy.primary` are null (this does occur in a small fraction of records), fall back to keyword matching on the business `name` field:

```python
NAME_KEYWORD_MAP = [
    (["restaurant", "grill", "kitchen", "diner", "cafe", "pizza", "sushi"], "Food & Beverage"),
    (["auto", "tire", "muffler", "brake", "oil change", "body shop"],       "Auto Service"),
    (["salon", "barber", "nail", "spa", "beauty"],                          "Personal Services"),
    (["law", "attorney", "cpa", "accounting", "insurance", "realty"],       "Professional / Office"),
    (["plumb", "electric", "hvac", "roofing", "landscap", "contractor"],    "Contractor / Trades"),
    (["dental", "dentist", "optom", "chiropract", "clinic", "therapy"],     "Medical / Clinic"),
]
```

Store the final `insurance_class` on the `business` record at ingestion time.
Reclassification is a simple re-run of the mapping script against existing records — no re-download needed.

---

# 10. Scoring Model

## 10.1 Scoring principle

Score **field usability**, not probability of buying insurance.

The agent is deciding:
* is this the right kind of business?
* is it easy enough to stop?
* can I act on it right now?

## 10.2 Score dimensions

### Fit Score — 40%

Is this the right kind of business?

| Condition | Score |
|---|---|
| Highly desirable class (Auto Service, Contractor, Retail) | 90–100 |
| Good class (Food & Beverage, Personal Services, Medical) | 70–89 |
| Borderline class (Other Commercial) | 40–69 |
| Excluded / low priority | 0–20 |

---

### Distance Score — 30%

Is this easy enough to stop at?

| Distance from route line | Score |
|---|---|
| 0–250 m | 100 |
| 250–750 m | 80 |
| 750–1,500 m | 60 |
| 1,500–3,000 m | 35 |
| 3,000 m+ | 10 |

Distance is computed using `ST_Distance(business.geom::geography, route.route_geom::geography)` — returns meters.

---

### Actionability Score — 30%

Can I do something with this right now?

| Data present | Score |
|---|---|
| Address + phone + website | 100 |
| Address + phone | 80 |
| Address + website | 70 |
| Address only | 50 |
| No address | 10 |

Apply confidence modifier: multiply by `max(confidence_score, 0.5)` if confidence < 0.7.

---

## 10.3 Final score formula

```
final_score = round(
  (fit_score * 0.40) +
  (distance_score * 0.30) +
  (actionability_score * 0.30)
)
```

Range: 0–100. Display as integer.

## 10.4 Score explanation (required for trust)

Each lead must show a plain-language explanation. Store in `score_explanation_json`:

```json
{
  "fit": "Strong fit: Auto Service",
  "distance": "Very close to route (180m)",
  "actionability": "Has phone and website"
}
```

Display all three lines on the lead card. This is the primary trust signal.

## 10.5 Score version

Always store `score_version` (e.g., `"v1"`) so historical scores can be identified and recomputed when weights change.

---

# 11. Route and Corridor Logic

## 11.1 Route creation flow

1. Frontend geocodes origin + destination strings via Photon API
2. `POST /routes` receives coordinates + corridor width
3. Backend calls ORS Directions API (`/v2/directions/driving-car`) with GeoJSON output
4. Store response: route LineString geometry, distance, duration
5. Corridor polygon generated on demand at query time via `ST_Buffer(route_geom::geography, width_meters)`
6. Return `route_id` + polyline to frontend for immediate map display

## 11.2 Corridor presets

| Label | Meters | Miles |
|---|---|---|
| Narrow | 805 | 0.5 |
| Standard (default) | 1,609 | 1.0 |
| Broad | 3,218 | 2.0 |

Store `corridor_width_meters` on the route record. User can change it and re-query without regenerating the route.

## 11.3 Candidate query (PostGIS)

```sql
-- Preferred: ST_DWithin is index-aware and avoids materializing a buffer polygon
SELECT
  b.id,
  b.name,
  b.insurance_class,
  b.address_line1,
  b.city,
  b.phone,
  b.website,
  b.confidence_score,
  b.has_phone,
  b.has_website,
  b.has_address,
  ST_Distance(b.geom::geography, r.route_geom::geography) AS distance_from_route_m
FROM business b
CROSS JOIN route r
WHERE r.id = :route_id
  AND b.insurance_class != 'Exclude'
  AND ST_DWithin(b.geom::geography, r.route_geom::geography, r.corridor_width_meters)
ORDER BY distance_from_route_m ASC;
```

`ST_DWithin` uses the GIST index automatically. Do not use `ST_Intersects(ST_Buffer(...))` — it materializes the full polygon and is slower.

---

# 12. API Design

All endpoints require authentication (JWT Bearer token) except `/health`. If `/geocode` is exposed pre-auth, apply strict rate limiting and caching.

## 12.1 Route endpoints

### POST /routes

Create a route and trigger candidate matching + scoring.

Request:
```json
{
  "origin_label": "123 Main St, Chicago IL",
  "origin_lat": 41.8781,
  "origin_lng": -87.6298,
  "destination_label": "456 Oak Ave, Naperville IL",
  "destination_lat": 41.7508,
  "destination_lng": -88.1535,
  "corridor_width_meters": 1609
}
```

Response:
```json
{
  "route_id": "uuid",
  "route_distance_meters": 35200,
  "route_duration_seconds": 1820,
  "lead_count": 47,
  "polyline": "encoded_or_geojson"
}
```

---

### GET /routes/{route_id}

Return route metadata and summary stats.

---

### GET /routes/{route_id}/leads

Return ranked leads for a route.

Query params:
* `insurance_class` (multi-value)
* `min_score` (integer, default 40)
* `has_phone` (boolean)
* `has_website` (boolean)
* `limit` (default 50, max 200)
* `offset`

Response:
```json
{
  "route_id": "uuid",
  "leads": [
    {
      "business_id": "uuid",
      "name": "Ace Auto Repair",
      "insurance_class": "Auto Service",
      "address": "789 Elm St, Lisle IL 60532",
      "phone": "630-555-0100",
      "website": "aceauto.com",
      "final_score": 87,
      "fit_score": 95,
      "distance_score": 90,
      "actionability_score": 80,
      "distance_from_route_m": 210,
      "explanation": {
        "fit": "Strong fit: Auto Service",
        "distance": "Very close to route (210m)",
        "actionability": "Has phone and website"
      },
      "lat": 41.80,
      "lng": -88.07
    }
  ],
  "total": 47,
  "filtered": 22
}
```

---

### PATCH /routes/{route_id}

Update corridor width and re-score (without re-calling ORS).

---

## 12.2 Geocoding proxy

### GET /geocode?q={query}

Proxies to Photon. Returns top 5 candidates with label + coordinates.

Proxy geocoding through the backend to avoid exposing external API endpoints to the frontend and to allow easy provider swaps.

---

## 12.3 Business endpoints

### GET /businesses/{business_id}

Full business detail.

---

## 12.4 Saved leads

### POST /saved-leads

```json
{ "business_id": "uuid", "route_id": "uuid" }
```

### GET /saved-leads

Query params: `status`, `limit`, `offset`

### PATCH /saved-leads/{id}

Update status or priority.

### DELETE /saved-leads/{id}

---

## 12.5 Notes

### POST /notes

```json
{
  "business_id": "uuid",
  "route_id": "uuid",
  "note_text": "Owner out, try Friday morning",
  "outcome_status": "follow_up",
  "next_action": "Call Friday"
}
```

### GET /notes?business_id={id}

### PATCH /notes/{id}

---

## 12.6 Export

### GET /export/routes/{route_id}/leads.csv

Returns CSV of leads for a route (all or filtered by saved status).

Columns: name, address, phone, website, insurance_class, final_score, distance_m, status, notes

---

## 12.7 Admin / ingestion

Not public-facing.

### POST /admin/import/overture

Trigger import job for a bounding box.

Request: `{ "bbox": [-87.94, 41.64, -87.52, 42.02], "label": "chicago" }`

### GET /admin/import/jobs/{id}

Job status + stats.

---

# 13. Backend Services

## 13.1 geocode_service

* Proxies address string queries to Photon
* Returns normalized `{label, lat, lng}` candidates
* Future: swap provider without changing API contract

## 13.2 route_service

* Calls ORS Directions API
* Parses GeoJSON response
* Stores route geometry as `geography(LineString, 4326)`
* Caches by origin+destination hash to avoid duplicate ORS calls

## 13.3 business_search_service

* Runs `ST_DWithin` spatial query
* Applies category pre-filter
* Returns raw candidates with distance

## 13.4 classification_service

* Maps Overture `basic_category` → `insurance_class` (primary path)
* Falls back to `taxonomy.hierarchy` traversal if `basic_category` is not in the map
* Falls back to keyword matching on `name` if both category fields are null
* Do NOT hardcode `taxonomy.primary` leaf values — they rename between releases
* Run at ingestion time, stored on business record
* Reclassification = re-run script against existing records, no re-download or rescoring needed
* After each monthly Overture refresh: run `insurance_class` distribution check; spike in "Other Commercial" signals new taxonomy values needing mapping

## 13.5 scoring_service

* Accepts list of candidates with distances
* Computes fit, distance, actionability per business
* Builds score explanation
* Returns sorted list

## 13.6 lead_service

* Orchestrates search → score → store → return
* Applies user filters (min_score, insurance_class, etc.)
* Returns final ranked payload

## 13.7 export_service

* Generates CSV from lead list + notes
* Streams to response (no temp file needed for MVP)

---

# 14. Ingestion Pipeline

## 14.1 Process

```
1. Identify target bounding box (e.g., Chicago metro: -87.94,41.64,-87.52,42.02)
2. Download Overture Places GeoParquet via CLI or DuckDB
3. Parse GeoParquet with geopandas or DuckDB
4. Normalize fields:
   - names.primary → name
   - addresses[0] fields → address_line1, city, state, postal_code
   - phones[0] → phone
   - websites[0] → website
   - basic_category → category_primary (stable ~280-value label; preferred mapping key)
   - taxonomy.primary → category_secondary (2,100+ specific value; use for hierarchy traversal)
   - taxonomy.hierarchy → used at classification time, not stored directly
   - Note: categories.primary is deprecated and will be removed June 2026 — do not use
   - confidence → confidence_score
   - operating_status → operating_status
5. Run classification_service → insurance_class
6. Filter: drop operating_status = 'permanently_closed'
7. Filter: drop insurance_class = 'Exclude'
8. Insert into business table (upsert on external_source + external_id)
9. Update GIST index
10. Run QA checks
```

## 14.2 QA checks after import

Validate and log:

* Total rows inserted
* Missing name rate (should be < 1%)
* Missing geometry rate (should be 0%)
* Missing category rate (flag if > 20%)
* Percent with phone
* Percent with website
* Percent operating_status = 'open'
* Duplicate name+address clusters (flag for review)
* Insurance class distribution

## 14.3 Geography strategy

Start with **one metro or focused multi-county area** where target agents work.

Reasons:
* faster iteration
* manageable dataset size (hundreds of MB, not tens of GB)
* easier to manually inspect results
* easier to QA data quality

Single US state Overture extract: ~1–5 GB Parquet depending on population density.

## 14.4 Refresh strategy

* Overture releases monthly (as of 2026-04-14: current `2026-03-18.0`)
* Schedule a monthly re-import job (RQ + cron or simple scheduled task)
* Use upsert on `(external_source, external_id)` — new records added, existing records updated
* After refresh: rerun classification, rerun scoring for active routes (or invalidate cached scores)

---

# 15. User Interface Design

## 15.1 UX principles

* glanceable
* field-friendly
* low-click
* list-driven, map-supported (the list drives action; the map builds spatial trust)
* confidence-building (score explanation always visible)

## 15.2 Base map tiles

Use **Protomaps + Cloudflare R2** (see Section 4.6 — this is the locked MVP tile strategy):
* Download a regional PMTiles extract for the target metro from protomaps.com
* Upload to Cloudflare R2 (free: 10 GB storage, 10M reads/month, zero egress)
* Configure MapLibre with a PMTiles source pointing to the R2 URL
* No API key, no per-request cost, commercially usable

Do not use MapTiler free tier — it is non-commercial only and contradicts the MVP decision lock.

## 15.3 Screens

### Screen 1: Route Entry

Components:
* Origin text input with geocode autocomplete (calls `/geocode?q=...` on debounce)
* Destination text input with geocode autocomplete
* Corridor width selector (0.5 / 1 / 2 miles)
* Category filter (multi-select, optional)
* "Find Prospects" button (disabled until both inputs resolve to coordinates)
* Recent routes list (optional, Phase 2)

---

### Screen 2: Lead Discovery

Layout: left panel (lead list) + right panel (map)

List item:
* Business name
* Insurance class badge
* Final score (large, prominent)
* Distance from route
* Phone / website indicators
* Score explanation (fit / distance / actionability lines)
* Quick save button

Top controls:
* Corridor width (re-queries without new ORS call)
* Insurance class filter
* Min score slider (default: 40)
* "Has phone" toggle
* "Has website" toggle

Map:
* Route line
* Business pins (colored by insurance class or score)
* Click pin → show lead detail

---

### Screen 3: Lead Detail (drawer or modal)

* Business name, address, phone (click-to-call), website (click-to-open)
* Insurance class
* Score breakdown (fit / distance / actionability with explanation text)
* Map position
* Save lead button + status selector
* Add / view notes

---

### Screen 4: Saved Leads

* List of saved businesses across all routes
* Filter by status
* Priority marker (drag or click to reorder)
* Notes preview
* Export CSV button
* Click → Lead Detail

---

### Screen 5: Notes (embedded in Lead Detail)

No separate CRM screen. Notes live inside the lead detail view.

Fields:
* Freeform text
* Outcome status (dropdown)
* Next action (text)
* Timestamp (auto)

---

# 16. Filtering Strategy

## 16.1 MVP filters (all applied client-side after initial results load, or as query params)

* Insurance class (multi-select)
* Minimum score (slider, 0–100)
* Corridor width (triggers re-query)
* Has phone (toggle)
* Has website (toggle)

## 16.2 Future filters

* Operating status (open only)
* Chain/brand detection
* Saved status
* Previously visited
* Route side preference (left/right of direction of travel)
* Distance from route (more granular)

---

# 17. Lead Workflow

## 17.1 Lead statuses

| Status | Meaning |
|---|---|
| Saved | Added to list, not yet acted on |
| Visited | Physically stopped by |
| Called | Contacted by phone |
| Not Interested | Ruled out |
| Follow Up | Worth coming back to |

## 17.2 Notes

Allow freeform text + optional outcome status per note.
Multiple notes per business are supported (append-only log).

---

# 18. Success Metrics

## 18.1 Primary metric

The product works if agents say:

> "These are businesses I would actually stop at."

## 18.2 Quantitative targets (initial)

* 15–30 leads per route after filtering
* 3–10 saved leads per route
* Under 5 seconds to return results after route creation
* At least 60% of shown leads judged "reasonable stop candidates" by test agents
* At least 40% of tested routes produce 5+ save-worthy leads

## 18.3 Post-session evaluation questions

* Were the results relevant?
* Were there enough choices?
* Were they close enough to the route?
* Did the score feel trustworthy?
* Would you use this instead of manually scanning maps?

---

# 19. Development Roadmap

> **`roadmap.md` is the authoritative source for phases, task checklists, definitions of done, and pilot gates.**
> This section is a summary only. For the full build plan, refer to `roadmap.md`.

## Phase summary

| Phase | Name | Duration |
|---|---|---|
| 0 | Foundation | 3–5 days |
| 1 | Data and routing | 5–7 days |
| 2 | Classification and scoring | 4–5 days |
| 3 | Discovery UI | 5–7 days |
| 4 | Save, notes, export | 3–4 days |
| 5 | Pre-pilot hardening | 3–4 days |
| 6 | Agent validation | 5–7 days |
| 7 | Polish and launch | 3–5 days |

**Total: ~6–7 weeks solo.**

## Pilot gate policy

The free stack (ORS public API, Photon public endpoint, Supabase free tier) stays in place through launch. Contingency upgrades — self-hosted ORS/Photon on a VPS, Supabase Pro — are triggered only when a specific problem actually occurs (rate limits hit, DB pauses during active use). They are not phase gates. See `roadmap.md` Phase 5 for trigger conditions and procedures.

# 20. Execution Timeline

## Weekly milestones

**Week 1:** Phase 0 + Phase 1 — skeleton running, ingestion done, routing and spatial query working

**Week 2:** Phase 2 + Phase 3 start — scoring engine live, lead list UI begun

**Week 3:** Phase 3 complete + Phase 4 — full discovery UI on mobile, save/notes/export done

**Week 4:** Phase 5 — pre-pilot hardening, performance confirmed, rate limits tested

**Week 5:** Phase 6 — agent validation sessions

**Week 6:** Phase 7 + buffer — polish, launch, feedback iteration

3 calendar weeks reaches a testable state (no auth, no save/notes/export, minimal UI) but not a pilot-ready product. The full MVP through launch is a 6–7 week solo build.

---

# 21. Team Roles

## Solo founder version

One person can build this MVP if comfortable with:
* React + TypeScript
* Python (FastAPI, SQLAlchemy/asyncpg)
* PostgreSQL / PostGIS
* Data wrangling (GeoParquet, pandas/DuckDB)
* Basic DevOps (Docker, environment management)

## Lean team version

* 1 full-stack engineer (core product)
* 1 product/designer (UX, test coordination)
* 1 domain advisor / test agent (insurance agent providing feedback)

---

# 22. Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Weak lead relevance — results don't feel useful | Medium | Test with real agents in Phase 5; tune category mapper and score weights early |
| Overture gaps or stale records | Medium | Start in one metro; manual inspection; preserve confidence fields; plan monthly refresh |
| Taxonomy drift — Overture renames category values between releases | Medium | Use `basic_category` + hierarchy traversal (not hardcoded leaf keys); QA class distribution after each refresh |
| ORS rate limits change or tighten | Low-Medium | Verify current limits at implementation time; cache by route hash; plan self-hosting before multi-user pilot |
| Geocode autocomplete burning provider quota | Medium | Per-user rate limit (30 req/min) + response caching (24h TTL) enforced on backend proxy before pilot |
| PostGIS buffer bug (degrees not meters) | High if unmitigated | **Always use `geography` type or explicit cast — enforced in schema and query** |
| MapTiler free tier used for commercial product | Resolved | Use Protomaps + Cloudflare R2 instead — commercially free, zero egress cost |
| UI too complex for field use | Low | Keep list primary; score explanation always visible; minimize clicks |
| Scope creep | Medium | Lock Phase 2+ features; enforce MVP decision list in Section 25 |
| Timeline overrun | Medium | 6–7 week estimate is conservative; cut export/notes to hit 4 weeks if needed |

---

# 23. Infrastructure and Hosting

## 23.1 Local development

```
Docker Compose:
  - postgres:16-postgis
  - redis (for RQ)
  - fastapi (uvicorn --reload)
  - react dev server (vite)
```

All free. No external accounts needed to develop locally.

---

## 23.2 Hosted stack — low-cost launch

Most components below have free tiers; total cost is ~$0–10/month depending on Fly.io usage:

| Component | Provider | Free tier details |
|---|---|---|
| **Frontend (PWA)** | Cloudflare Pages | Unlimited bandwidth, unlimited static asset requests; note: Pages Functions (if used) fall under Workers plan limits — keep all logic in FastAPI, not Functions |
| **Backend (FastAPI)** | Fly.io | Fly no longer has a permanent free tier for new accounts — expect PAYG billing (~$2–5/mo for a small always-on instance); verify current pricing at fly.io/pricing before assuming $0 |
| **Database (PostGIS)** | Supabase free tier | 500 MB storage, 2 shared CPU — fits one metro |
| **Redis** | Upstash free tier | 10,000 commands/day — enough for caching + rate limiting |
| **Map tiles** | Cloudflare R2 (Protomaps) | 10 GB storage, **10M reads/month** free, zero egress fees |
| **Geocoding cache** | Cloudflare Workers KV | 100K reads/day, 1K writes/day — edge-cached geocode responses |
| **Routing** | ORS public API | Fair-use; rate-limited — cache aggressively by route hash |
| **Geocoding** | Photon public endpoint | Fair-use; proxied + cached via Workers KV |
| **Auth** | Clerk Hobby tier | **50,000 MRU (monthly active users)** free — verify current limits at clerk.com/pricing |
| **CI/CD** | GitHub Actions | 2,000 minutes/month |
| **Container registry** | GitHub Container Registry | Free for public; free private with storage limits |
| **DNS + SSL** | Cloudflare | Free |

**Total: ~$0–10/month** (Fly.io PAYG is the only likely non-zero cost; all other components have usable free tiers)

> Note: free tier terms change. Verify all limits at provider pricing pages before committing to cost assumptions.

### Supabase free tier caveat
Supabase pauses inactive databases after **7 days of inactivity**. During active development and a live pilot where agents use the app daily, this will not trigger. If the DB pauses, it resumes immediately on next connection — it is a nuisance, not a data loss event. **Upgrade to Supabase Pro ($25/mo) only if the pause actually causes problems**, not preemptively.

---

## 23.3 Contingency upgrades (pay when you hit the trigger, not before)

The free stack handles development, testing, and a small pilot. Upgrade individual components only when a specific trigger occurs:

| Trigger | Upgrade | Cost |
|---|---|---|
| Supabase DB pauses during active pilot use | Supabase Pro | +$25/mo |
| ORS public API rate limits hit under real load | Hetzner CAX21 VPS — self-host ORS + Photon | +$10–15/mo |
| Photon public endpoint throttled or unreliable | Self-host Photon on same VPS as ORS | included above |
| Fly.io costs exceed ~$10/mo | Move backend to same VPS as ORS | replaces Fly cost |

**If no triggers hit:** stay on the free stack through launch. Total remains ~$2–5/mo.
**If all triggers hit at once:** ~$35–45/mo — still cheap.

---

## 23.4 Production stack (at real user scale)

| Component | Option | Est. cost |
|---|---|---|
| Database | Supabase Pro or Neon Pro | $25/mo |
| Backend | Fly.io paid or consolidated on VPS | $10–20/mo |
| ORS + Photon | Hetzner VPS (8–16 GB RAM) | $20–40/mo |
| Auth | Clerk (scales with MAU) | $0–25/mo |
| Tiles | Cloudflare R2 (stays free at this scale) | $0 |
| CI/CD | GitHub Actions (stays free) | $0 |

**Total: ~$55–110/mo**

---

## 23.5 CI/CD pipeline (GitHub Actions)

```
push to main
  → run tests (pytest + spatial query regression)
  → build Docker image
  → push to ghcr.io
  → deploy backend to Fly.io (flyctl deploy)
  → build frontend (npm run build)
  → deploy to Cloudflare Pages (wrangler pages deploy)
```

All free. Fully automated on every push to main.

---

## 23.6 Commercial platform migration (if needed)

If you outgrow the free stack and want to move to AWS / GCP / Azure:

| Component | Migration effort |
|---|---|
| Database (Supabase → RDS/self-hosted) | `pg_dump` + `pg_restore` — ~1 hour |
| Backend (Fly.io → ECS/VPS) | Redeploy same Docker image — ~2 hours |
| Frontend (CF Pages → S3+CloudFront) | `npm run build` + upload — ~30 min |
| Tiles (R2 → S3) | Copy files, update one URL constant — ~1 hour |
| Geocode cache (Workers KV → Redis) | Remove Worker, point proxy at backend cache — ~2 hours |
| Redis (Upstash → ElastiCache/self-hosted) | Change one env var — ~10 min |
| Auth (Clerk → Auth0/Cognito) | JWT validation code change — ~half a day |

**Total realistic migration: 1–2 days of focused work — not a rewrite.**

This is guaranteed by the three migration-safety rules in Section 5.2: plain Postgres, thin Cloudflare layer, Docker + env vars throughout.

---

# 24. Post-MVP Expansion Plan

## Phase 2 additions (after usefulness is proven)

* Basic chain/brand detection (flag franchises, deprioritize large chains)
* OSM supplemental candidates (fill gaps in Overture)
* Saved routes (re-run previous route with fresh data)
* Improved scoring weights (informed by real agent feedback)
* Repeat territory mode (flag previously visited businesses)

## Phase 3 additions

* Google Places validation as optional premium enrichment
* Stop-order optimization (reorder saved leads by drive efficiency)
* CRM integration (HubSpot, Salesforce export)
* Agency/team workspace (shared territories, shared saved leads)
* Background GPS / location-aware suggestions (deeper native integration beyond PWA capability — React Native at this stage)

---

# 25. MVP Decision Lock

These decisions are locked to prevent drift:

1. **Only one business data source: Overture**
2. **Open routing only: ORS (not Google)**
3. **Open geocoding: Photon-backed, proxied and cached — not Google**
4. **Open base map: Protomaps on Cloudflare R2 — not MapTiler free tier, not Google Maps**
5. **Three scoring factors only: fit, distance, actionability**
6. **PWA from day one — mobile-first, no native app required**
7. **List-first UI, map supports spatial trust**
8. **No web enrichment in MVP**
9. **No CRM integration in MVP**
10. **No AI summaries in MVP**
11. **No stop-order optimization in MVP**
12. **One geography (metro) first**
13. **Hosted auth (Clerk), not custom**
14. **Treat Supabase as plain Postgres — no platform-specific features**
15. **All business logic in FastAPI — Cloudflare Workers is cache/proxy only**
16. **Backend is a Docker container with env vars — platform-agnostic**
17. **Success = agent says "I would stop here"**

---

# 26. Product Thesis

> This app helps field insurance agents decide where to stop by turning a real-world route into a ranked list of nearby small-commercial businesses — using open place data, spatial filtering, and simple, trustworthy scoring.

Deeper thesis:

> The product does not win by having perfect data. It wins by helping the agent make better stop decisions, faster, with confidence.

---

# 27. Known Limitations (document for users)

* **Business data is not real-time.** Overture is refreshed monthly. Some closed, moved, or newly opened businesses may be inaccurate.
* **Not every business in the corridor will appear.** Coverage depends on Overture's upstream sources. Rural and micro-business coverage is thinner.
* **Routing accuracy.** ORS free tier uses OpenStreetMap road network, which is generally accurate but may have gaps in less-mapped areas.
* **Score is a stop-worthiness indicator, not a sales probability.** It reflects data quality and proximity, not likelihood of a sale.
* **iOS PWA install requires Safari.** On iPhone, agents must open the app in Safari and use "Add to Home Screen" — there is no automatic install prompt. Android Chrome shows a native install prompt. Document this for agents before pilot.
* **Offline mode covers saved leads only.** New route searches require a network connection — spatial queries run on the server.

---

# 28. Required Non-Functional Controls (must be implemented before pilot)

## 28.1 Compliance and attribution

* Display required map/data attributions in-app (Protomaps/OSM © OpenStreetMap contributors, Overture CDLA-Permissive-2.0, per provider terms)
* Keep a source attribution field on each business record (`source_payload_json` already supports this)
* Document data licenses in `/docs/licenses.md` and link from app footer

## 28.2 API protection and abuse prevention

* Add per-user and per-IP rate limits on `/routes`, `/geocode`, `/export`
* Cache geocode and route responses to reduce third-party quota usage
* Reject oversized bounding boxes and enforce max CSV export size

## 28.3 Reliability and operations

* Add structured logging with request IDs and route/job IDs
* Add metrics: request latency, geocoder errors, ORS errors, DB query latency, import job duration
* Add nightly DB backup + monthly restore drill
* Add health/readiness checks for API, DB, Redis

## 28.4 Security and privacy

* Encrypt secrets with environment-based secret manager (not `.env` in repo)
* Minimize stored PII (email + notes only as needed)
* Define data retention policy for notes/exports
* Add audit logging for lead status changes and note edits

## 28.5 Delivery hygiene

* Use migration tooling (Alembic) for all schema changes
* Add CI gates: lint, unit tests, integration tests, and one spatial query regression test
* Pin critical dependency versions (PostGIS, FastAPI, map libs) in lockfiles
