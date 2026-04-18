# Phase 1-4 Validation Playbook

This runbook captures repeatable checks for the remaining evidence-heavy items in Phases 1-4.

## Latest Evidence Snapshot (2026-04-17)

- Ingestion QA artifact: `docs/evidence/phase1_ingest_qa_2026-04-17.md`
- EXPLAIN ANALYZE artifact: `docs/evidence/phase1_explain_route_pending_2026-04-17.txt` (to be replaced with route-specific trace file before phase close)
- Route IDs and p95 timing:
  - Route IDs: pending production capture (`validate_scoring.py` now supports output artifact with per-route metrics and `other_unknown_rate`)
  - p95 capture: pending production capture

## Gate 1 Security Verification Checklist (2026-04-17)

- [ ] Production startup fails when DB TLS is insecure and emergency override is disabled.
- [ ] Emergency override path verified with sunset guard.
- [ ] Invalid signature / wrong issuer / expired token tests green.
- [ ] Cross-user access denial tests green for routes, saved leads, notes, export.
- [ ] CI security scanners green (gitleaks + pip-audit + npm audit).

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
