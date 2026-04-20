 # RepRoute Codebase Audit — GLM Report v2

**Date:** April 20, 2026 (re-audited after codebase updates)
**Auditor:** Cline (automated full-codebase audit against `docs/roadmap.md`)
**Scope:** Every file in the repository, line-by-line, measured against the roadmap's phase deliverables, exit criteria, and MVP definition.

---

## Executive Summary

The RepRoute codebase is **architecturally sound** with significant recent improvements since the first audit pass. Backend compile and frontend typecheck both pass clean. The owner name and employee count extraction pipelines are now fully wired from website validation through OSM enrichment. The `validation_state` field is properly populated in saved lead responses. Frontend API client params are fully aligned with backend endpoints.

**Remaining issues** are one dead-code function, one missing `group_by` param on leads fetch, a frontend type mismatch on grouped responses, unnecessary `(it as any)` casts, and a large body of **evidence/sign-off gaps** that prevent any phase from being formally closed.

**Estimated distance to MVP:** ~70–80% of code is written and wired; ~20–30% of verification, evidence, platform wiring, and UI polish remains. The primary blockers are operational (evidence capture, Phase 11 Gate 4 polish) rather than structural.

---

## Table of Contents

1. [Bugs and Code Issues](#1-bugs-and-code-issues)
2. [Incomplete Implementations](#2-incomplete-implementations)
3. [Frontend ↔ Backend Alignment](#3-frontend--backend-alignment)
4. [Phase-by-Phase Gap Analysis](#4-phase-by-phase-gap-analysis)
5. [Evidence and Sign-off Deficit](#5-evidence-and-sign-off-deficit)
6. [Test Coverage Assessment](#6-test-coverage-assessment)
7. [Security Posture](#7-security-posture)
8. [Infrastructure and Platform](#8-infrastructure-and-platform)
9. [MVP Readiness Scorecard](#9-mvp-readiness-scorecard)
10. [Recommended Priority Actions](#10-recommended-priority-actions)

---

## 1. Bugs and Code Issues

### 1A. `main.py` — Fragile forward reference in `_validate_startup_config()`

**File:** `backend/app/main.py`
**Lines:** 46, 55 reference `cors_origin_regex` and `cors_origins`
**Defined:** Lines 79–80

The function `_validate_startup_config()` reads module-level variables `cors_origin_regex` and `cors_origins` that are assigned 30+ lines later. In normal execution this works (module-level code runs before `lifespan()`), but the backward-compatible `startup()` function (line 73) also calls it. If `startup()` is imported and called before module load completes (e.g., in tests), it raises `NameError`.

**Severity:** Low (works in practice, fragile in testing/refactoring)
**Fix:** Read CORS config from `get_settings()` inside the function.

### 1B. Dead code: `_write_owner_name()` in `enrichment_service.py`

**File:** `backend/app/services/enrichment_service.py`, lines 27–46

`_write_owner_name()` is a private function that was superseded by `promote_owner_name()` from `contact_intelligence.py`. It is never called anywhere in the codebase (confirmed by grep). It bypasses the confidence resolution and person-name guard that `promote_owner_name()` provides. If anyone were to call it in the future, it would write owner names without proper validation.

**Severity:** Low (dead code, no runtime impact)
**Fix:** Delete the function and its import of `resolved_confidence` (line 15) if unused elsewhere.

### 1C. `fetchLeads()` frontend missing `group_by` param

**File:** `frontend/src/api/client.ts`, `fetchLeads()` function (line 170)

The backend `GET /routes/{route_id}/leads` supports `group_by` (confirmed in `leads.py` line 42), and the backend returns a `groups` field in the response schema (`LeadsResponse.groups`). However, `fetchLeads()` does not accept or send a `group_by` param. The response type also doesn't include the `groups` field.

**Severity:** Medium (grouped lead browsing is unavailable in the frontend)
**Fix:** Add `groupBy?: string` to the options type, send it as `group_by`, and add `groups` to the response type.

### 1D. `listSavedLeads()` grouped response type mismatch

**File:** `frontend/src/api/client.ts`, line 280

`listSavedLeads()` is typed to return `Promise<SavedLead[]>`. But when the backend receives `group_by`, it returns a JSON array of group objects `{key, label, count, leads}`, not `SavedLead[]`. The frontend would receive objects that don't match the type, causing silent rendering failures.

Currently the `SavedLeads.tsx` component doesn't send `groupBy`, so this doesn't trigger in practice. But the API client type is misleading.

**Severity:** Medium (latent — will break when grouped saved leads UI is built)
**Fix:** Either create a separate `listSavedLeadsGrouped()` function with the correct return type, or make `listSavedLeads()` return a union type.

### 1E. `SavedLeads.tsx` uses `(it as any)` casts for fields that exist on the type

**File:** `frontend/src/components/SavedLeads.tsx`, lines 498, 503, 506, 507, 508

The component renders `owner_name` and `employee_count_*` fields using `(it as any).owner_name` and `(it as any).employee_count_estimate` casts. But the `SavedLead` type in `client.ts` already includes these fields (lines 123–129, 130). The `as any` casts bypass TypeScript's type checking unnecessarily.

**Severity:** Low (works at runtime, defeats type safety)
**Fix:** Replace `(it as any).owner_name` with `it.owner_name`, etc.

### 1F. Client-side sorting defeats server-side capabilities

**File:** `frontend/src/components/SavedLeads.tsx`

The `SavedLeads` component fetches all saved leads via `listSavedLeads(token, statusFilter)` and then sorts them client-side with `sortSavedLeads()`. The backend supports 9 sort modes including `validation_confidence`, `blue_collar_score`, `owner_name`, `saved_at`. None of these server sort modes are used.

Additionally, the frontend only fetches by `status` filter — none of the backend's Phase 10 filters (`blue_collar`, `has_owner_name`, `has_employee_count`, `score_band`, `overdue_only`, `untouched_only`) are exposed in the UI.

**Severity:** Medium (Phase 10 backend capabilities unused, pagination broken if >100 leads)
**Fix:** Pass `sortBy`/`sortDir` to `listSavedLeads()` and use server-side sorting. Add filter controls for Phase 10 dimensions.

---

## 2. Incomplete Implementations

### 2A. Phase 11 Gate 4 — Polish (5 steps pending)

**Roadmap reference:** Phase 11, Gate 4 (steps 14–18)
**Status:** All 5 steps listed as "Pending"

| Step | Description | Status |
|------|-------------|--------|
| 14 | Error recovery: inline retry + dismiss on all error banners | Pending |
| 15 | Loading skeletons: Today, Saved, detail notes | Partial (SavedLeads has skeletons, others don't) |
| 16 | Micro-interactions: card lift, tab indicator, score badge pulse, status flash | Partial (status flash exists) |
| 17 | Onboarding replacement: remove modal, `isFirstRun` prop, extended/compact empty states | Pending |
| 18 | Accessibility pass: tap targets, focus rings, ARIA labels, focus trap | Pending |

### 2B. Phase 11-E — Already-worked markers on map (deferred)

**Current state:**
- `SavedLeadItem` backend schema: **no `lat`/`lng` fields**
- `SavedLead` frontend type: **no `lat`/`lng` fields**
- `_saved_leads_base_query()`: doesn't select `Business.geom`

**Impact:** Already-worked markers on the map cannot be implemented. This is acknowledged in the roadmap as deferred.

### 2C. Phase 11-E — Backend proximity filter stub not added

**Roadmap says:** `GET /saved-leads` gains optional `lat`, `lng`, `radius_m` params — accepted but ignored in Phase 11.

**Current state:** These params do not exist on the endpoint.

**Impact:** Low (Phase 12 scope), but the roadmap explicitly calls for stubs in Phase 11.

### 2D. Phase 12 Evidence Template Missing

No `docs/evidence/phase12_*` template exists. The `docs/evidence/phase12_owner_employee_template.md` referenced in the roadmap has not been created.

---

## 3. Frontend ↔ Backend Alignment

### Confirmed Working ✅

These items were fixed since the first audit:

| Feature | Status |
|---------|--------|
| `validation_state` populated in saved leads response | ✅ Fixed — joins `lead_field_validation`, computes via `_overall_label()` |
| `validation_state` on frontend `SavedLead` type | ✅ Fixed — `client.ts` line 132 |
| Phase 10 filter params on `listSavedLeads()` | ✅ Fixed — all 14 params wired |
| Owner name extraction from website validation | ✅ Fixed — `_extract_owner_from_html()` → `promote_owner_name()` |
| Employee count extraction from website validation | ✅ Fixed — `_extract_employee_count_from_html()` → `promote_employee_count()` |
| OSM operator tag → owner name | ✅ Fixed — `osm_enrichment_service.py` extracts with person-name guard |
| Export grouped CSV columns include Phase 10/12 | ✅ Confirmed — `insurance_class`, `operating_status`, `is_blue_collar`, `owner_name_*`, `employee_count_*` |
| PWA manifest, service worker, install prompt | ✅ Confirmed |
| CI pipeline (security, backend, frontend) | ✅ Confirmed |

### Remaining Gaps

| Gap | Details |
|-----|---------|
| `fetchLeads()` missing `group_by` | Backend supports it, frontend doesn't send it |
| `fetchLeads()` response missing `groups` field | `LeadsResponse.groups` not in frontend type |
| `listSavedLeads()` grouped response type | Returns `SavedLead[]` but backend sends group objects |
| `SavedLead` missing `lat`/`lng` | Both backend schema and frontend type |
| Client-side sorting in `SavedLeads.tsx` | Doesn't use server sort, breaks with >100 leads |
| Phase 10 filters not in Saved Leads UI | Backend supports them, no UI controls exposed |

---

## 4. Phase-by-Phase Gap Analysis

### Phase 0 — Baseline Freeze ✅ Code Complete

| Deliverable | Status |
|-------------|--------|
| README, DEPLOYMENT_GUIDE, REQUIRED_SECRETS current | ✅ |
| CI pipeline (security, backend test, frontend build) | ✅ |
| Rollback instructions (RUNBOOK.md) | ✅ |
| Clean-machine setup validation | ⚠️ Not evidenced |

### Phase 1 — Data/Routing Foundation ⚠️ Code Complete, Evidence Missing

| Deliverable | Status |
|-------------|--------|
| Ingestion QA artifact committed | ❌ Missing |
| EXPLAIN ANALYZE trace committed | ❌ Placeholder file |
| Stale record detection in ingest script | ✅ |

### Phase 2 — Security Lockdown ⚠️ Code Complete, Platform Pending

| Deliverable | Status |
|-------------|--------|
| P0-1 DB TLS enforcement | ✅ Startup check |
| P0-2 JWT verification | ✅ With JWKS cache |
| P0-3 Admin import hardening | ✅ Allowlist + path validation + concurrency |
| P0-4 POC mode guard | ✅ Startup check |
| Rate limiting on all mutation endpoints | ✅ |
| Request body size limit | ✅ |
| Security headers (backend + Cloudflare) | ✅ |
| Secret scanning (gitleaks) | ✅ In CI |
| Dependency audit (pip-audit + npm audit) | ✅ In CI |
| Branch protection on `main` | ❌ External platform task |
| Log forwarding | ❌ Not wired |
| Uptime monitoring | ❌ Not wired |

### Phase 3 — Scoring/Explanation ⚠️ Code Complete, Evidence Missing

| Deliverable | Status |
|-------------|--------|
| v2 quality calibration | ✅ |
| Score explanation UI | ✅ |
| Five-route scoring validation | ❌ Not evidenced |
| Other/Unknown rate ≤ 35% | ❌ Not measured |
| v2 shadow comparison artifact | ❌ Not produced |

### Phase 4 — Discovery UX ✅ Code Complete

| Deliverable | Status |
|-------------|--------|
| Follow-up fields on saved leads | ✅ |
| Deduplication (`_dedupe_leads()`) | ✅ |
| Today view with all sections | ✅ |
| Cross-route CSV export | ✅ |
| Offline queue + sync | ✅ |
| PWA install prompt | ✅ |
| Error handling | ✅ |

### Phase 5 — Lead Validation ✅ Code Complete

| Deliverable | Status |
|-------------|--------|
| Validation engines (website, phone, owner_name) | ✅ |
| Failure taxonomy | ✅ |
| API endpoints | ✅ |
| CF Worker cron | ✅ |
| UI badges and evidence drawer | ✅ |
| Retention pruning | ✅ |
| Evidence sign-off | ❌ Not committed |

### Phase 6 — Dataset Expansion ✅ Code Complete

| Deliverable | Status |
|-------------|--------|
| OSM enrichment with retry | ✅ |
| Enrichment quota counters | ✅ |
| 30-day freshness gate | ✅ |
| Background enrichment on save/route load | ✅ |

### Phase 7 — Operations Hardening ⚠️ Code Complete, Platform Pending

| Deliverable | Status |
|-------------|--------|
| Structured audit logging | ✅ |
| ORS/Photon retry fallback | ✅ |
| Log forwarding | ❌ |
| Uptime monitoring | ❌ |
| Alert rules | ❌ |
| Backup/restore drill | ❌ |
| Least-privileged DB roles | ❌ |

### Phase 8 — MVP Verification ❌ Blocked

Blocked by Phases 3–7 evidence.

### Phase 9 — Pilot ❌ Blocked

Blocked by Phase 8.

### Phase 10 — Lead Intelligence ✅ Code Complete

All deliverables implemented. Evidence sign-off not committed.

### Phase 11 — UI Overhaul ⚠️ Gates 1–3 Done, Gate 4 Pending

See §2A.

### Phase 12 — Owner/Contact Reliability ✅ Code Complete (wiring), ⚠️ Evidence Missing

| Deliverable | Status |
|-------------|--------|
| Employee count columns + migration | ✅ |
| `contact_intelligence.py` promotion engine | ✅ |
| Website JSON-LD employee count extraction | ✅ Wired in `validation_service.py` |
| Website text employee count extraction | ✅ Wired in `validation_service.py` |
| OSM operator → owner name | ✅ Wired in `enrichment_service.py` |
| Website JSON-LD owner name extraction | ✅ Wired in `validation_service.py` |
| Manual PATCH for owner_name and employee_count | ✅ |
| Export CSVs include all Phase 12 columns | ✅ |
| Frontend types include all Phase 12 fields | ✅ |
| Phase 12 evidence template | ❌ Not created |

---

## 5. Evidence and Sign-off Deficit

This is the single largest gap. **No phase has complete exit-criteria evidence committed.**

| Phase | Evidence Required | Evidence Committed |
|-------|-------------------|-------------------|
| 0 | Clean-machine walkthrough | ❌ None |
| 1 | Ingestion QA, EXPLAIN trace | ❌ Placeholder only |
| 2 | Auth smoke, branch protection | ⚠️ Partial (tests captured) |
| 3 | 5-route scoring, rate measurement, v2 artifact | ❌ None |
| 4 | Offline no-loss, dedup spot-check | ❌ None |
| 5 | 10+ validation runs | ❌ None |
| 6 | Enrichment before/after | ❌ None |
| 7 | Backup drill, DB roles, alert rules | ❌ None |
| 8 | Full QA matrix | ❌ Not started |
| 10 | Sort/filter/group on real data | ❌ None |
| 11 | Mobile e2e, accessibility | ❌ None |
| 12 | Owner/employee extraction rates | ❌ None |

---

## 6. Test Coverage Assessment

### Backend Tests (11 files)

| Test File | Covers |
|-----------|--------|
| `test_smoke.py` | Basic endpoint smoke |
| `test_admin_import_security.py` | Admin import hardening |
| `test_security_auth_and_authz.py` | JWT, cross-user |
| `test_security_middleware.py` | Headers, body size |
| `test_validation_routes.py` | Validation endpoints |
| `test_contact_intelligence.py` | Person-name guard, promotion |
| `test_http_clients.py` | HTTP client resilience |
| `test_score_version_selection.py` | v1/v2 gating |
| `test_scoring.py` | Score computation |
| `test_upstream_resilience.py` | ORS/Photon/Overpass retry |
| `test_validation_service.py` | Validation engine |

### Notable Test Gaps

1. **No tests for `saved_leads.py`** — 581 lines, 9+ filter params, grouping, today view — untested
2. **No tests for `export.py`** — CSV export with grouped separators untested
3. **No frontend tests** — Zero test files in the frontend
4. **No load/performance tests** — Phase 1 requires p95 ≤ 5s; no harness exists

---

## 7. Security Posture

### What's Done Well ✅

- JWT verification with JWKS cache TTL and issuer validation
- Admin import: email allowlist, path validation, concurrency guard
- Rate limiting on all mutation endpoints
- Request body size limit middleware
- Security headers (backend middleware + Cloudflare `_headers`)
- HMAC secret required in production
- POC mode blocked in production
- DB TLS enforcement with sunset override
- Secret scanning in CI (gitleaks)
- Dependency audit in CI (pip-audit + npm audit)

### Remaining Concerns

1. **CSP still report-only** — `Content-Security-Policy-Report-Only` in `_headers`. Should transition to enforcement before pilot.
2. **No branch protection on `main`** — Direct pushes possible.
3. **`X-Frame-Options: DENY` missing from Cloudflare headers** — Only set in backend middleware (not applicable for Cloudflare-served frontend assets).
4. **Dev JWT bypass** — `should_verify_jwt_signature()` returns `False` when `CLERK_JWKS_URL` is empty (intentional for local dev).

---

## 8. Infrastructure and Platform

### CI/CD (`/.github/workflows/ci.yml`)

| Check | Status |
|-------|--------|
| Gitleaks secret scanning | ✅ |
| Backend tests (`pytest -q`) | ✅ |
| Frontend typecheck (`npm run typecheck`) | ✅ |
| Frontend build (`npm run build`) | ✅ |
| Python dependency audit | ✅ `pip-audit` |
| Node dependency audit | ✅ `npm audit --audit-level=high` |
| Backend compile check | ❌ Not in CI |
| Deploy step | ⚠️ Placeholder echo |

### External Services Not Yet Wired

| Service | Status |
|---------|--------|
| Log forwarding (Render → Logtail) | ❌ |
| Uptime monitoring (UptimeRobot → `/health`) | ❌ |
| Logtail alert rules | ❌ |
| Supabase backup/restore drill | ❌ |
| Branch protection on `main` | ❌ |

---

## 9. MVP Readiness Scorecard

Per the roadmap's consolidated MVP definition:

| MVP Criterion | Status | Confidence |
|---------------|--------|------------|
| Core discovery workflow stable on mobile | ✅ Code complete | 85% |
| Validation signals live in UI | ✅ Feature complete | 85% |
| Follow-up workflow (dates, overdue, urgency) | ✅ Code complete | 90% |
| Per-route + cross-route CSV export | ✅ Both work | 95% |
| Security P0/P1 closed and verified | ⚠️ Code done, platform pending | 70% |
| Evidence committed (Phases 1–4) | ❌ Almost none | 10% |
| Pilot sessions ≥ 3 agents | ❌ Not started | 0% |

### Overall MVP Completion Estimate

| Category | Code | Tests | Evidence | Overall |
|----------|------|-------|----------|---------|
| Backend | 95% | 75% | 15% | 65% |
| Frontend | 88% | 0% | 10% | 50% |
| Infrastructure | 75% | N/A | 20% | 50% |
| Security | 90% | 70% | 30% | 70% |
| **Overall** | **90%** | **50%** | **15%** | **60%** |

---

## 10. Recommended Priority Actions

### Immediate (code fixes)

1. **Fix `main.py` fragile variable reference** — Read CORS config from `get_settings()` inside `_validate_startup_config()`.
2. **Delete `_write_owner_name()` dead code** in `enrichment_service.py`.
3. **Add `groupBy` to `fetchLeads()`** and include `groups` in the response type.
4. **Fix `listSavedLeads()` grouped response type** — return a union or separate function.
5. **Remove `(it as any)` casts** in `SavedLeads.tsx` — use proper `SavedLead` type fields.

### Short-term (close evidence gaps)

6. Capture Phase 1 evidence (ingestion QA, EXPLAIN trace).
7. Capture Phase 5 evidence (10+ validation runs).
8. Capture Phase 3 evidence (5-route scoring, rate measurement).
9. Capture Phase 4 evidence (offline sync, dedup, Today view).

### Medium-term (platform + UI)

10. Wire server-side sorting into `SavedLeads.tsx` (pass `sortBy`/`sortDir` to API).
11. Add Phase 10 filter controls to Saved Leads UI.
12. Add `lat`/`lng` to saved leads response (enables map markers).
13. Add proximity filter stubs (`lat`, `lng`, `radius_m`) to `GET /saved-leads`.
14. Complete Phase 11 Gate 4 (5 polish steps).
15. Connect log forwarding (Render → Logtail).
16. Set up uptime monitoring (UptimeRobot → `/health`).
17. Enable branch protection on `main`.
18. Run backup/restore drill on Supabase.

### Before pilot

19. Transition CSP from report-only to enforcement.
20. Add frontend tests (offline queue, sync, export at minimum).
21. Create Phase 12 evidence template.
22. Add backend compile check to CI pipeline.

---

## Corrections from First Audit Pass

The following findings from the first audit were **incorrect** and have been removed:

| First Audit Finding | Actual Status |
|---------------------|---------------|
| `validation_state` never populated in saved leads | ✅ **Fixed** — joins validation tables, computes via `_overall_label()` |
| Phase 10 params missing from `listSavedLeads()` frontend | ✅ **Fixed** — all 14 params wired |
| No automated employee count extraction | ✅ **Fixed** — `_extract_employee_count_from_html()` → `promote_employee_count()` in `validation_service.py` |
| Owner name validation not wired | ✅ **Fixed** — `_extract_owner_from_html()` → `promote_owner_name()` in `validation_service.py` |
| OSM operator tag not extracted | ✅ **Fixed** — `osm_enrichment_service.py` extracts with person-name guard |
| No `validation_state` on frontend type | ✅ **Fixed** — `SavedLead` type has `validation_state?: string | null` |

These were likely fixed between the first audit pass and this re-audit.

---

## Appendix: Files Audited

### Backend Core
- `app/main.py`, `app/core/config.py`, `app/core/auth.py`, `app/core/errors.py`
- `app/db/session.py`, `app/db/base.py`

### Backend Models (all 13)
- `business.py`, `saved_lead.py`, `route.py`, `route_candidate.py`, `note.py`, `user.py`
- `lead_score.py`, `lead_validation_run.py`, `lead_field_validation.py`
- `lead_expansion_candidate.py`, `business_contact_candidate.py`, `scoring_feedback_prior.py`, `import_job.py`

### Backend Schemas (all 8)
- `lead.py`, `saved_lead.py`, `route.py`, `note.py`, `geocode.py`, `validation.py`, `import_job.py`, `common.py`

### Backend API Routes (all 11)
- `leads.py`, `saved_leads.py`, `routes.py`, `export.py`, `notes.py`, `geocode.py`
- `validation.py`, `enrichment.py`, `admin_import.py`, `businesses.py`, `health.py`

### Backend Services (all 11)
- `lead_service.py`, `scoring_service.py`, `classification_service.py`, `validation_service.py`
- `routing_service.py`, `geocode_service.py`, `osm_enrichment_service.py`, `enrichment_service.py`
- `contact_intelligence.py`, `scoring_feedback_service.py`, `business_search_service.py`

### Backend Utils & Tests
- `utils/geo.py`, `utils/http_clients.py`, `utils/rate_limit.py`, `utils/redis_client.py`
- All 11 test files

### Frontend (all files)
- `pages/App.tsx`
- `components/LeadList.tsx`, `LeadDetail.tsx`, `MapPanel.tsx`, `RouteForm.tsx`, `SavedLeads.tsx`, `TodayDashboard.tsx`, `ToastContainer.tsx`
- `api/client.ts`
- `lib/toast.ts`, `leadCache.ts`, `offlineQueue.ts`, `savedLeadCache.ts`
- `styles/app.css`
- `vite.config.ts`

### Infrastructure
- `.github/workflows/ci.yml`, `.github/workflows/ingest_overture.yml`
- `frontend/public/_headers`
- `infra/docker-compose.yml`, `infra/validation-cron.js`, `infra/geocode-worker.js`
- `infra/wrangler.toml`, `infra/wrangler.validation-cron.toml`

### Migrations
- `alembic/versions/0001` through `0009`

### Scripts
- `scripts/backfill_classification.py`, `compare_scoring_versions.py`, `explain_candidate_query.py`
- `scripts/ingest_overture.py`, `recompute_scoring_priors.py`, `validate_scoring.py`

---

*End of audit report v2.*

---

## Addendum: Claude Code Verification of v2 Audit (April 20, 2026)

**Reviewer:** Claude Code (claude-sonnet-4-6)
**Method:** Direct file reads and grep cross-checks against every claim in v2.

---

### Corrections to the v2 Audit

#### §2D — "Phase 12 Evidence Template Missing": **Wrong**

The audit states `docs/evidence/phase12_owner_employee_template.md` "has not been created." It exists:

```
docs/evidence/phase12_owner_employee_template.md   ✅
```

`ls docs/evidence/` lists it alongside `gate_closeout_2026-04-19.md`, `phase1_*`, `phase2_*`, `phase7_*`, and `session_roadmap_closure_2026-04-19.md`. The v2 audit's §2D and the checklist entry in §4/Phase 12 (`❌ Not created`) are both wrong and should be struck.

#### §7 — "X-Frame-Options: DENY missing from Cloudflare headers": **Partially wrong**

The audit says `X-Frame-Options: DENY` is absent from Cloudflare-served frontend assets. This is technically true — `frontend/public/_headers` does not include it. However, the CSP in that same file already includes `frame-ancestors 'none'` in the `Content-Security-Policy-Report-Only` directive. Modern browsers honor `frame-ancestors` over `X-Frame-Options`; the two are functionally equivalent for this purpose. The real issue is that CSP is still report-only. Once CSP is enforced (Priority Action 19), the framing protection will be active for frontend assets. The audit's framing of this as a standalone gap is misleading.

#### §1C — "`fetchLeads()` frontend missing `group_by` param": **Confirmed, with more detail**

The audit is correct. But it understates the gap. The backend `GET /routes/{id}/leads` has three additional params that `fetchLeads()` also doesn't send:

- `min_validation_confidence` (float filter on lead quality)
- `validation_state` (filter by overall label e.g. "Validated")
- `operating_status` (filter by business status)

Additionally, the `fetchLeads()` return type is `{ route_id, leads, total, filtered }` — it omits the `groups` field that the backend includes in `LeadsResponse.groups` when `group_by` is set. The frontend `Lead` type also doesn't include `employee_count_confidence` (the backend `LeadItem` schema does, at `lead.py` line 36).

Wait — re-checking `client.ts` line 101: `employee_count_confidence: number | null` is present. That's fine. The missing params are `min_validation_confidence`, `validation_state`, `operating_status`, `groupBy`, and `groups` in the response type.

#### §1F — "Client-side sorting in `SavedLeads.tsx`": **Confirmed but nuanced**

The `SortMode` type in `SavedLeads.tsx` is `"due_date" | "status" | "score" | "name" | "saved_date"`. The `saved_date` sort uses `b.id > a.id` comparison (UUID lexicographic order), which is unreliable — UUIDs v4 are random, not time-ordered. The correct approach would be to pass `sort_by=saved_at` to the backend, which sorts on `SavedLead.created_at`. The v2 audit noted client-side sorting but missed this specific `saved_date` UUID-sort bug.

Also: the `fetchLeads()` `sortBy` union type is `"score" | "blue_collar_score" | "name" | "distance"` — it's missing `"validation_confidence"` and `"owner_name"`, both of which are valid backend sort modes in `VALID_SORT_BY`. The backend also accepts `"follow_up_date"`, `"last_contact"`, `"saved_at"` for leads (they're shared from `lead_service.VALID_SORT_BY`), though these are less relevant for route leads.

---

### Additional Issues the v2 Audit Missed

#### A. `_write_owner_name()` in `enrichment_service.py` — confirmed dead but `resolved_confidence` import is **not** stranded

The v2 audit (§1B) says "Delete the function and its import of `resolved_confidence` (line 15) if unused elsewhere." This is **wrong about `resolved_confidence`**: `resolved_confidence` is imported from `contact_intelligence` at line 15 of `enrichment_service.py`, but it is only used inside `_write_owner_name()` — it is not called anywhere else in the file. So once `_write_owner_name()` is deleted, the `resolved_confidence` import should also be removed. The audit's phrasing "if unused elsewhere" implies uncertainty; the answer is: it is unused elsewhere in this file and the import should be removed.

#### B. `fetchLeads()` return type hardcodes non-grouped shape

`fetchLeads()` in `client.ts` line 205 returns `req<{ route_id: string; leads: Lead[]; total: number; filtered: number }>`. The backend `LeadsResponse` schema has `groups: list[LeadGroup] | None = None`. Even without `group_by`, the backend will always serialize the `groups` field as `null` in the JSON response. The frontend type simply silently drops it. When `group_by` is eventually added, the response will have `groups` populated but the frontend type won't know about it. Adding `groups?: LeadGroup[]` (where `LeadGroup = { key: string; label: string; count: number; leads: Lead[] }`) to the return type costs nothing now and prevents a silent breakage later.

#### C. `fetchLeads()` `sortBy` union is too narrow

As noted above: `sortBy?: "score" | "blue_collar_score" | "name" | "distance"` is missing `"validation_confidence"` and `"owner_name"` from the backend's `VALID_SORT_BY`. These are Phase 10 additions that were wired on the backend but the frontend type was never updated.

#### D. `VALID_SORT_BY` in `lead_service.py` includes `"follow_up_date"`, `"last_contact"`, `"saved_at"` — not relevant for route leads

This is a pre-existing naming bleed from when `VALID_SORT_BY` was a shared set. These sort modes make no sense for `GET /routes/{id}/leads` (there's no follow-up date or last-contact on a route lead), but they're accepted without error. Not a critical bug, but a code quality note: the leads service and the saved leads route should use distinct sort mode sets. The v2 audit didn't surface this.

#### E. `isFirstRun` prop and `ONBOARDING_KEY` still present in `App.tsx` (Gate 4, step 17)

The v2 audit marks step 17 ("Onboarding replacement: remove modal, `isFirstRun` prop") as Pending. This is confirmed: `App.tsx` lines 128, 174, 336, 508, 577, 596 still reference `ONBOARDING_KEY` and pass `isFirstRun` to three components. The prop exists on `SavedLeads` (line 21), is consumed on line 440, and is passed from `App.tsx` to `SavedLeads`, `LeadDetail`, and another component. The old onboarding modal code appears to have been removed (no `OnboardingModal` component found), but the `isFirstRun` prop machinery and `localStorage` key remain. Step 17 is genuinely incomplete — the prop threads persist.

#### F. `sortSavedLeads()` `saved_date` mode sorts by UUID not timestamp

As noted above: `SavedLeads.tsx` line 51 sorts by `b.id > a.id` (string UUID comparison). UUIDs v4 are random, so this produces arbitrary ordering rather than insertion order. This is a silent correctness bug. The `id` field is `uuid` not `ulid`, so lexicographic comparison is meaningless. Fix: pass `sort_by=saved_at&sort_dir=desc` to the backend API for this mode.

#### G. `_headers` CSP `frame-ancestors 'none'` is in report-only mode — Cloudflare framing not actually enforced

The `frame-ancestors 'none'` directive in `_headers` is inside `Content-Security-Policy-Report-Only`, not `Content-Security-Policy`. Report-only means violations are reported but not blocked. Combined with the absence of `X-Frame-Options`, the Cloudflare-served frontend is technically embeddable in an iframe right now. This is more serious than the v2 audit implied — it's an active gap, not just a missing redundant header.

---

### Summary Table

| v2 Claim | Verdict |
|---|---|
| §2D Phase 12 evidence template missing | **Wrong** — `docs/evidence/phase12_owner_employee_template.md` exists |
| §7 X-Frame-Options missing from Cloudflare | **Partially wrong** — CSP has `frame-ancestors 'none'` but it's report-only, so framing is technically unblocked; real fix is enforcing CSP, not adding `X-Frame-Options` |
| §1C `fetchLeads()` missing `group_by` | **Confirmed** — also missing `min_validation_confidence`, `validation_state`, `operating_status`, and `groups` in response type |
| §1F Client-side sorting | **Confirmed** — also note `saved_date` sort uses UUID comparison (wrong), and `sortBy` union missing `validation_confidence`/`owner_name` |
| §1B `_write_owner_name()` dead code | **Confirmed** — `resolved_confidence` import is also stranded (not "maybe") |

### New Issues Not in v2

| Issue | File | Severity |
|---|---|---|
| `fetchLeads()` response type missing `groups` field | `client.ts` | Low (latent) |
| `fetchLeads()` `sortBy` union missing `validation_confidence`, `owner_name` | `client.ts` | Low |
| `VALID_SORT_BY` in `lead_service.py` includes saved-lead sort modes irrelevant to route leads | `lead_service.py` | Low (code quality) |
| `sortSavedLeads()` `saved_date` mode sorts by random UUID not timestamp | `SavedLeads.tsx` | Medium (silent correctness bug) |
| `isFirstRun` prop threads + `ONBOARDING_KEY` still present despite modal removal | `App.tsx`, `SavedLeads.tsx` | Low (Gate 4 step 17 incomplete) |
| Cloudflare `frame-ancestors 'none'` is report-only — frontend actually embeddable | `_headers` | Medium (active security gap) |