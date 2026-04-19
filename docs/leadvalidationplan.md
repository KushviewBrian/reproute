# Lead Validation Plan (Free-First, Reliable-Enough)

## 1) Goal

Build a selective lead expansion + validation system that is:
- Free to run on current stack tiers
- Reliable for field prospecting decisions
- Transparent (confidence + evidence, not black-box truth)

This system improves lead quality across four dimensions:
- **Website validity** — is the URL reachable, stable, and associated with this business?
- **Phone validity** — is the number well-formed, and does it appear on the business's own site?
- **Hours availability** — best-effort structured hours extraction
- **Address consistency** — does the stored address match what the business publishes?

---

## 2) Non-Goals
- Guaranteed real-time truth for all businesses
- Active phone-line verification (requires paid telecom data)
- Heavy web crawling at scale
- Validation of every business in the database (saved/top leads only)

---

## 3) Reliability Principles
1. **Confidence, not certainty** — every field gets a confidence score and evidence payload.
2. **Selective checks only** — validate saved leads and top-scored route leads, not the full corpus.
3. **Freshness-aware** — confidence decays on stale data; stale does not mean wrong, just less trusted.
4. **Do not silently overwrite** — never replace core business data on weak or single-source signals.
5. **Human override always wins** — user-confirmed values are pinned and not overwritten by automated checks.
6. **Fail transparent** — every failure mode produces a labeled state, not a silent gap.

---

## 4) Free-Tier Safety Constraints

### 4.1 Hard Caps (Global)
| Parameter | Value |
|---|---|
| Max validations/day (global) | 50 |
| Max validations/month (global) | 2,000 |
| Max validations/day per user | 15 |
| Max pages fetched per domain per run | 3 |
| Max fetch timeout | 5s |
| Max retries per fetch | 1 (transient errors only) |
| Max evidence payload size | 8 KB |

Per-user daily cap prevents a single active user from exhausting the shared daily budget.

### 4.2 Scope Policy
- **Default scope**: saved leads only
- **Optional scope**: top N route leads by score (`N <= 20`, user-triggered)
- **Manual trigger**: always allowed within per-user daily cap

Revalidation cadence (minimum interval between rechecks):
| Field | Cadence |
|---|---|
| website | 30 days |
| phone | 30 days |
| hours | 14 days |
| address | 30 days |

Freshness gate: if a field was checked within its cadence window, skip unless `force=true`.

### 4.3 Data Retention
- `lead_field_validation`: one row per `(business_id, field_name)` — current state only
- `lead_validation_run`: retain for 30 days; pruned by nightly job. Two records is too few for calibration and incident debugging — run rows are tiny (no evidence payload), so 30 days is safe within free-tier storage.
- `lead_expansion_candidate`: retain indefinitely until approved/rejected; auto-expire `new` candidates after 90 days
- Evidence JSON: stored only on `lead_field_validation` (current state row); truncate to 8 KB max before storage; log truncation event

---

## 5) Expected Service Impact

### 5.1 Supabase
- Light-to-moderate writes for validation state and run logs
- Risk is low with bounded history and trimmed payloads
- Index `lead_field_validation(business_id, field_name)` and `lead_validation_run(business_id, created_at)`

### 5.2 Upstash Redis
- Not used for MVP. Rate counters live in Workers KV (see §5.5). DB-backed queue requires no Redis.
- Add Redis only if queue throughput outgrows the DB polling model.

### 5.3 GitHub Actions
- Not used for scheduling. Cloudflare Workers cron handles scheduling (see §5.5).
- GitHub Actions still used for data ingestion workflows (separate concern).

### 5.4 Render
- Main backend compute; validation logic runs here on request from the CF Worker cron.
- Render free tier does **not** support always-on background workers — do not rely on Render for any polling or background process. All scheduling is driven externally (CF Workers).
- Synchronous user-triggered validation executes inline on the Render web process.

### 5.5 Cloudflare Workers (Primary Scheduler + Rate Counter)
- **Cron trigger**: `0 */6 * * *` (every 6 hours) — Worker calls `POST /admin/validation/run-due` on Render. Cadence can be tightened later without any code changes.
- Free tier: 100k requests/day, cron triggers included — well within needs.
- **Workers KV**: stores daily and monthly validation counter keys with TTL. Faster and cheaper than DB round-trips for cap enforcement on every user-triggered request.
- No public repo requirement (unlike GitHub Actions scheduled workflows).
- Worker does no validation compute itself — it is purely orchestrator/scheduler.

---

## 6) Data Model

### 6.1 `lead_validation_run`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `business_id` | uuid | FK → business |
| `user_id` | uuid (nullable) | null = automated run |
| `requested_checks` | text[] | subset of `[website, phone, hours, address]` |
| `status` | text | `queued\|running\|done\|partial\|failed` |
| `started_at` | timestamptz | |
| `finished_at` | timestamptz (nullable) | |
| `error_message` | text (nullable) | top-level failure message |
| `created_at` | timestamptz | for retention/pruning |

Index: `(business_id, created_at DESC)` for per-business history queries and retention pruning.

### 6.2 `lead_field_validation`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `business_id` | uuid | FK → business |
| `field_name` | text | `website\|phone\|hours\|address` |
| `value_current` | text | raw value from business record |
| `value_normalized` | text (nullable) | cleaned/normalized form |
| `state` | text | `valid\|warning\|invalid\|unknown\|blocked` |
| `confidence` | int | 0–100 |
| `evidence_json` | jsonb | structured evidence (see §8.2) |
| `failure_class` | text (nullable) | `network\|bot_blocked\|dns\|timeout\|parse_error` |
| `last_checked_at` | timestamptz | |
| `next_check_at` | timestamptz | computed from cadence |
| `pinned_by_user` | bool | if true, skip automated overwrite |

Unique constraint: `(business_id, field_name)` — one row per field per business (current state only, not history).

> Note: run-level history lives in `lead_validation_run`. Field-level history is intentionally not kept to stay within free-tier storage limits.

### 6.3 `lead_expansion_candidate`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid | PK |
| `source_business_id` | uuid | FK → business |
| `candidate_payload` | jsonb | extracted fields |
| `dedupe_key` | text | indexed; see §11.2 for derivation |
| `confidence` | int | 0–100 |
| `source_url` | text | page where candidate was found |
| `status` | text | `new\|approved\|rejected\|merged` |
| `created_at` | timestamptz | |
| `expires_at` | timestamptz | `created_at + 90 days` for `new` records |

Index: `(dedupe_key)` unique, `(source_business_id, status)`.

---

## 7) Fetch Failure Taxonomy

Before describing validators, we need a shared failure taxonomy. Fetch failures are **not** equivalent to "site is down" and must be classified before producing a confidence score.

| Class | Trigger | Resulting State | Confidence Effect |
|---|---|---|---|
| `dns` | DNS resolution failure | `invalid` | −40 |
| `timeout` | No response within 5s | `unknown` | −15 |
| `network` | Connection refused / RST | `unknown` | −15 |
| `bot_blocked` | 403/429 with bot signals | `unknown` | −5 |
| `http_error` | 4xx (not 403) or 5xx | `invalid` | −30 |
| `tls_error` | Certificate invalid/expired | `warning` | −20 |
| `parse_error` | Fetched but content unparseable | `warning` | −10 |

`bot_blocked` produces `unknown`, not `invalid` — the site may be fine but is blocking automated fetches. Marking it `invalid` would incorrectly degrade the lead.

User-Agent policy: use a realistic browser User-Agent string. Do not spoof a specific browser version; use a generic descriptor like `RepRouteBot/1.0 (+https://reproute.app/bot)` to allow site operators to identify and whitelist the crawler if desired.

---

## 8) Validation Engines

### 8.1 Website Check

**Process:**
1. Normalize URL: add scheme if missing, strip tracking params, lowercase domain
2. Fetch with `httpx` (async), follow redirects, respect max timeout
3. Classify any fetch failure using §7 taxonomy
4. If successful: record HTTP status, final URL, redirect chain length, latency, TLS validity
5. Parse HTML for JSON-LD `LocalBusiness` schema

**State logic:**
| Condition | State |
|---|---|
| 200–399, stable final URL, no anomalies | `valid` |
| Reachable but redirect to unrelated domain | `warning` |
| Reachable but TLS error | `warning` |
| `bot_blocked` failure class | `unknown` |
| `timeout` or `network` failure | `unknown` |
| `dns` failure, 4xx, or 5xx | `invalid` |

**Confidence formula (website):**

| Signal | Effect |
|---|---|
| Base (fetch succeeded) | +50 |
| JSON-LD LocalBusiness found | +20 |
| Final URL matches expected domain | +10 |
| Redirected to same domain (www ↔ root) | +5 |
| TLS valid | +5 |
| Redirect to unrelated domain | −25 |
| TLS error | −15 |
| `bot_blocked` | −5 |

### 8.2 Phone Check

**Dependency**: phone corroboration requires a successful website fetch. If website check failed with `bot_blocked`, `timeout`, or `network`, skip corroboration but still run format validation. Record the dependency in evidence.

**Process:**
1. Parse with `phonenumbers` (libphonenumber)
2. Normalize to E.164
3. Evaluate `is_possible_number` + `is_valid_number` for US/CA region
4. If website content available: search for phone string in rendered text and JSON-LD

**State logic:**
| Condition | State |
|---|---|
| Valid format + corroborated on site | `valid` |
| Valid format, site unavailable for corroboration | `warning` |
| Valid format, site available, not found on site | `warning` |
| Parseable but `is_valid_number` = false | `warning` |
| Not parseable / impossible number | `invalid` |

**Confidence formula (phone):**
| Signal | Effect |
|---|---|
| Base (parseable) | +40 |
| `is_valid_number` = true | +15 |
| Corroborated in JSON-LD on site | +30 |
| Corroborated in site text | +15 |
| Site available but not found | −10 |
| Website check was `bot_blocked` (corroboration skipped) | 0 (no penalty) |

> Note: this does NOT confirm active line ownership. Confidence reflects format correctness and association with the business's own web presence.

### 8.3 Hours Check

**Process priority (waterfall):**
1. `openingHours` / `openingHoursSpecification` from website JSON-LD
2. Structured text heuristics on homepage/contact page
3. Overpass API `opening_hours` tag if business has OSM link or is matched by name+location

**State logic:**
| Condition | State |
|---|---|
| Structured hours from JSON-LD, parseable | `valid` |
| Hours found in text, partially parseable | `warning` |
| Conflicting hours from two sources | `warning` |
| No hours found anywhere | `unknown` |

**Confidence formula (hours):**
| Signal | Effect |
|---|---|
| Base | +30 |
| JSON-LD structured hours | +40 |
| OSM corroboration | +15 |
| Text-only extraction | +10 |
| Source conflict | −20 |
| Stale > 14 days | −10 |

### 8.4 Address Check

**Process:**
1. Normalize stored address (USPS abbreviation expansion, comma normalization)
2. If website JSON-LD has `address` field: compare normalized strings
3. If coordinates available: compare JSON-LD address geocode proximity (within 200m = match)
4. Flag mismatch type: street-level, city-level, state-level

**State logic:**
| Condition | State |
|---|---|
| JSON-LD address matches stored (fuzzy ≥ 85%) | `valid` |
| Match at city level but street differs | `warning` |
| City or state mismatch | `invalid` |
| No external address source available | `unknown` |

**Confidence formula (address):**
| Signal | Effect |
|---|---|
| Base | +30 |
| JSON-LD address found | +30 |
| Fuzzy match ≥ 85% | +20 |
| Geo proximity match (within 200m) | +15 |
| Street-level mismatch | −20 |
| City/state mismatch | −40 |

---

## 9) Overall Confidence Score

Each field produces an independent confidence score (0–100, floored at 0).

**Overall lead validation score** = weighted average of available field scores:

| Field | Weight |
|---|---|
| website | 35% |
| phone | 30% |
| hours | 15% |
| address | 20% |

If a field has no check result (never run), it is excluded from the average (denominator adjusts).

**Score interpretation:**
| Score | Label |
|---|---|
| 80–100 | Validated |
| 60–79 | Mostly valid |
| 40–59 | Needs review |
| 0–39 | Low confidence |

**Calibration note**: the confidence weights above are initial estimates. They should be reviewed after the first 200+ manual validation outcomes are collected and compared against actual field truth. The plan should include a calibration step in Phase 3.

---

## 10) API Design

### 10.1 Trigger Validation
```
POST /leads/{business_id}/validate
```
Body:
```json
{
  "checks": ["website", "phone", "hours", "address"],
  "force": false
}
```
- `checks`: subset of all four; defaults to all if omitted
- `force`: bypass freshness gate (still subject to per-user daily cap)

Response:
```json
{
  "run_id": "uuid",
  "status": "queued",
  "estimated_checks": ["website", "phone"]
}
```
`estimated_checks` reflects which checks will actually run after freshness gate; if all are fresh and `force=false`, returns `status: "skipped"`.

Auth: requires authenticated user. Applies per-user daily cap check before queuing.

### 10.2 Read Validation State
```
GET /leads/{business_id}/validation
```
Access model: validation data is **scoped to users who have saved that business**. A user can only read validation state for businesses in their own saved leads or a route they own. This avoids leaking competitor prospecting intelligence (e.g. which businesses another user has saved and investigated). The underlying validation data is objective, but access follows the same ownership model as `saved_leads`.

`pinned_by_user` values are user-scoped: each user's pins are independent.

Response:
```json
{
  "overall_score": 74,
  "overall_label": "Mostly valid",
  "fields": {
    "website": {
      "state": "valid",
      "confidence": 85,
      "last_checked_at": "...",
      "next_check_at": "...",
      "evidence": { ... }
    },
    "phone": { ... }
  },
  "latest_run": {
    "id": "uuid",
    "status": "done",
    "started_at": "...",
    "finished_at": "..."
  }
}
```

### 10.3 Batch Run Due Checks
```
POST /admin/validation/run-due
```
- Server-enforced global daily/monthly caps
- Returns count of validations queued
- Called by Cloudflare Workers cron; protected by GitHub OIDC-style short-lived token (see §17 for auth detail)
- Selects candidates: `next_check_at <= now()` ordered by `last_checked_at ASC NULLS FIRST` (prioritize never-checked)

### 10.4 Pin / Unpin Field
```
PATCH /leads/{business_id}/validation/{field_name}
```
Body:
```json
{ "pinned_by_user": true }
```
Pinned fields are skipped by automated runs. User can override validated values without losing their override on recheck.

---

## 11) Queue + Scheduling

### 11.1 Queue Implementation
- **DB-backed queue**: `lead_validation_run` rows with `status=queued`
- Render web process claims rows with `UPDATE ... WHERE status='queued' ORDER BY created_at LIMIT 1 ... RETURNING` (atomic claim, no double-processing)
- No Redis, no always-on background worker on Render — Render only processes jobs when triggered by an inbound HTTP request
- No fallback polling process: all scheduling is driven by CF Workers cron

### 11.2 Execution Model

```
[CF Worker cron, every 6 hours]
    → POST /admin/validation/run-due  (Render)
        → claims up to N queued rows
        → runs validation inline, respecting caps
        → writes results to DB
        → returns { queued: N, completed: M }
```

For user-triggered validation (`POST /leads/{id}/validate`):
- Row inserted as `queued`
- Render immediately processes it **synchronously** within the same request (not deferred)
- If the run would exceed per-user cap, return 429 before inserting

### 11.3 Execution Policy
- Strict per-run and per-day caps enforced server-side before dequeue
- Jittered delay between fetches: 500ms–2000ms random to avoid burst
- Retry policy: retry once after 3s for `timeout` and `network` classes only; never retry `bot_blocked` or `dns`
- Parallel workers: max 2 concurrent validation workers to stay within connection pool limits

---

## 12) Lead Expansion Flow

### 12.1 Scope
Expansion crawls only pages discovered from a successful website check. The max 3 pages/domain cap (§4.1) covers both the initial homepage fetch and expansion pages combined.

Eligible pages (in priority order):
1. `/contact`
2. `/about`
3. `/locations`

If homepage already consumed 1 of 3 page slots, only 2 expansion pages are fetched.

### 12.2 Extraction Targets
- Additional phone numbers
- Additional postal addresses
- Sibling/branch location indicators

### 12.3 Deduplication
`dedupe_key` is derived as:
```
SHA256(source_business_id + "|" + normalized_phone_or_address)
```
Before inserting a candidate, check for existing `dedupe_key`. If found and `status != rejected`, skip insert.

### 12.4 Approval Flow
- Candidates surface in a review queue (UI: §13.3)
- `approved`: merge fields into `business` record
- `rejected`: mark rejected; never re-surface same `dedupe_key`
- `merged`: auto-close after successful field update

---

## 13) UI/UX Plan

### 13.1 Lead Card (Route Tab)
- Small validation badge next to business name:
  - `✓ Validated` (score ≥ 80, green)
  - `~ Review` (score 40–79, yellow)
  - `✗ Low` (score < 40, red)
  - `· Unchecked` (no validation run yet, gray)
- Last checked timestamp on hover/expand
- "Validate" button in expanded card view (triggers §10.1 for all checks)

### 13.2 Saved Leads Card
Per-field status chips below the business name:
- `Website OK` / `Website ⚠` / `Website ✗` / `Website ?`
- `Phone OK` / `Phone ⚠` / `Phone ✗`
- `Hours ✓` / `Hours ~` / `Hours ?`
- Show overall confidence score (e.g. `74%`)
- Last validated timestamp

### 13.3 Evidence Drawer
Accessible via expand/detail action on a validated lead. Shows:
- Per-field: state, confidence, normalized value, source URL, timestamp
- Mismatch notes (e.g. "Address on site: 123 Main St; stored: 124 Main St")
- Failure class if applicable (e.g. "Site blocked automated fetch")
- "Pin this value" action per field

### 13.4 Expansion Candidate Review (Phase 3)
Admin/power-user queue showing:
- Source business
- Candidate type (phone / address / branch)
- Extracted value + source URL + confidence
- Approve / Reject actions

---

## 14) Rollout Phases

### Phase 1 — MVP
- DB migrations for `lead_validation_run`, `lead_field_validation`
- Website validator (fetch + JSON-LD + failure taxonomy)
- Phone validator (format + corroboration, dependency on website result)
- `POST /leads/{id}/validate` (synchronous) and `GET /leads/{id}/validation` (ownership-scoped) endpoints
- Global + per-user daily caps via Workers KV
- Cloudflare Worker cron → `run-due` with HMAC auth
- DB pruning for run history (30-day retention)
- Saved lead cards: per-field chips (website + phone)
- Lead card: validation badge

### Phase 2
- Hours validator (JSON-LD → text heuristics → OSM waterfall)
- Address consistency checker
- Evidence drawer in UI
- Freshness indicators and stale warnings
- `PATCH` pin/unpin endpoint

### Phase 3
- Lead expansion crawl (§12)
- Expansion candidate review queue (UI §13.4)
- Confidence calibration review (compare predicted vs. actual outcomes)
- Per-field history (optional table `lead_field_validation_history` if storage allows)

---

## 15) Quality Controls

### 15.1 Unit Tests
- Each field validator: happy path, each failure class, edge cases (empty URL, international phone, no JSON-LD)
- Confidence formula: verify score bounds (floor 0, ceiling 100)
- Deduplication key derivation

### 15.2 Integration Tests
- Full validate endpoint: trigger → poll status → confirm field state persisted
- Cap enforcement: exceed per-user daily cap, confirm 429
- Freshness gate: re-trigger within cadence window without `force`, confirm `skipped`

### 15.3 E2E Smoke
- Trigger validate for a known business
- Read validation state
- Confirm lead card badge updates
- Confirm evidence drawer renders correctly

---

## 16) Failure Handling

| Failure Scenario | Handling |
|---|---|
| Network failure on fetch | Mark field `unknown` (class: `network`), schedule retry at next cadence |
| Bot blocked (403/429) | Mark field `unknown` (class: `bot_blocked`), do not retry sooner than cadence |
| Partial run completion | Run status `partial`, keep successful field updates, log failed fields |
| Queue outage | Allow direct synchronous validate for manual user action; apply per-user cap; do not bypass global cap |
| Rate limiter / DB outage | Fail open for core user flows (route + lead browsing unaffected); log failed validation attempt |
| Global cap exhausted | Return 429 with `Retry-After` header; log incident |
| Per-user cap exhausted | Return 429 with remaining daily quota in response body |

---

## 17) Security + Compliance

- No secret leakage in evidence payloads (strip auth headers, tokens from stored URLs)
- Sanitize all fetched HTML before storage (strip scripts, limit stored content to metadata/text only)
- Respect `robots.txt` using `urllib.robotparser` or `protego`; cache parsed robots for 24h
- Default crawl-delay: 2s between requests to the same domain; honor `Crawl-delay` directive if present
- Track `user_id` on all manually triggered runs for auditability
- Admin `run-due` endpoint auth: Cloudflare Worker generates a **short-lived HMAC token** (HMAC-SHA256 of `timestamp + secret`, valid for 60s) sent as `X-Admin-Token`. Render verifies the HMAC and rejects tokens older than 60s. The shared secret (`VALIDATION_HMAC_SECRET`) is stored in CF Worker secrets and Render env vars — never in code. This avoids the static-secret-forever problem without requiring a full OIDC setup.
- Expansion candidates undergo same sanitization before storage

---

## 18) KPIs + Targets

| KPI | Target | Timeline |
|---|---|---|
| % saved leads with validation run | ≥ 80% | 30 days post-Phase 1 launch |
| % validated leads with score ≥ 70 | ≥ 60% | 60 days post-launch |
| % leads with website state `valid` | Baseline in first 2 weeks | — |
| % leads with phone `warning` or `invalid` | Baseline in first 2 weeks | — |
| Avg time from save → first validation | < 24 hours | Ongoing |
| Validation success rate (not `failed`) | ≥ 90% | Ongoing |
| Daily cap utilization | < 80% sustained | Alert if exceeded |

---

## 19) Implementation Checklist

### Infrastructure
- [ ] DB migration: `lead_validation_run`, `lead_field_validation`, `lead_expansion_candidate`
- [ ] DB indexes (see §6)
- [ ] DB pruning job for `lead_validation_run` rows older than 30 days
- [ ] Add env vars for all config values (§20)
- [ ] Cloudflare Worker: cron trigger + HMAC token generation
- [ ] Workers KV namespace for rate counters
- [ ] CF Worker secret: `VALIDATION_HMAC_SECRET` + `RENDER_ADMIN_URL`

### Backend — Phase 1
- [ ] Fetch layer with failure taxonomy classification (§7)
- [ ] `robots.txt` parser integration (`protego`)
- [ ] Website validator module
- [ ] Phone validator module (with website dependency handling)
- [ ] Cap enforcement service (global + per-user, Workers KV counters via CF; DB fallback for direct calls)
- [ ] HMAC token verifier for `run-due` endpoint (60s window)
- [ ] Freshness gate logic
- [ ] `POST /leads/{id}/validate` endpoint (synchronous inline execution)
- [ ] `GET /leads/{id}/validation` endpoint (scoped to user's saved leads / owned routes)
- [ ] `POST /admin/validation/run-due` endpoint + HMAC auth
- [ ] Atomic queue claim (`UPDATE ... RETURNING` pattern)

### Backend — Phase 2
- [ ] Hours validator module
- [ ] Address consistency checker
- [ ] `PATCH /leads/{id}/validation/{field}` pin endpoint

### Frontend — Phase 1
- [ ] Lead card validation badge
- [ ] Saved lead per-field chips (website + phone)

### Frontend — Phase 2
- [ ] Evidence drawer component
- [ ] Stale/freshness indicators
- [ ] "Validate now" action in lead detail

### Frontend — Phase 3
- [ ] Expansion candidate review queue UI

### Quality
- [ ] Unit tests: all validators + confidence formulas
- [ ] Integration tests: endpoints + cap enforcement
- [ ] E2E smoke test
- [ ] CI checks for new modules

---

## 20) Configuration Reference

| Env Var | Default | Description |
|---|---|---|
| `VALIDATION_DAILY_CAP` | `50` | Global max validations per day |
| `VALIDATION_MONTHLY_CAP` | `2000` | Global max validations per month |
| `VALIDATION_PER_USER_DAILY_CAP` | `15` | Per-user daily limit |
| `VALIDATION_MAX_PAGES_PER_DOMAIN` | `3` | Homepage + expansion pages combined |
| `VALIDATION_HTTP_TIMEOUT_SECONDS` | `5` | Per-request fetch timeout |
| `VALIDATION_RETRY_DELAY_SECONDS` | `3` | Delay before single retry |
| `VALIDATION_CRAWL_DELAY_SECONDS` | `2` | Min delay between requests to same domain |
| `VALIDATION_RECHECK_DAYS_WEBSITE` | `30` | Freshness cadence: website |
| `VALIDATION_RECHECK_DAYS_PHONE` | `30` | Freshness cadence: phone |
| `VALIDATION_RECHECK_DAYS_HOURS` | `14` | Freshness cadence: hours |
| `VALIDATION_RECHECK_DAYS_ADDRESS` | `30` | Freshness cadence: address |
| `VALIDATION_EVIDENCE_MAX_BYTES` | `8192` | Max evidence payload before truncation |
| `VALIDATION_CANDIDATE_EXPIRE_DAYS` | `90` | Auto-expire `new` expansion candidates |
| `VALIDATION_HMAC_SECRET` | — | Shared HMAC secret for `run-due` endpoint (set in both CF Worker secrets and Render env) |
| `VALIDATION_ADMIN_TOKEN_TTL_SECONDS` | `60` | Max age of HMAC token before rejection |
| `VALIDATION_RUN_RETENTION_DAYS` | `30` | How long to keep `lead_validation_run` rows |
| `RENDER_ADMIN_URL` | — | Full URL of Render backend (set in CF Worker secrets only) |

---

*This plan is intentionally free-first. It prioritizes practical reliability and operational safety over perfect data certainty. Confidence scores reflect evidence, not ground truth.*
