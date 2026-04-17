# RepRoute Master Roadmap

Updated: April 17, 2026

## Purpose

This roadmap is the canonical execution plan for RepRoute. It consolidates and supersedes all other planning documents for delivery order and go/no-go criteria. Supporting specs are listed as source-of-truth references per topic:

| Topic | Source document |
|---|---|
| MVP feature scope and acceptance criteria | `docs/mvpoutline.md` |
| Security controls and pilot gates | `docs/securityplan.md` |
| Lead validation system spec | `docs/leadvalidationplan.md` |
| Dataset expansion and enrichment plan | `docs/datasetexpansion.md` |
| Product architecture and API design | `docs/design&dev.md` |
| QA evidence and verification log | `docs/PHASE1_4_VALIDATION.md` |

**If any supporting document conflicts with this file, this roadmap is the source of truth for delivery order and gate criteria.**

---

## Product Positioning

RepRoute is a route-aware field sales prospecting platform for B2B reps. Insurance is the priority vertical for pilot; the core engine is vertical-flexible.

- Core engine: route corridor lead discovery, scoring, validation, and follow-up workflow
- Vertical layer: classification presets and score weight profiles per vertical

---

## Current Delivery Snapshot

### What is built and usable

- Route creation and lead retrieval pipeline (end-to-end)
- Classification and scoring (rule-based, insurance-tuned)
- Discovery UI: route, list/map, detail, saved views
- Save lead, status changes, notes, per-route CSV export
- Today dashboard (initial), follow-up date fields (initial), and cross-route saved-leads CSV export
- PWA shell: manifest + service worker + icons
- Offline queue for notes and status changes (localStorage-backed)
- Ingestion scripts (`scripts/ingest_overture.py`) and scoring validation scripts
- Phase 5 schema foundations: validation/expansion tables and migrations

### Confirmed by recent checks

- Backend compile check passes (`python3 -m compileall backend/app scripts`)
- Frontend build passes (`npm run build`)
- Frontend typecheck passes (`npm run typecheck`)
- Manual prototype flow verified: fetch, save, note, saved view rendering

### Confirmed open gaps (must close before pilot)

- Security P0 code is implemented but not yet fully verified/closed (see Phase 2)
- Lead validation system not implemented (see Phase 5)
- Dataset enrichment not implemented (see Phase 6)
- Deduplication baseline is not implemented (see Phase 4)
- Onboarding overlay is not implemented (see Phase 4)
- Score explanation tooltip and evidence calibration are incomplete (see Phase 3)
- Evidence capture for ingestion QA and scoring validation is incomplete (see Phase 1)

---

## Execution Rules

- Work phases are sequential by default. Parallel execution is allowed only where this document explicitly marks work as parallel-safe (see "Parallel Workstream Guide" and phase-level notes).
- Each phase defines: Scope, Deliverables, Exit criteria, Blocking dependencies.
- A phase is complete only when its exit criteria are met and evidence is recorded in the project evidence log (`docs/PHASE1_4_VALIDATION.md` for now).
- Do not mark a phase complete without explicit exit-criteria proof.

---

## Phase Plan

---

### Phase 0 — Baseline Freeze and Build Reliability

**Status: In progress**

**Scope:**
Lock current architecture, environments, and dev workflow. Ensure any developer can set up and run the system from scratch without tribal knowledge.

**Deliverables:**
- Repository structure and owner docs current (`README`, `DEPLOYMENT_GUIDE`, `REQUIRED_SECRETS`)
- Clean-machine setup validation: backend, frontend, and database smoke flow
- CI path covering: backend lint/compile, frontend build, basic smoke checks
- Rollback instructions documented for Render and Cloudflare Pages deploys

**Test focus:**
- New/changed: clean-machine bootstrap from docs only (backend start, frontend start, DB connectivity, migrations)
- Existing regression checks: route creation, lead fetch, save lead, note create/list, per-route export, auth-protected access
- CI verification: test discovery/import path works on GitHub Actions and local

**Exit criteria:**
- Fresh machine can run backend, frontend, and end-to-end smoke flow using only committed docs
- CI consistently runs lint/build/check on every push to `main`
- Rollback steps documented and walked through once manually

**Blocking dependencies:** None

---

### Phase 1 — Data and Routing Foundation Evidence

**Status: Mostly implemented; stale-record handling complete; real evidence capture incomplete**

**Scope:**
The route geometry, corridor query, and Overture ingestion pipeline are implemented. This phase captures the QA evidence needed to proceed with confidence, and adds the stale-record handling gap identified in `datasetexpansion.md`.

**Deliverables:**
- At least one metro Overture ingestion run with archived QA stats (row count, skipped, classified, score distribution) committed to the evidence log (`docs/PHASE1_4_VALIDATION.md` for now)
- `EXPLAIN ANALYZE` output for at least one production-like route + corridor query on real data, committed to the evidence log (`docs/PHASE1_4_VALIDATION.md` for now)
- Stale record detection added to `scripts/ingest_overture.py`: after each full refresh, `UPDATE business SET operating_status = 'possibly_closed' WHERE external_source = 'overture' AND last_seen_at < <refresh_start_time>`
- Ingestion QA artifact template documented so each monthly refresh produces a consistent report

**Test focus:**
- New/changed: stale-record update logic in ingestion script (correct rows marked, no false positives on fresh rows)
- New/changed: ingestion QA report generation and metric completeness
- Existing regression checks: route corridor query output count/ordering, route creation latency, lead endpoint stability on refreshed data

**Exit criteria:**
- At least one ingestion run QA artifact committed
- At least one `EXPLAIN ANALYZE` trace committed; route creation + lead retrieval p95 <= 5s on real metro data (measured with the same test route configuration used for the trace)
- Stale-record update runs correctly on a test dataset (before and after row counts match expectations)

**Blocking dependencies:** Phase 0 complete

---

### Phase 2 — Security Lockdown (MVP Critical)

**Status: In progress — P0 code landed, verification + sign-off incomplete**

This is the highest-risk open work. All P0 items must close before pilot traffic. Security work that is backend-only can be parallelized against Phase 3 frontend work.

**Scope:**
Close all P0 security risks. Establish baseline hardening across auth, data access, API protection, secrets, and CI.

**Deliverables — P0 (must close before any pilot traffic):**

- **P0-1 DB TLS:** In `backend/app/db/session.py`, replace `ssl.CERT_NONE` with `ssl.CERT_REQUIRED` + `check_hostname=True`. Add production startup check that fails if `CERT_NONE` is active. Verify pgbouncer cert is valid before removing.
- **P0-2 JWT verification:** In `backend/app/core/auth.py`, remove the conditional `if settings.clerk_jwks_url:` guard — verification must always run in non-dev environments. Add production startup check that fails if `CLERK_JWKS_URL` or `CLERK_JWT_ISSUER` are empty.
- **P0-3 Admin import hardening:**
  - Admin email allowlist: `if user.email not in settings.admin_allowed_emails: raise 403`
  - `parquet_path` validation: `Path(parquet_path).resolve()` + assert within allowlisted root directory
  - Add per-job concurrency guard (max 1 running job at a time)
- **P0-4 POC mode guard:** Startup check: if `environment == "production"` and `poc_mode == True`, log critical and refuse to start.

**Deliverables — P1 (before pilot, can follow P0):**

- JWKS cache TTL: replace unbounded module-level dict with 1-hour TTL; refresh on expiry
- User cache TTL: replace unbounded `_user_cache` with LRU (max 500 entries, 5-minute TTL per entry)
- Rate limiting extended to: `saved-leads` writes (60/hr/user), `notes` create (120/hr/user), `export` (20/hr/user), `admin import` (5/day global)
- Request body size limit middleware added to `main.py`
- Security headers added to FastAPI backend (`main.py`) with production-only HSTS enforcement: `Strict-Transport-Security` (prod only), `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- `frontend/public/_headers` created for Cloudflare Pages: CSP (report-only first in rollout), `Permissions-Policy`, `X-Content-Type-Options`, `Referrer-Policy`
- Secret scanning added to GitHub Actions CI (`trufflesecurity/trufflehog-actions-scan` or `gitleaks`)
- Dependency vulnerability scan added to CI: `pip-audit` (Python) + `npm audit --audit-level=high` (Node)
- Branch protection on `main`: required review for `auth.py`, `session.py`, `config.py`, `admin_import.py`, migrations, CI workflows; no force-push to `main`
- Negative auth tests: cross-user access on routes, saved-leads, notes, export; invalid JWT, wrong issuer, expired token
- Log forwarding from Render to external service (Logtail, Papertrail, or Supabase log table)
- Uptime monitoring for `/health` with alerting (UptimeRobot free tier or equivalent)

**HMAC auth for validation admin endpoint (implement here, used in Phase 5):**
- `POST /admin/validation/run-due` will be protected by short-lived HMAC-SHA256 tokens (not static `X-Admin-Secret`)
- Token = HMAC-SHA256(timestamp + secret), 60-second validity window
- Add `VALIDATION_HMAC_SECRET` to `Settings` and secret stores now so Phase 5 can wire it without a Phase 2 re-open

**Test focus:**
- New/changed security tests: DB TLS required in production, JWT verification hard-fail when JWKS/issuer misconfigured, `poc_mode=true` startup block in production
- New/changed authz tests: admin allowlist + path allowlist, HMAC signature validity/expiry checks, extended rate-limit enforcement and body-size limits
- Existing regression checks: authenticated route/leads/saved/notes/export flows still function for valid users and tokens after security hardening

**Exit criteria:**
- All P0 items closed and verified (code review + manual test evidence)
- Security regression tests pass (negative auth + cross-user access tests)
- CI secret scan and dependency audit running green
- Production config review checklist completed and signed off
- P0 items in `securityplan.md` marked closed with commit reference

**Blocking dependencies:** Phase 0 complete (P0 items can begin immediately; P1 items can follow)

---

### Phase 3 — Classification, Scoring, and Score Explanation

**Status: In progress — explanation text largely implemented; tooltip + calibration evidence missing**

**Scope:**
Validate scoring quality on real data and complete the score explanation display in the UI. Vertical profiles are documented but the config path is deferred — do not build a multi-profile config system for MVP.

**Deliverables:**
- Five-route scoring validation run on real metro data; outcomes documented in the evidence log (`docs/PHASE1_4_VALIDATION.md` for now)
- `insurance_class = 'Other'` / `'Unknown'` rate measured and <= 35% for launch metro (sample size >= 500 classified businesses)
- Score explanation UI: lead card and lead detail must display three things in plain language in under 5 seconds (per `mvpoutline.md` §5.2):
  1. Why the business ranked high/low (fit + distance signal)
  2. What contact data is available (phone/website present or missing)
  3. Confidence in the data (validation state when available, "Unchecked" when not)
- Sub-scores (fit, distance, actionability) surfaced as plain-language labels, not raw numbers alone
- Score explanation tooltip: one-time tooltip on first score badge interaction

**Test focus:**
- New/changed: score explanation rendering on lead list/detail (plain-language text, tooltip behavior, unreadable/empty-state handling)
- New/changed: scoring validation harness outputs and interpretation logs for 5 routes
- Existing regression checks: filter-by-score behavior, lead ranking consistency, map/list selection behavior, saved-lead status updates unaffected by score UI changes

**Exit criteria:**
- Scoring validation run committed to the evidence log for 5 routes
- `Other/Unknown` classification rate documented and <= 35% on launch metro sample (n >= 500)
- Score explanation passes a reading test: a non-technical person can state why a lead ranked high after 5 seconds of reading

**Blocking dependencies:** Phase 1 evidence complete

---

### Phase 4 — Core Discovery UX, Workflow Completion, and Missing MVP Features

**Status: In progress — backend foundations and core UX landed; remaining feature/test gaps open**

**Scope:**
Complete all remaining MVP-required UI and workflow features. This is the largest remaining build phase before validation is layered on. Work within this phase can be parallelized across frontend and backend tracks.

**Deliverables:**

**Backend:**
- Schema migration: add `next_follow_up_at` (timestamptz, nullable) and `last_contact_attempt_at` (timestamptz, nullable) to `saved_lead`
- Deduplication baseline (query-time only for MVP): suppress obvious duplicates from the same lead list using same-name (fuzzy >= 85%) + within 100m + matching phone or website when available
- Defer canonical merge model fields/tables (`canonical_business_id`, `dedupe_group_id`, multi-source merge state) until after Phase 6, consistent with `datasetexpansion.md`
- `PATCH /saved-leads/{id}`: add `next_follow_up_at` and `last_contact_attempt_at` fields
- `GET /saved-leads?due_before=...`: filter by follow-up due date
- `GET /saved-leads/today`: returns today view payload (overdue + due today + top untouched high-score leads + recent route)
- `GET /export/saved-leads.csv`: cross-route export of all saved leads, CRM-ready column format (see `mvpoutline.md` §5.6 for column spec: `first_name`, `last_name`, `company`, `phone`, `email`, `address`, `city`, `state`, `zip`, `source`, `status`, `notes`)

**Frontend:**
- Today view / daily dashboard (default landing tab after login; spec per `mvpoutline.md` §5.5):
  - Overdue follow-ups
  - Due today
  - High-priority untouched (score ≥ 70, status = saved, no contact, capped at 5)
  - Recent route with unsaved lead count
  - Empty state: prompt to create route, not blank screen
- Follow-up date picker on saved lead card and detail; overdue state indicator
- Saved list sorted by follow-up urgency (overdue first, soonest due, then unsorted)
- Offline status change queue: status mutations must be queued in localStorage alongside notes. Notes are already queued (`reproute_offline_note_queue_v1`); status changes are the gap. Add status changes to the queue.
- Sync state indicator: visible when unsynced items exist; clears on successful sync
- Cross-route CSV export from Saved tab
- CRM-ready export format (second export format, mapped for AMS import)
- First-run onboarding overlay: three-step flow (Plan → Review → Track); dismissible; does not reappear; empty states for route tab, saved tab, Today tab
- iOS install banner: custom "Add to Home Screen" instructions (iOS Safari does not auto-prompt)
- Route entry UX: error clarity for geocode failures, reverse geocode on current location
- Error handling: clear states for 401, 429, and network failures on all mutation actions

**Test focus:**
- New/changed backend tests: follow-up date fields round-trip, `GET /saved-leads/today` section logic, cross-route export format and schema
- New/changed frontend tests: Today tab sections, follow-up urgency sorting, onboarding and iOS install banner, offline status queue + sync indicator
- Existing regression checks: current save lead flow, note save/list/edit, existing notes offline queue, route form behavior, per-route export still works

**Exit criteria:**
- No lead or note data loss in offline → reconnect scenario (verified: airplane mode → changes → reconnect → second device check)
- Follow-up date fields round-trip correctly (set, display overdue, sort by urgency)
- Today view renders correct data for all four content sections
- Deduplication suppresses obvious same-business duplicates in route output (manual spot-check on 3 routes, with zero duplicate pairs in the top 20 for each route)
- Export opens without column mapping errors in target AMS
- Full end-to-end flow completable in one session without instructions: route → review → save → note → schedule follow-up → export

**Blocking dependencies:** Phase 2 P0 items complete; Phase 3 scoring explanation done (so validation badge placeholder can be placed correctly)

---

### Phase 5 — Lead Validation System

**Status: Started — schema layer implemented, runtime validation system not started**

**Scope:**
Implement the selective confidence-based validation system per `docs/leadvalidationplan.md`. This is a core trust signal for MVP — the system must be live before pilot.

**Caps (hard limits — do not exceed):**
- Global daily: **50 validations/day**
- Global monthly: **2,000 validations/month**
- Per-user daily: **15 validations/day**
- Max pages fetched per domain per run: 3
- Max fetch timeout: 5s; max retries: 1 (transient errors only)
- Evidence payload: truncate to 8 KB before storage

**Deliverables:**

**Database migrations:**
- `lead_validation_run`: id, business_id, user_id (nullable), requested_checks (text[]), status, started_at, finished_at, error_message, created_at. Index: `(business_id, created_at DESC)`.
- `lead_field_validation`: id, business_id, field_name, value_current, value_normalized, state, confidence, evidence_json, failure_class, last_checked_at, next_check_at, pinned_by_user. Unique: `(business_id, field_name)`. One row per field per business — current state only.
- `lead_expansion_candidate`: id, source_business_id, candidate_payload, dedupe_key (unique, indexed), confidence, source_url, status, created_at, expires_at.
- Do **not** add flat columns (`website_ok`, `phone_ok`, `status_confidence`) to `business` — incompatible with the evidence/confidence model.

**Validation engines** (full spec in `leadvalidationplan.md` §8):
- Website check: normalize URL → fetch with `httpx` → classify failure using §7 taxonomy → parse JSON-LD → score confidence
- Phone check: parse with `phonenumbers` → E.164 normalize → corroborate on website content (if available)
- Hours check: waterfall — JSON-LD → text heuristics → Overpass `opening_hours` tag
- Address check: normalize → compare with JSON-LD `address` → geo proximity check (within 200m = match)

**Fetch failure taxonomy** (must be implemented before any validators):
`dns` → `invalid`; `timeout`/`network` → `unknown`; `bot_blocked` → `unknown` (never `invalid`); `http_error` → `invalid`; `tls_error`/`parse_error` → `warning`.

**Overall confidence score** = weighted average of available field scores (website 35%, phone 30%, address 20%, hours 15%); exclude fields with no result.
Labels: 80–100 = Validated; 60–79 = Mostly valid; 40–59 = Needs review; 0–39 = Low confidence.

**API endpoints** (spec in `leadvalidationplan.md` §10):
- `POST /leads/{business_id}/validate` — trigger validation; apply per-user daily cap before queuing; return `run_id`
- `GET /leads/{business_id}/validation` — read state; access scoped to users who have saved that business or own a route containing it
- `POST /admin/validation/run-due` — batch trigger; protected by HMAC-SHA256 short-lived token (implemented in Phase 2); claims queued rows, runs inline, enforces global caps
- `PATCH /leads/{business_id}/validation/{field_name}` — pin/unpin field; pinned fields skipped by automated runs

**Scheduler:**
- Cloudflare Worker cron: `0 */6 * * *` → `POST /admin/validation/run-due` on Render
- Workers KV: daily and monthly counter keys with TTL for cap enforcement
- Worker is orchestrator only — no validation compute; Render runs all jobs
- User-triggered validation executes synchronously within the same request (not deferred to background)

**Queue implementation:**
- DB-backed: `lead_validation_run` rows with `status=queued`
- Atomic claim: `UPDATE ... WHERE status='queued' ORDER BY created_at LIMIT 1 ... RETURNING`
- Jittered inter-fetch delay: 500ms–2000ms random
- Max 2 concurrent validation workers
- Retry once after 3s for `timeout` and `network` only; never retry `bot_blocked` or `dns`

**Data retention:**
- `lead_validation_run`: retain 30 days; pruned by nightly job
- `lead_field_validation`: one row per (business_id, field_name) — current state, no history
- `lead_expansion_candidate`: retain indefinitely until approved/rejected; auto-expire `new` at 90 days

**UI:**
- Validation badge on lead card: `Validated` / `Mostly valid` / `Needs review` / `Low confidence` / `Unchecked`
- Evidence drawer in lead detail: per-field state, confidence, last checked, next check, pin control
- `bot_blocked` → `unknown` state shown in UI (never shown as `invalid`)

**Lead expansion:**
- Crawl eligible pages from successful website fetch: `/contact`, `/about`, `/locations` (max 3 total including homepage)
- Extract: additional phones, addresses, branch/sibling location indicators
- Dedupe key: `SHA256(source_business_id + "|" + normalized_phone_or_address)`
- Candidates require manual approval; auto-expire `new` status at 90 days

**Test focus:**
- New/changed validator unit tests: website/phone/hours/address state and confidence outcomes, failure taxonomy (`bot_blocked` => `unknown`)
- New/changed integration tests: validation queue claim/processing, global/per-user cap enforcement, HMAC-protected `run-due`, retention pruning
- Existing regression checks: lead retrieval/saving latency and behavior unaffected when validation tables and cron jobs are active

**Exit criteria:**
- Validation runs succeed on 10+ saved leads within global cap limits; results correct for known test cases
- `bot_blocked` never produces `invalid` state — verified with a test case
- Evidence drawer renders all fields, shows `Unchecked` when no run has occurred
- Batch cron endpoint called by CF Worker; counter enforces global daily cap
- HMAC token auth on `run-due` endpoint rejects invalid/expired tokens
- Nightly retention pruning job runs without errors
- 30-day calibration plan documented in the evidence log (first 200 manual outcomes required before weight tuning)

**Blocking dependencies:** Phase 2 (P0 security + HMAC secret), Phase 3 (score explanation complete so validation badge fits UI correctly)

---

### Phase 6 — Dataset Expansion

**Status: Not started**

**Scope:**
Improve contact field completeness without cost blowout, using selective OSM enrichment on top of the existing Overture monthly refresh. Per `docs/datasetexpansion.md`.

**Enrichment caps (do not exceed):**
- Global daily: 100 enrichments/day
- Global monthly: 2,000 enrichments/month
- Per-user daily: 15 enrichments/day

**Deliverables:**

**Database migrations:**
```sql
ALTER TABLE business
  ADD COLUMN osm_enriched_at          TIMESTAMPTZ,
  ADD COLUMN osm_phone                TEXT,
  ADD COLUMN osm_website              TEXT,
  ADD COLUMN city_license_verified_at TIMESTAMPTZ;
```

**Overture refresh hardening:**
- After each monthly refresh, mark stale records: `UPDATE business SET operating_status = 'possibly_closed' WHERE external_source = 'overture' AND last_seen_at < <refresh_start_time>`
- Do not hard-delete; mark for downstream validation review

**Selective OSM enrichment:**
- Overpass fetch utility: point lookup by lat/lng/name, 50m radius, extract `phone`/`contact:phone`, `website`/`contact:website`, `opening_hours`
- Do not run against Overpass public endpoint above ~500 queries/day; use local Docker instance if volume approaches that
- Enrichment trigger: new lead save + route generation (async, non-blocking)
- Column-level merge only: write to `osm_phone`/`osm_website`; copy to primary `phone`/`website` only when primary is null
- Skip re-enrichment if `osm_enriched_at > now() - 30 days` (unless `force=true`)
- Quota counter: Upstash Redis keys `enrich:day:{date}` and `enrich:user:{uid}:{date}`

**Licensing compliance** (required before any data is ingested from a new source):
- Overture Places: CDLA-Permissive-2.0. Individual records may include ODbL-licensed OSM content — check per-record `sources` field. Do not hardcode a single attribution string. See `datasetexpansion.md` §11.1 for full detail.
- OSM/Overpass: ODbL 1.0. Share-alike applies to derived databases. Attribution: "© OpenStreetMap contributors" must be visible wherever OSM-derived data is displayed.
- Any new source: confirm license before ingesting; record in `datasetexpansion.md` §11.4 table.

**Launch-metro local authority data (optional, after OSM pass):**
- Only if OSM enrichment leaves significant gaps after Phase 6 OSM pass
- Restricted to launch metro bbox; confirm license before touching
- Document in `datasetexpansion.md` §11.4

**Test focus:**
- New/changed enrichment tests: OSM fetch parsing, quota counters, 30-day freshness skip, stale-record marking on refresh
- New/changed merge tests: only fill primary phone/website when null; never overwrite stronger existing values
- Existing regression checks: route creation + lead retrieval latency, score ordering, save/note/export behavior unchanged after enrichment writes

**Exit criteria:**
- Contact field completeness (`has_phone OR has_website`) improves by ≥ 10% for saved leads after one enrichment pass (measured before and after)
- Stale record marking runs correctly on a post-refresh test (before/after counts verified)
- Enrichment stops at daily cap; Redis counter increments correctly
- No user-visible latency regression on route load or lead save
- License and attribution requirements documented and implemented

**Blocking dependencies:** Phase 2 complete (recommended); can start Phase 6 schema work in parallel with Phase 5 if needed since they touch different tables

---

### Phase 7 — Operations Hardening

**Status: Partial**

**Scope:**
Stabilize operations before pilot traffic. Health monitoring, alerting, error handling, and backup verification.

**Deliverables:**
- Structured audit logging for all required events (per `securityplan.md` §4.8): auth failures, 403s, 429s, admin access, note/status mutations, exports, validation runs
- Log forwarding from Render to external service (if not already done in Phase 2)
- Uptime monitoring for `/health` with alerting (if not already done in Phase 2)
- Alert rules: 401/403 spike (>20 in 5 min from single IP), admin endpoint failures (>3 in 10 min), export volume (>10 exports/hr from one user), 5xx rate >1% over 5 min
- p95 latency tracking for key endpoints; alert if route creation + lead retrieval exceeds 5s p95
- Queue/retry behavior verified for ORS and Photon upstream failures (exponential backoff, graceful degraded mode)
- Backup and restore drill: confirm Supabase backup policy for active plan; run one restore drill; document result
- Least-privileged DB roles: app role (`SELECT/INSERT/UPDATE/DELETE` on app tables only); migration role separate; verify `service_role` key not exposed anywhere
- Supabase Data API (PostgREST) verified disabled or restricted for all app tables

**Test focus:**
- New/changed ops tests: alert trigger simulations (401/403 spike, 5xx spike, admin failures), `/health` uptime alarms, log forwarding integrity
- New/changed security posture checks: DB role permissions, backup restore drill validation, PostgREST restrictions
- Existing regression checks: no functional change to user-facing route/lead/save/note/export flows while observability controls are enabled

**Exit criteria:**
- Critical endpoint p95 latency tracked in monitoring
- Alerting catches outage and auth failure scenarios within 5 minutes
- Backup restore drill completed once and result committed to `docs/`
- Audit log events fire correctly for all listed event types (verified by triggering each manually)
- DB app role in use; no superuser credentials in app connection string

**Blocking dependencies:** Phase 2 complete

---

### Phase 8 — MVP Feature Verification and QA

**Status: Not started (depends on Phases 3–7 all being in progress)**

**Scope:**
Verify all MVP acceptance criteria from `mvpoutline.md` §14 are met before declaring pilot readiness.

**Deliverables:**
- Mobile QA matrix pass (per `mvpoutline.md` §9 testing matrix):
  - iOS Safari (iPhone SE, iPhone 15)
  - Android Chrome (mid-range device)
  - Desktop Chrome (1280px wide)
- Performance evidence committed to the evidence log (`docs/PHASE1_4_VALIDATION.md` for now):
  - p95 route creation + lead retrieval ≤ 5s on a real route in target metro, measured from a mobile device on 4G
- Lead quality evaluation: 80% of top-10 leads on 5 test routes in target metro are valid commercial prospects per `mvpoutline.md` §18 rubric (evaluated manually)
- Offline reliability verified: airplane mode → changes → reconnect → second device confirms sync
- No silent failures verified: force-fail API → confirm all error states surface correctly
- PWA install flow verified on iOS and Android (install prompt after first route, iOS banner)
- Operational runbook committed: ingestion trigger, quota exhaustion (ORS, Photon, Clerk), backend outage, validation cap reached

**Test focus:**
- New/changed comprehensive QA: Today view, follow-up dates, validation badges/evidence drawer, cross-route export, onboarding, install flow
- Existing regression suite: route creation, lead filters, map/list interactions, save/status/note, per-route export, auth session behavior
- Failure-path testing: offline mode, reconnect sync, upstream routing/geocoding failures, explicit 401/429/network response handling

**Exit criteria — all of the following must be true:**
1. Full end-to-end flow completable without instructions: route → leads → save → note → follow-up → export
2. ≥ 80% valid commercial prospects on 5 test routes (manual evaluation, per §18 rubric)
3. Offline status + note queue syncs correctly after reconnect
4. No layout breakage on iOS Safari (iPhone SE) and Android Chrome
5. No silent failures on any save, note, status, or export action
6. Operational runbook exists and `/health` monitoring is active with alerting
7. p95 route creation ≤ 5s on 4G mobile, measured and committed

**Blocking dependencies:** Phases 3–7 substantially complete

---

### Phase 9 — Pilot Validation and Launch Readiness

**Status: Not started**

**Scope:**
Run structured pilot sessions with real reps. Measure against KPI targets. Iterate on critical blockers before general launch.

**KPI targets** (per `mvpoutline.md` §16; baselines established in first 2 weeks):

| KPI | Target |
|---|---|
| Route-to-save conversion | ≥ 30% of leads viewed result in a save |
| Save-to-contacted conversion | ≥ 50% of saved leads reach `called` or `visited` within 7 days |
| Follow-up completion rate | ≥ 60% of follow-ups resolved within 3 days of due date |
| Weekly active agents (WAU) | ≥ 3 during pilot, growing after |
| Median time: route → first save | < 5 minutes |
| Lead quality score | ≥ 80% valid commercial prospects (manual eval) |

**Deliverables:**
- Structured pilot sessions (target: 3+ independent insurance agents)
- Usability feedback log: friction points, trust signals, workflow gaps
- Device and connectivity QA across pilot participants
- Final QA matrix across all supported devices
- Launch runbook:
  - Incident response path (Brian is primary incident owner)
  - Render and Cloudflare Pages rollback steps
  - Clerk, Supabase, ORS, Photon support contacts documented
  - First-contact SLA for pilot participants
- Clerk MAU monitoring: upgrade plan at 80% of free-tier limit (50k MAU); verify current pricing at clerk.com/pricing before budgeting
- Validation confidence weight calibration plan: after 200+ manual outcomes, compare against automated scores; tune weights in `leadvalidationplan.md` §9

**Test focus:**
- New/changed pilot instrumentation: KPI events accuracy (save/contact/follow-up timestamps), dashboard/report calculations, calibration dataset quality
- Existing regression checks under real usage: no data loss, no auth leakage, stable sync across devices, stable export content over repeated sessions
- Real-world scenario testing: spotty network behavior, long sessions, repeated route generation, high-note-volume accounts

**Exit criteria:**
- KPI baseline established; pilot targets met or explicit iteration plan approved by Brian
- Security and operational gates remain green for 2+ consecutive weeks
- No P0 or P1 security issues open
- Confidence calibration plan in place for Phase 10

**Blocking dependencies:** Phases 5–8 complete

---

## Parallel Workstream Guide

The phases above are ordered for a single developer. If capacity allows parallelism:

| Workstream | Phases | Can start when |
|---|---|---|
| A — Platform and Security | Phase 2 | Phase 0 done |
| B — Scoring and UX | Phases 3–4 | Phase 1 evidence done |
| C — Validation System | Phase 5 | Phase 2 P0 done + Phase 3 done |
| D — Data Quality | Phase 6 | Phase 2 done (schema can start alongside Phase 5) |
| E — Ops Hardening | Phase 7 | Phase 2 done (some items can run with Phase 2 P1) |

Phase 2 (Security) is the only phase with true blocking effect on everything downstream. Prioritize closing P0 items first.

---

## MVP Definition (Consolidated)

MVP is complete when all are true:

- Core discovery, save, and follow-up workflow is stable on mobile
- Lead validation signals (website + phone) are live and understandable in UI
- Follow-up workflow exists: due dates, overdue visibility, urgency sorting
- Export supports per-route CSV and cross-route CRM-format CSV
- Security P0 and P1 controls are closed and verified
- Evidence is committed for Phases 1–4 in the evidence log (`docs/PHASE1_4_VALIDATION.md` for now; rename to `docs/EVIDENCE_LOG.md` when expanded beyond Phase 4)
- Pilot sessions confirm repeat weekly usage intent from ≥ 3 agents

---

## Phase Status Table

| Phase | Name | Status | Confidence |
|---|---|---|---|
| 0 | Baseline reliability | In progress | Medium |
| 1 | Data/routing foundation evidence | Mostly done | Medium |
| 2 | Security lockdown | In progress (P0 code landed) | Medium |
| 3 | Scoring + score explanation | In progress | Medium |
| 4 | Discovery UX + workflow completion | In progress | Medium |
| 5 | Lead validation system | Started (schema only) | Medium |
| 6 | Dataset expansion | Not started | Low |
| 7 | Operations hardening | Partial | Low |
| 8 | MVP verification and QA | Not started | Low |
| 9 | Pilot and launch | Not started | Low |

---

## Immediate Next Sprint (Recommended)

1. **Verify and close Phase 2 P0 formally** — run security regression tests, production startup config validation, and update `securityplan.md` with commit-linked closure evidence.
2. **Replace Phase 1 placeholder evidence with real artifacts** — run one ingestion QA pass and one real `EXPLAIN ANALYZE` trace on seeded metro data; commit results to `docs/evidence/` + `docs/PHASE1_4_VALIDATION.md`.
3. **Finish Phase 3 remaining items** — add one-time score explanation tooltip and commit 5-route scoring validation evidence (including `Other/Unknown` rate).
4. **Finish Phase 4 remaining items** — implement dedup suppression baseline, onboarding overlay, and complete end-to-end offline/reconnect verification for status+notes.
5. **Start Phase 5 runtime work** — keep schema as-is, then implement validation APIs/queue/worker orchestration only after Phase 2 P0 is signed off.

---

## Change Control

When updating this roadmap:
- Update phase status and confidence only after evidence exists.
- Reference supporting docs in commit messages when phase specs change.
- Do not mark a phase complete without explicit exit-criteria proof committed to the evidence log (`docs/PHASE1_4_VALIDATION.md` for now, Phases 1–4) or verifiable in the codebase/config (Phases 5–9).
