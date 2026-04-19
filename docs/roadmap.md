# RepRoute Master Roadmap

Updated: April 19, 2026 (Phase 10 code complete — all 16 files patched, 105 backend tests passing)

##
Developer notes:
Find a way to streamline / optimize /minimize server usage
plan mobile app / integration
integrate with google/apple maps?

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
| Reliability gate execution checklist | `docs/RELIABILITY_EXECUTION_CHECKLIST.md` |
| Gate closeout reporting template | `docs/GATE_CLOSEOUT_TEMPLATE.md` |
| Lead sorting, grouping, and owner-contact spec | `docs/phase10_lead_intelligence.md` |

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
- Hybrid scoring v2 shadow scaffolding: deterministic calibrated components, additive feedback priors, dual-compute storage, and score-version gating (`v1` default)
- Scoring v2 quality pass implemented: geo-aware feedback priors, validation-failure penalties, weak-name penalties, and sample-size-adaptive feedback weighting
- Discovery UI: route, list/map, detail, saved views
- Save lead, status changes, notes, per-route CSV export
- Today dashboard (initial), follow-up date fields (initial), and cross-route saved-leads CSV export
- PWA shell: manifest + service worker + icons
- Offline queue for notes and status changes (localStorage-backed)
- Deduplication baseline in lead retrieval path (query-time suppression)
- First-run onboarding overlay (Plan -> Review -> Track), dismissible/non-repeating
- One-time score explanation tooltip behavior on first score interaction
- Ingestion scripts (`scripts/ingest_overture.py`) and scoring validation scripts
- Phase 5 complete: validation/expansion schema, all API endpoints, validation engine, CF Worker cron, and full UI (badges, evidence drawer, per-field chips, pin/unpin, "Validate now" trigger with polling)
- Phase 6 OSM enrichment implemented: migration 0005 (osm_phone, osm_website, osm_enriched_at), Overpass fetch service, enrichment quota counters (Redis, separate from validation), 30-day freshness gate, column-level merge, background enrichment on lead save and route load (per-business sessions, Redis dedup lock), POST /leads/{id}/enrich endpoint
- Map reinitialization regression fixed: MapPanel now uses a ref for onSelectLead instead of depending on it in the init effect, preventing the map from being torn down on every App render
- Security hardening (partial): request body limit, backend security headers, extended rate limits, Cloudflare Pages `_headers`
- Security middleware test scaffolding added (`backend/tests/test_security_middleware.py`)
- FastAPI startup lifecycle migrated to lifespan handler with backward-compatible `startup()` shim for test/import compatibility
- Structured audit logging added for mutation/admin/auth-denial events (middleware-based)
- Reliability gate documentation baseline added (deployment contract + evidence tracker updates)
- Reliability process artifacts added: PR gate template and gate closeout template
- Validation runtime hardening added: stricter HMAC parsing and weighted confidence consistency
- Security/runtime test coverage expanded: admin import hardening, validation routes, HMAC/cap edge paths
- CI security workflow hardened for gitleaks push-range scans (`checkout fetch-depth: 0`)
- Phase 2 startup hardening: `VALIDATION_HMAC_SECRET` now required at production startup (raises `RuntimeError` on missing); `CORS_ALLOW_ORIGIN_REGEX` compiled at startup to catch malformed regex before traffic begins
- Phase 2 rate-limit observability: Redis unavailability in production now emits a `CRITICAL` log (`rate_limit_redis_unavailable`) instead of silently bypassing; fail-open behavior retained for reliability but is now auditable
- Phase 2 test coverage: startup tests added for missing HMAC secret and invalid CORS regex; cross-user validation access denial explicitly tested (trigger + read endpoints)
- Phase 1 stale-record observability: ingest script now logs `stale_record_update` line with `refresh_started_at` timestamp and row count immediately after marking — provides per-refresh audit trail in CI/ops logs
- Phase 5 backend runtime complete: pin/unpin endpoint (`PATCH /leads/{id}/validation/{field_name}`), retention pruner (`POST /admin/validation/prune`), inter-fetch jitter (500ms–2000ms), pinned-field skip in `process_run_by_id`, CF Worker cron (`infra/validation-cron.js` + `wrangler.validation-cron.toml`), full unit/route test coverage; HMAC startup guard active in production
- Offline sync hardening complete: app-level queue flushing now runs on token availability/online/interval, queue-count state is event-driven across views, and duplicate concurrent queue flushes are guarded in `offlineQueue.ts`
- Session evidence and gate closeout artifacts added under `docs/evidence/` (`session_roadmap_closure_2026-04-19.md`, `gate_closeout_2026-04-19.md`)

### Confirmed by recent checks

- Backend compile check passes (`python3 -m compileall backend/app scripts`)
- Frontend build passes (`npm run build`)
- Frontend typecheck passes (`npm run typecheck`)
- CI warning/regression fixes landed for startup lifecycle deprecation, raw-request-body test warning, and scoring saturation edge case
- Manual prototype flow verified: fetch, save, note, saved view rendering
- Post-hardening frontend checks pass after queue-sync updates (`npm run typecheck`, `npm run build`)

### Confirmed open gaps (must close before pilot)

- Security P0 verification is partially closed: startup/auth/authz/admin/HMAC suites pass and staging negative auth/HMAC smoke is captured; remaining runtime sign-off deltas are authenticated success-path smoke and explicit live TLS cert-chain verification evidence (see Phase 2 + `docs/evidence/phase2_security_signoff_2026-04-19.md`)
- Security scanner remediation is complete in-repo (`starlette` pin, CI pip upgrade, gitleaks false-positive allowlist); CI-linked confirmation URL remains open in this session
- Backend security test coverage and staging negative-path runtime evidence are current; authenticated staging success-path evidence and CI-linked run URLs remain open
- Phase 5 evidence sign-off still open (10+ sample runs with correct outcomes required before gate can close)
- Phase 6 OSM enrichment deployed; Overpass retry logic in place (2 attempts, 1s delay, graceful None fallback); Render env vars `OVERPASS_TIMEOUT_SECONDS` and `OVERPASS_ENDPOINT` documented in DEPLOYMENT_GUIDE and REQUIRED_SECRETS; evidence sign-off pending once enrichment hits confirm in staging
- Scoring calibration evidence is incomplete (5-route evidence + `Other/Unknown` threshold sign-off) (see Phase 3)
- Scoring v2 shadow evidence/cutover gate is open (top-20 save/contacted uplift + latency guardrails not yet evidenced) (see Phase 3)
- Evidence capture for ingestion QA and scoring validation is incomplete (see Phase 1)
- Staging-backed evidence execution remains blocked in local session without staging runtime inputs (`INGEST_DATABASE_URL`, staging bearer token + route IDs) and script runtime dependency installation for EXPLAIN capture
- Production DB TLS connectivity is restored using CA-chain PEM configuration; remaining work is to document and regression-test this deployment path so it stays stable
- Branch protection, uptime monitoring, and log forwarding remain external platform tasks not yet evidenced in repo
- Phase 4 error handling complete: `toUserMessage()` helper wired into all mutation catch sites in `App.tsx` (onCreated, onSaveLead, onSaveLeadWithNote, onApplyFilters, onCorridorChange); 401/429/network failures produce distinct actionable messages
- Phase 4 geocode/GPS error clarity complete: RouteForm surfaces "Couldn't find X — try adding a city or zip code" on no-result; "Geocoding unavailable — check your connection" on network failure; GPS denial distinguishes permission-denied from unavailable
- Phase 7 ORS upstream resilience complete: `routing_service.py` retries up to 2 attempts with 1s delay on transient errors (timeout/ConnectError/5xx); 4xx errors are terminal; on exhaustion falls back to straight-line mock with `properties.degraded=True`; degraded routes cached with short TTL (≤300s)
- Phase 7 Photon geocode resilience complete: `geocode_service.py` retries up to 2 attempts with 0.5s delay; same error taxonomy; on exhaustion returns POC fallback with `degraded=True`
- Phase 7 audit latency tracking complete: `duration_ms` (time.monotonic) included in every `audit_event` log line in `main.py`; enables Logtail p95 alert rules
- 18 new unit tests for upstream resilience (all paths: retry success, retry exhaustion → degraded, cache hit, 4xx terminal, degraded flag propagation); 94 backend tests total passing
- Phase 6 Overpass retry complete: `osm_enrichment_service.py` retries up to 2 attempts with 1s delay on transient errors; 4xx terminal; exhaustion returns None gracefully — enrichment never raises, always records attempted timestamp
- 11 new Overpass resilience tests added; 105 backend tests total passing
- Phase 0 baseline docs complete: `backend/.env.example`, `frontend/.env.example`, root `.env.example` with all env vars through Phase 7; `README.md` updated with accurate setup steps and runbook reference
- Phase 10 code complete: `is_blue_collar` + owner-contact columns (migration 0008), `classify()` returns `(insurance_class, is_blue_collar)` tuple, expanded blue-collar category mappings (auto detailing, towing, weld/fab, pest, lawn, pressure wash, painting, cleaning, locksmith), +5 fit-score bonus in v1 and v2, OSM `operator` tag extraction → `owner_name`, JSON-LD Person + website-text heuristic owner extraction in validation service, `sort_by` / `sort_dir` / `group_by` on `GET /leads` and `GET /saved-leads` (9 sort modes, 7 group modes), expanded filter params (`blue_collar`, `has_owner_name`, `operating_status`, `score_band`, `has_notes`, `saved_after`, `saved_before`, `overdue_only`, `untouched_only`), Today view gains `blue_collar_today` and `has_owner_name` sections, Phase 10 export columns added to both CSVs (`is_blue_collar`, `owner_name`, `owner_name_source`, `owner_name_confidence` as %, `operating_status`), grouped CSV export via `?group_by=`, manual `owner_name` write via `PATCH /saved-leads/{id}` (source=manual, confidence=1.0, never overwritten), `ingest_overture.py` and `backfill_classification.py` updated for tuple unpack + `is_blue_collar` upsert; all 105 backend tests passing
- Phase 8 prerequisite complete: `docs/RUNBOOK.md` (266 lines) covering ingestion trigger, all quota/outage scenarios (ORS/Photon/Overpass/Clerk/validation), DB migration recovery, Redis down, CF Worker troubleshooting, Render + CF Pages rollback, support contacts, pilot P0-P3 SLA
- `docs/REQUIRED_SECRETS.md` and `docs/DEPLOYMENT_GUIDE.md` updated with OVERPASS_* and ENRICHMENT_* env vars

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

**Status: Code complete — clean-machine walkthrough verification remaining**

**Scope:**
Lock current architecture, environments, and dev workflow. Ensure any developer can set up and run the system from scratch without tribal knowledge.

**Deliverables:**
- Repository structure and owner docs current (`README`, `DEPLOYMENT_GUIDE`, `REQUIRED_SECRETS`) ✅ (complete — all updated with Phase 7 env vars, runbook reference, and accurate setup steps)
- Clean-machine setup validation: backend, frontend, and database smoke flow
- CI path covering: backend lint/compile, frontend build, basic smoke checks
- Rollback instructions documented for Render and Cloudflare Pages deploys ✅ (complete — see `docs/RUNBOOK.md` §4, §8)

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

**Status: In progress — P0-1/2/3/4 code landed with emergency controls + key P1 controls landed; test verification and staging negative-path evidence captured, scanner/sign-off deltas remain**

This is the highest-risk open work. All P0 items must close before pilot traffic. Security work that is backend-only can be parallelized against Phase 3 frontend work.

**Scope:**
Close all P0 security risks. Establish baseline hardening across auth, data access, API protection, secrets, and CI.

**Deliverables — P0 (must close before any pilot traffic):**

- **P0-1 DB TLS:** Runtime enforces strict production startup failure on insecure TLS config. Temporary emergency override exists (`DATABASE_TLS_EMERGENCY_INSECURE_OVERRIDE`) and is allowed only until `DATABASE_TLS_EMERGENCY_OVERRIDE_SUNSET`; usage must be audited and retired before pilot.
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
- New/changed security tests: strict DB TLS required in production (with startup hard-fail on insecure config), JWT verification hard-fail when JWKS/issuer misconfigured, `poc_mode=true` startup block in production
- New/changed authz tests: admin allowlist + path allowlist, HMAC signature validity/expiry checks, extended rate-limit enforcement and body-size limits
- New/changed middleware tests: response security headers, request body size enforcement, production HSTS header behavior
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

**Status: In progress — explanation text + one-time tooltip + v2 shadow + quality improvements implemented; evidence/sign-off and cutover gate missing**

**Scope:**
Validate scoring quality on real data and complete the score explanation display in the UI. Vertical profiles are documented but the config path is deferred — do not build a multi-profile config system for MVP.

**Deliverables:**
- Five-route scoring validation run on real metro data; outcomes documented in the evidence log (`docs/PHASE1_4_VALIDATION.md` for now)
- `insurance_class = 'Other'` / `'Unknown'` rate measured and <= 35% for launch metro (sample size >= 500 classified businesses)
- v2 shadow scoring comparison artifact for 5 routes (rank deltas, top-k overlap, proxy save/contacted lift), with `v1` as default until launch gate passes
- v2 quality calibration enhancements shipped (non-breaking): geo-aware priors, validation quality penalties, weak-name penalties, adaptive feedback weighting by evidence volume
- Explicit v2 launch gate documented and satisfied before default cutover:
  - top-20 save-rate uplift over v1
  - top-20 contacted-rate uplift over v1
  - no p95 latency regression beyond threshold
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

**Status: In progress — all code tasks complete; evidence sign-off remaining**

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
- Route entry UX: error clarity for geocode failures, reverse geocode on current location ✅ (complete — actionable copy for no-result, network failure, GPS denial)
- Error handling: clear states for 401, 429, and network failures on all mutation actions ✅ (complete — toUserMessage wired into all mutation surfaces)

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

**Status: Feature complete — pending evidence sign-off**

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
- Batch cron endpoint called by CF Worker; counter enforces global daily cap
- HMAC token auth on `run-due` endpoint rejects invalid/expired tokens
- Nightly retention pruning job runs without errors
- 30-day calibration plan documented in the evidence log (first 200 manual outcomes required before weight tuning)

**Blocking dependencies:** Phase 2 (P0 security + HMAC secret), Phase 3 (score explanation complete so validation badge fits UI correctly)

---

### Phase 6 — Dataset Expansion

**Status: In progress — OSM enrichment + Overpass retry complete; staging verification pending**

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
- Overpass fetch utility: point lookup by lat/lng/name, 50m radius, extract `phone`/`contact:phone`, `website`/`contact:website`, `opening_hours` ✅ (complete — retry + graceful fallback added, 11 unit tests passing)
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

**Status: In progress — code tasks complete (retry/degraded fallback, audit latency); platform tasks pending (log forwarding, uptime monitor, alert rules, DB roles, backup drill)**

**Scope:**
Stabilize operations before pilot traffic. Health monitoring, alerting, error handling, and backup verification.

**Deliverables:**
- Structured audit logging for all required events (per `securityplan.md` §4.8): auth failures, 403s, 429s, admin access, note/status mutations, exports, validation runs
- Log forwarding from Render to external service (if not already done in Phase 2)
- Uptime monitoring for `/health` with alerting (if not already done in Phase 2)
- Alert rules: 401/403 spike (>20 in 5 min from single IP), admin endpoint failures (>3 in 10 min), export volume (>10 exports/hr from one user), 5xx rate >1% over 5 min
- p95 latency tracking for key endpoints; alert if route creation + lead retrieval exceeds 5s p95 ✅ (duration_ms in every audit_event log line — ready for Logtail alert rules)
- Queue/retry behavior verified for ORS and Photon upstream failures (exponential backoff, graceful degraded mode) ✅ (complete — 18 unit tests passing, see commit 65f9ab5)
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
- Operational runbook committed: ingestion trigger, quota exhaustion (ORS, Photon, Clerk), backend outage, validation cap reached ✅ (complete — `docs/RUNBOOK.md`)

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
- Phase 10 lead intelligence plan reviewed and sequenced

**Blocking dependencies:** Phases 5–8 complete

---

### Phase 10 — Lead Intelligence: Sorting, Grouping, Blue-Collar Category, and Owner Contact

**Status: Code complete — staging evidence and exit-criteria sign-off remaining**

**Scope:**
Deepen lead handling quality and rep control across every tab. This phase introduces a blue-collar meta-category for faster vertical-within-vertical targeting, a structured owner/contact name field with multi-source extraction and validation, meaningful server-side sort and filter expansion, and user-controlled grouping on the lead list and saved tabs. The Today view gains configurable sections. Exports gain the new fields. This is fundamentally a data model + API + workflow phase — UI elements are included only where required to expose the new capabilities.

**What this phase does NOT do:** full UI redesign, new map features, new route geometry logic, new upstream data sources beyond what Phase 6 already established.

---

**Deliverables — 10-A: Blue-Collar Meta-Category**

The existing `insurance_class` values already capture the right atoms. Blue-collar is a derived grouping, not a new class. Implementation:

- Add `is_blue_collar` boolean column to `business` (default `false`, non-null, indexed)
- Definition: `is_blue_collar = insurance_class IN ('Auto Service', 'Contractor / Trades', 'Personal Services')` — captures hands-on, owner-operated, in-person service businesses that are the highest-value insurance prospects
- Populate via migration backfill on existing rows; set on insert/upsert in `ingest_overture.py` and `classification_service.py`
- Scoring service: `is_blue_collar` businesses receive a +5 additive bonus to `fit_score` (non-breaking; does not change v1 vs v2 gating)
- API filter: add `blue_collar=true/false` query param to `GET /leads` and `GET /saved-leads`
- API sort: blue-collar-first sort mode (`sort_by=blue_collar_score` — sorts `is_blue_collar DESC, final_score DESC`)
- Export: add `is_blue_collar` column to both per-route and cross-route CSV exports
- `classification_service.py` extension: add additional category mappings that clearly belong in blue-collar but currently fall to Other Commercial — specifically: auto detailing, auto glass, towing, welding/fabrication, pest control, landscaping/lawn care, pressure washing, painting contractor, cleaning services, locksmith

**Migration:** `0006_blue_collar_and_owner_contact.py`
```sql
ALTER TABLE business
  ADD COLUMN is_blue_collar BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN owner_name TEXT,
  ADD COLUMN owner_name_source TEXT,  -- 'manual' | 'website_jsonld' | 'website_text' | 'osm_operator' | 'unknown'
  ADD COLUMN owner_name_confidence REAL,  -- 0.0–1.0
  ADD COLUMN owner_name_last_checked_at TIMESTAMPTZ;

CREATE INDEX idx_business_is_blue_collar ON business (is_blue_collar);
CREATE INDEX idx_business_owner_name ON business (owner_name) WHERE owner_name IS NOT NULL;

-- Backfill is_blue_collar from existing insurance_class
UPDATE business
SET is_blue_collar = TRUE
WHERE insurance_class IN ('Auto Service', 'Contractor / Trades', 'Personal Services');
```

---

**Deliverables — 10-B: Owner / Contact Name**

Goal: give reps a name to use when they walk in the door. Even a partial or low-confidence name is better than nothing — but it must be clearly labeled with its confidence level so reps do not rely on it blindly.

**Data model** (in migration 0006 above):
- `owner_name TEXT` — raw name as extracted; may be a full name, first name only, or business owner title
- `owner_name_source TEXT` — enum: `manual` (rep-entered), `website_jsonld` (JSON-LD Person schema), `website_text` (heuristic page scrape), `osm_operator` (OSM `operator` tag), `unknown`
- `owner_name_confidence REAL` — 0.0–1.0; source-based baseline: jsonld=0.85, osm_operator=0.70, website_text=0.50, manual=1.0
- `owner_name_last_checked_at TIMESTAMPTZ` — for freshness gating (re-check if > 60 days old and business is saved)

**Extraction sources (in priority order):**

1. **JSON-LD Person schema** — during Phase 5 website validation fetch, if a `Person` or `LocalBusiness.employee` schema is present, extract `name`. This is the highest-confidence automated source. Wire into `validation_service.py` as an additional field parsed from the JSON-LD payload already being fetched.

2. **OSM `operator` tag** — the Overpass fetch in `osm_enrichment_service.py` already retrieves all tags. Add `operator` to the tag extraction; store as `owner_name` when no higher-confidence source exists. OSM `operator` is often the business owner's name for sole proprietorships (confidence: 0.70).

3. **Website text heuristics** — secondary pass during Phase 5 website crawl: scan for patterns like "Owner: [Name]", "Founded by [Name]", "Contact [Name]" in `<meta>`, `<h1–h3>`, and footer text. Truncate and normalize. Confidence: 0.50.

4. **Manual rep entry** — `PATCH /saved-leads/{id}` gains an `owner_name` field that reps can set from the lead detail view. Manual entry is always confidence 1.0 and is never overwritten by automated extraction.

**Write rules:**
- Never overwrite a `manual` source with an automated one
- Only overwrite a lower-confidence automated source with a higher-confidence one
- If website fetch fails, do not clear an existing `owner_name`; leave it in place with its existing confidence

**API surface:**
- `GET /leads` response: add `owner_name`, `owner_name_source`, `owner_name_confidence` to the lead schema
- `GET /saved-leads` response: same
- `PATCH /saved-leads/{id}`: add `owner_name` (rep-editable; sets source to `manual`, confidence 1.0)
- `GET /leads` filter: `has_owner_name=true` — filter to leads where `owner_name IS NOT NULL`
- `GET /saved-leads` filter: same
- Export: add `owner_name`, `owner_name_source`, `owner_name_confidence` columns to both CSV exports

**Validation integration:**
- Add `owner_name` as a pinnable field in `lead_field_validation` — field_name = `owner_name`
- Confidence displayed in evidence drawer alongside website/phone/address/hours
- A manually entered owner name is treated as pinned by default (skip automated re-extraction)

**UI elements (minimal — data surface only):**
- Lead card: if `owner_name` is present, show it beneath the business name with a confidence indicator (high/medium/low chip)
- Lead detail: editable owner name field with source label; confidence chip; "Re-check" button triggers a fresh website JSON-LD pass for that business
- Saved lead export: owner_name column included automatically

---

**Deliverables — 10-C: Expanded Server-Side Sorting**

Current state: sort is client-side only (`score` or `business_type`). No sort param reaches the backend.

Add `sort_by` and `sort_dir` query params to `GET /leads` and `GET /saved-leads`:

| `sort_by` value | Description |
|---|---|
| `score` | `final_score DESC` (current default) |
| `blue_collar_score` | `is_blue_collar DESC, final_score DESC` |
| `name` | `business.name ASC/DESC` |
| `distance` | `distance_m ASC/DESC` |
| `validation_confidence` | `lead_field_validation.overall_confidence DESC NULLS LAST` |
| `follow_up_date` | `next_follow_up_at ASC NULLS LAST` (saved leads only) |
| `last_contact` | `last_contact_attempt_at DESC NULLS LAST` (saved leads only) |
| `owner_name` | `owner_name ASC NULLS LAST` (leads with owner name first) |
| `saved_at` | `saved_lead.created_at DESC` (saved leads only) |

- `sort_dir`: `asc` | `desc` (default per sort_by as noted above)
- Multi-key sort: primary + secondary. `sort_by=blue_collar_score` implies `is_blue_collar DESC, final_score DESC`. Others use `name ASC` as tiebreaker.
- Frontend sort controls updated to use server-side params; client-side sort removed (single source of truth)
- Backend enforces an allowlist of valid `sort_by` values; unknown values return 422

---

**Deliverables — 10-D: Expanded Server-Side Filtering**

Add the following filter params to `GET /leads` and/or `GET /saved-leads`:

| Param | Type | Applies to | Description |
|---|---|---|---|
| `blue_collar` | bool | both | Filter to `is_blue_collar = true/false` |
| `has_owner_name` | bool | both | Filter to leads where `owner_name IS NOT NULL` |
| `min_validation_confidence` | float 0–1 | both | Filter by overall validation confidence |
| `validation_state` | enum | both | `validated`, `mostly_valid`, `needs_review`, `low_confidence`, `unchecked` |
| `operating_status` | enum | both | `open`, `possibly_closed`, `unknown` (maps to `business.operating_status`) |
| `score_band` | enum | both | `high` (≥70), `medium` (40–69), `low` (<40) |
| `has_notes` | bool | saved | Filter to saved leads that have at least one note |
| `status` | enum[] | saved | Existing; ensure multi-value works correctly |
| `saved_after` | date | saved | `saved_lead.created_at >= date` |
| `saved_before` | date | saved | `saved_lead.created_at <= date` |
| `due_before` | date | saved | Existing; confirm works with new sort |
| `overdue_only` | bool | saved | `next_follow_up_at < now() AND status NOT IN ('called','visited','not_interested')` |
| `untouched_only` | bool | saved | `last_contact_attempt_at IS NULL` |

All filters are additive (AND). Invalid values return 422 with a descriptive message.

---

**Deliverables — 10-E: Grouping on Lead List and Saved Tabs**

Add a `group_by` query param to `GET /leads` and `GET /saved-leads`. The API returns results in grouped sections rather than a flat list. Each section has a `group_key`, `group_label`, `count`, and `leads[]` array.

| `group_by` value | Groups |
|---|---|
| `insurance_class` | One section per class; ordered by fit score (blue-collar classes first by default) |
| `blue_collar` | Two sections: "Blue Collar" then "Other" |
| `score_band` | Three sections: High (≥70), Medium (40–69), Low (<40) |
| `validation_state` | Five sections: Validated → Unchecked |
| `follow_up_urgency` | Four sections: Overdue, Due Today, Upcoming, No Date (saved leads only) |
| `contact_status` | Three sections: Contacted, Saved/Untouched, Not Interested (saved leads only) |
| `owner_name_status` | Two sections: Has Owner Name, No Owner Name |

- No `group_by` param = flat list (current behavior, backward-compatible)
- Within each group, the active `sort_by` and `sort_dir` apply
- Empty groups are omitted from the response
- Response schema: `{ groups: [{ key, label, count, leads[] }] }` when grouped; `{ leads[] }` when flat
- Frontend: renders section headers between groups with count badges; collapsible (collapsed state persisted in localStorage)

---

**Deliverables — 10-F: Today View Improvements**

- Add a **Blue Collar Today** section: overdue + due today filtered to `is_blue_collar = true`, capped at 5 — surfaces the highest-priority blue-collar follow-ups in one glance
- Add a **Has Owner Name** section: top 5 unsaved high-score leads where `owner_name IS NOT NULL` — "ready to approach" leads where the rep has a name
- Section priority order becomes user-configurable: stored in `user_preferences` (new table or `saved_lead` metadata — TBD); default order: Overdue → Due Today → Blue Collar Today → High Priority Untouched → Has Owner Name → Recent Route
- Empty sections are always hidden; minimum 1 lead required to show a section
- `GET /saved-leads/today` response schema extended with new sections; existing sections unchanged (backward-compatible)

---

**Deliverables — 10-G: Export Enhancements**

Both the per-route CSV (`GET /export/routes/{id}/leads.csv`) and cross-route CSV (`GET /export/saved-leads.csv`) gain new columns:

| New column | Source |
|---|---|
| `is_blue_collar` | `business.is_blue_collar` |
| `owner_name` | `business.owner_name` |
| `owner_name_source` | `business.owner_name_source` |
| `owner_name_confidence` | `business.owner_name_confidence` |
| `validation_state` | overall validation state label |
| `operating_status` | `business.operating_status` |

- Columns are appended after existing columns — no column reordering (preserves existing AMS import mappings)
- `owner_name_confidence` exported as a percentage string (`"85%"`) for readability in AMS
- Add `group_by` filter support to cross-route export: `GET /export/saved-leads.csv?group_by=insurance_class` produces a CSV with a blank separator row and group header between sections

---

**Database migrations required (0006):**
- `business.is_blue_collar` BOOLEAN NOT NULL DEFAULT FALSE + index
- `business.owner_name` TEXT nullable
- `business.owner_name_source` TEXT nullable
- `business.owner_name_confidence` REAL nullable
- `business.owner_name_last_checked_at` TIMESTAMPTZ nullable
- Backfill `is_blue_collar` from `insurance_class`
- Index on `owner_name` (partial, WHERE NOT NULL)

**Classification service updates required:**
- `classify()` returns `(insurance_class, is_blue_collar)` tuple; callers updated
- Expand blue-collar category mappings: auto detailing, auto glass, towing, welding/fabrication, pest control, landscaping/lawn care, pressure washing, painting contractor, cleaning services, locksmith
- `NAME_KEYWORDS` expanded with blue-collar name signals: `"detail"`, `"tow"`, `"weld"`, `"pest"`, `"lawn"`, `"landscape"`, `"pressure wash"`, `"paint"`, `"clean"`, `"lock"`

**Scoring service updates required:**
- `is_blue_collar` parameter added to `compute_score()` and `compute_score_v2()`
- +5 additive bonus to `fit_score` when `is_blue_collar = true` (does not affect `distance_score` or `actionability_score`)
- Score explanation updated: "Blue collar fit" label shown when `is_blue_collar = true`

---

**Test focus:**
- New/changed: `is_blue_collar` classification unit tests for all new category mappings; backfill correctness on known fixture rows
- New/changed: `owner_name` extraction unit tests — JSON-LD Person, OSM operator tag, website heuristics; write-rule precedence (manual never overwritten)
- New/changed: sort param unit tests — all 9 `sort_by` values; unknown value → 422
- New/changed: filter param unit tests — all new params; invalid enum → 422; combined filters (AND logic)
- New/changed: grouping response schema tests — all 7 `group_by` modes; empty group omission; flat fallback
- New/changed: Today view section tests — Blue Collar Today section, Has Owner Name section, empty section hiding
- New/changed: export column tests — new columns present, confidence as percentage, group-by CSV separator rows
- Existing regression checks: existing `insurance_class` sort and filter behavior unchanged; scoring v1/v2 rank order not materially changed by +5 blue-collar bonus (verify top-20 overlap ≥ 85% vs pre-bonus on test routes)

---

**Exit criteria:**
- `is_blue_collar` is set correctly on ≥ 95% of Auto Service, Contractor / Trades, and Personal Services businesses in a test ingestion run (verified by spot-check query)
- New blue-collar category mappings cover all listed business types (verified against test fixture with known categories)
- `owner_name` populated for ≥ 20% of saved leads after one enrichment + validation pass on a staging dataset of ≥ 50 saved leads with websites
- Manual `owner_name` entry round-trips correctly and is never overwritten by automated extraction
- All 9 sort modes return correctly ordered results on a real dataset (verified by manual inspection of 3 test routes)
- All new filter params work correctly in combination on a real dataset
- Grouping response schema is valid for all 7 modes; empty groups are absent from response
- Today view shows Blue Collar Today and Has Owner Name sections when qualifying leads exist; both are absent when they do not
- Export columns are present and correctly populated; grouped export has separator rows in correct positions
- +5 blue-collar bonus does not change top-20 rank order by more than 15% on the 5 Phase 3 validation routes (regression guardrail)
- All new tests pass; existing suite remains green (105+ passing)

**Blocking dependencies:** Phase 9 complete or in sustained pilot with stable data; Phase 5 validation system active (owner name extraction depends on the website fetch infrastructure)

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
| F — Lead Intelligence | Phase 10 | Phase 9 complete (or parallel with Phase 9 post-baseline) |

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
| 0 | Baseline reliability | Code complete — walkthrough verification remaining | Medium |
| 1 | Data/routing foundation evidence | Mostly done | Medium |
| 2 | Security lockdown | In progress (verification run captured; scanner/runtime deltas remain) | Medium |
| 3 | Scoring + score explanation | In progress (v2 shadow + quality pass landed; evidence incomplete) | Medium |
| 4 | Discovery UX + workflow completion | In progress — code complete; evidence sign-off remaining | Medium |
| 5 | Lead validation system | Feature complete — evidence sign-off remaining | High |
| 6 | Dataset expansion | In progress — Overpass retry complete; staging evidence pending | Medium |
| 7 | Operations hardening | In progress — code complete; platform setup remaining | Low |
| 8 | MVP verification and QA | Not started | Low |
| 9 | Pilot and launch | Not started | Low |
| 10 | Lead intelligence — sorting, grouping, blue-collar, owner contact | Code complete — evidence pending | Medium |

---

## Immediate Next Sprint (Recommended)

1. **Close Phase 2 sign-off deltas** *(requires staging Clerk token)*: capture authenticated success-path smoke (`GET /routes`, lead fetch, `GET /saved-leads/today`, `GET /export/saved-leads.csv`), grab the GitHub Actions run URL for commit `7f340ae`, and paste both into `docs/evidence/phase2_security_signoff_2026-04-19.md` and `docs/evidence/gate_closeout_2026-04-19.md`. Enable branch protection on `main` in GitHub settings.
2. **Wire Phase 7 platform tasks** *(requires Render/external-account access; step-by-step in `docs/evidence/phase7_ops_platform_guide.md`)*:
   - Render → Log Streams → Logtail (7-C)
   - UptimeRobot → monitor `/health` every 5 min with keyword `"status":"ok"` (7-D)
   - Logtail → 5 alert rules: 401/403 spike, admin failures, export volume, 5xx rate, p95 >5s on `/routes`/`/leads` (7-E)
   - Supabase: remove `public` from PostgREST exposed schemas, verify `service_role` key not in frontend dist (7-G)
   - `pg_dump` backup drill + document restore path (7-H)
3. **Close Phase 4/5 evidence** *(requires staging Clerk token + saved leads)*:
   - Offline reconnect no-loss: airplane mode → add note + status change → reconnect → confirm sync
   - Dedup spot-check: 3 routes same metro, verify no duplicate pairs in top 20
   - Today dashboard: set overdue follow-up, confirm it appears in correct section
   - 10+ validation runs with correct website/phone outcomes; `bot_blocked` → `unknown` test case
4. **Close Phase 1/3 evidence** *(requires `INGEST_DATABASE_URL` + staging route IDs)*:
   - Replace EXPLAIN placeholder (`docs/evidence/phase1_explain_route_pending_2026-04-17.txt`) with a live trace
   - Run ingestion QA script and commit metrics artifact
   - Run `validate_scoring.py` on 5 routes; commit `other_unknown_rate`
5. **Verify Phase 6 Overpass enrichment in staging** — set `OVERPASS_TIMEOUT_SECONDS=10` (and `OVERPASS_ENDPOINT=https://overpass.kumi.systems/api/interpreter` if the primary still times out) in Render env vars; save a lead and confirm `osm_phone` or `osm_website` populates in Supabase within 30s.
6. **Use gate closeout workflow for each merge/deploy** — attach `docs/GATE_CLOSEOUT_TEMPLATE.md` entries with rollback notes and artifact links before marking any gate complete.

---

## Change Control

When updating this roadmap:
- Update phase status and confidence only after evidence exists.
- Reference supporting docs in commit messages when phase specs change.
- Do not mark a phase complete without explicit exit-criteria proof committed to the evidence log (`docs/PHASE1_4_VALIDATION.md` for now, Phases 1–4) or verifiable in the codebase/config (Phases 5–9).
