# Phase 1-4 Validation Playbook

This runbook captures repeatable checks for the remaining evidence-heavy items in Phases 1-4.

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
  --route-id "<route_5>"
```

Expected:

- Each route prints `latency_ms`, `avg_score`, and `excluded_in_top`.
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

