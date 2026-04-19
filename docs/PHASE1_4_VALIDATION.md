# Phase 1-4 Validation Playbook

This runbook captures repeatable checks for the remaining evidence-heavy items in Phases 1-4.

## Reliability Execution Rules (Gate Policy)

- Every PR merged to `main` must include:
  - linked roadmap line item
  - test evidence summary
  - rollback note
- No gate is marked complete without committed artifact proof.
- Evidence entries must include:
  - command(s) executed
  - timestamp (UTC)
  - commit SHA
  - CI run URL (if applicable)
  - pass/fail outcome

## Gate Tracker (Apr 20, 2026 → May 1, 2026)

### Gate 0 — Stabilization Baseline + Merge Controls

- [ ] Branch protection + required checks policy verified and documented.
- [x] Production env contract documented (`docs/DEPLOYMENT_GUIDE.md`, `docs/REQUIRED_SECRETS.md`).
- [x] Post-deploy `/health` + core flow smoke checklist documented.

Evidence links:
- Commit(s): `TODO`
- CI run(s): `TODO`
- Notes: `TODO`

## Session Update (2026-04-19)

- Added app-level offline queue flush orchestration and queue-count refresh events:
  - `frontend/src/pages/App.tsx`
  - `frontend/src/lib/offlineQueue.ts`
  - `frontend/src/components/SavedLeads.tsx`
  - `frontend/src/components/LeadDetail.tsx`
- Re-baselined roadmap consistency:
  - Phase 6 status now matches implemented state in `docs/roadmap.md`
  - Immediate next sprint item updated to evidence-first closeout work
- Recorded evidence and blockers in:
  - `docs/evidence/session_roadmap_closure_2026-04-19.md`
  - `docs/evidence/gate_closeout_2026-04-19.md`
  - `docs/evidence/phase2_security_signoff_2026-04-19.md`

Blocked (remaining after this session):
- `INGEST_DATABASE_URL` not configured locally, so ingestion QA command was not executed to avoid writes against unknown DB target.
- Scoring/validation runtime evidence requires staging bearer token and route IDs (not available in local env files).
- CI-linked evidence URLs are still open for this session.

## Latest Evidence Snapshot (2026-04-17)

- Ingestion QA artifact: `docs/evidence/phase1_ingest_qa_2026-04-17.md`
- EXPLAIN ANALYZE artifact: `docs/evidence/phase1_explain_route_pending_2026-04-17.txt` (to be replaced with route-specific trace file before phase close)
- Route IDs and p95 timing:
  - Route IDs: pending production capture (`validate_scoring.py` now supports output artifact with per-route metrics and `other_unknown_rate`)
  - p95 capture: pending production capture

## Gate 1 Security Verification Checklist (updated 2026-04-19)

- [x] Production startup fails when DB TLS is insecure and emergency override is disabled.
- [x] Emergency override path verified with sunset guard.
- [x] Invalid signature / wrong issuer / expired token tests green.
- [x] Cross-user access denial tests green for routes, saved leads, notes, export.
- [ ] CI security scanners green (gitleaks + pip-audit + npm audit).
- [x] Admin import allowlist/path/concurrency protections verified.
- [x] Validation admin HMAC enforcement verified (`/admin/validation/run-due`).
- [ ] Production smoke passes under Supabase pooler (route create, lead fetch, today view, exports).

Evidence links:
- Commit(s): `7944b29` (baseline for verification session)
- CI run(s): `n/a in this local/staging session`
- Notes:
  - Security suite result: `58 passed`
  - Scanner rerun result: `pip-audit` clean, `gitleaks` clean, `npm audit --audit-level=high` pass (moderate-only findings)
  - Staging smoke: `/health` 200; `/admin/validation/run-due` rejects missing/invalid HMAC; protected endpoints reject missing bearer token
  - Full evidence package: `docs/evidence/phase2_security_signoff_2026-04-19.md`

## Gate 2 Evidence Checklist (Phase 1 + Phase 3/4)

- [ ] Replace EXPLAIN placeholder with route-specific artifact.
- [ ] Ingestion QA artifact includes required metrics and p95 context.
- [ ] 5-route scoring validation artifact committed with `other_unknown_rate`.
- [ ] Offline reconnect no-loss verification documented (notes + status).
- [ ] Dedup spot-check evidence documented.
- [ ] Today dashboard section correctness evidence documented.

### Phase 4 Code Tasks — Completed 2026-04-19

- [x] 401/429/network errors produce actionable human-readable messages on all mutation surfaces
  (`toUserMessage` helper wired into `App.tsx` — `onCreated`, `onSaveLead`, `onSaveLeadWithNote`, `onApplyFilters`, `onCorridorChange`).
- [x] Geocode failure shows actionable copy: "Couldn't find X — try adding a city or zip code."
- [x] GPS denial distinguishes permission-denied vs. unavailable with separate copy.
- [x] Route submit catch passes geocode errors through cleanly (401/429 still mapped).

### Phase 7 Code Tasks — Completed 2026-04-19

- [x] ORS upstream: retry up to 2 attempts with 1s delay; graceful degraded straight-line fallback on
  exhaustion. `properties.degraded=True` set on fallback features. 18 new unit tests green.
- [x] Geocode upstream: retry up to 2 attempts with 0.5s delay; POC fallback on exhaustion.
  Failure taxonomy: timeout/ConnectError/5xx → retry; 4xx → terminal.
- [x] Audit middleware: `duration_ms` now included in every `audit_event` log line for p95 tracking.

Evidence links:
- Commit(s): `TODO`
- CI run(s): `TODO`
- Notes: `TODO`

## Per-PR Evidence Template

```
Date (UTC):
PR/Commit:
Roadmap line item:

Commands run:
- ...

Results:
- ...

Rollback note:
- ...

Linked artifacts:
- ...
```

## 1) Spatial index evidence (`EXPLAIN ANALYZE`)

Run:

```bash
python scripts/explain_candidate_query.py \
  --database-url "$INGEST_DATABASE_URL" \
  --route-id "<route_uuid>" \
  --corridor-width-meters 1609 \
  --output docs/evidence/phase1_explain_route_<route_uuid>.txt
```

Expected:

- Plan includes `Index Scan` or `Bitmap Index Scan` on route/business geometry paths.
- Output file is committed under `docs/evidence/` for traceability.

## 2) Ingestion QA metrics

Run:

```bash
python scripts/ingest_overture.py \
  --bbox="-86.35,39.65,-85.95,39.95" \
  --label="indianapolis" \
  --database-url "$INGEST_DATABASE_URL"
```

Or with an existing parquet:

```bash
python scripts/ingest_overture.py \
  --parquet data/indianapolis_places.parquet \
  --database-url "$INGEST_DATABASE_URL"
```

Expected terminal summary includes:

- `missing_name_rate`
- `missing_geometry_rate`
- `missing_basic_category_rate`
- `with_phone_rate`
- `with_website_rate`
- `open_rate`

## 3) Scoring validation harness

Run on 5 real route IDs:

```bash
python scripts/validate_scoring.py \
  --api-base-url "https://<backend-host>" \
  --token "<clerk_jwt>" \
  --route-id "<route_1>" \
  --route-id "<route_2>" \
  --route-id "<route_3>" \
  --route-id "<route_4>" \
  --route-id "<route_5>" \
  --output docs/evidence/phase3_scoring_validation_<date>.txt
```

Expected:

- Each route prints `latency_ms`, `avg_score`, and `excluded_in_top`.
- Summary prints `other_unknown_rate` for phase threshold tracking.
- Use these outputs as the baseline before pilot hardening.

## 4) Manual UI checks (Phase 3-4)

- Route entry: geocode + "Use my location" resolves to a label.
- Discovery: filter and sort update lead list without full page reload.
- Lead detail: notes support `outcome_status` + `next_action`.
- Saved tab:
  - status-priority ordering
  - note preview visible
  - cached fallback works offline
- Export CSV works for current route and `saved_only=true`.
