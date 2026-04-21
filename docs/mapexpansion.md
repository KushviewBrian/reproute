# Map Expansion Plan (IN North + Western OH + Southern MI)

Updated: April 20, 2026

## Goal
Expand RepRoute lead coverage from the current metro-scale footprint to a multi-state regional footprint:
- Top half of Indiana
- Western Ohio
- Southern half of Michigan

without destabilizing ingest jobs, Postgres performance, or map UX.

## Executive Summary
The map UI itself is not the primary cost driver. Basemap tiles are fetched on demand, while major usage growth will come from:
- Overture ingest volume
- `business` table growth (including `source_payload_json`)
- Index size and query latency in corridor searches

This plan uses staged regional ingestion, chunked processing, and explicit capacity gates before each expansion step.

## Current Architecture (What Matters For Expansion)
- Basemap:
  - Frontend renders OSM raster tiles by default in [MapPanel.tsx](/Users/brian/reproute/frontend/src/components/MapPanel.tsx).
  - Optional PMTiles mode exists via `VITE_MAP_PMTILES_URL`.
- Lead data:
  - Candidate businesses come from PostGIS `business` records.
  - Corridor search uses `ST_DWithin` around route geometry.
- Ingestion:
  - [scripts/ingest_overture.py](/Users/brian/reproute/scripts/ingest_overture.py) loads Overture places and upserts `business`.
  - Current script materializes full parquet into memory; this is a scaling risk.
- Geocoding:
  - Cached in Redis and Worker KV; not a major expansion blocker.

## Scope Definition
Use explicit bbox-driven waves rather than one giant envelope.

### Proposed Wave Boundaries
1. Wave A: North Indiana only
2. Wave B: Add western Ohio
3. Wave C: Add southern Michigan

Each wave has its own bbox, ingest artifact, metrics, and rollback checkpoint.

## Non-Goals
- No UI redesign
- No scoring model rewrite
- No auth/session changes
- No immediate migration to paid map provider (evaluate after Wave B)

## Delivery Plan

### Phase 0: Preflight Baseline
Capture baseline before any new ingest:
- `business` row count
- `pg_total_relation_size('business')`
- route/leads endpoint p50/p95 latency on representative routes
- ingest runtime for current metro bbox
- failure rates in app logs (4xx/5xx)

Artifacts:
- `docs/evidence/mapexpansion_baseline_<date>.md`

### Phase 1: Ingestion Hardening (Required Before Expansion)
Update ingest to avoid full in-memory dataframe conversion.

Required changes:
1. Stream/chunk parquet processing instead of `fetchdf().to_dict("records")`.
2. Add ingest progress logging every N rows.
3. Add per-batch timing + error counters.
4. Add optional `--max-rows` dry-run mode for safe profiling.
5. Add safety guard on batch size and transaction duration.

Acceptance:
- Can process a large bbox artifact without memory spikes or process crash.
- Runtime logs include progress and throughput.

### Phase 2: Storage Control
Reduce avoidable storage growth while preserving audit value.

Required changes:
1. Add option to store reduced source payload (or strip known large/nonessential nested fields).
2. Keep key fields required for debugging/provenance.
3. Verify index set is sufficient, not excessive.

Acceptance:
- Storage growth per million rows is measured and documented.
- Query performance is unchanged or better.

### Phase 3: Wave A (North Indiana)
1. Ingest Wave A bbox.
2. Run post-ingest QA:
   - row count delta
   - missing field rates
   - stale mark count
3. Run route query performance validation:
   - p50/p95 on 5 representative routes
4. Run frontend smoke:
   - route create
   - leads load
   - map render

Go/No-Go gate:
- No material latency regression beyond threshold
- No ingest instability
- No sustained error spike

### Phase 4: Wave B (Western Ohio)
Repeat Wave A process with new bbox. Only proceed if Wave A gate passed.

### Phase 5: Wave C (Southern Michigan)
Repeat Wave A process with new bbox. Only proceed if Wave B gate passed.

### Phase 6: Post-Expansion Optimization
After all waves:
1. Reassess basemap strategy:
   - keep OSM raster fallback, or
   - move to PMTiles/self-hosted vector tiles for predictable usage
2. Reassess table partitioning/archival strategy if size warrants it.
3. Update roadmap status + capacity guidance docs.

## Capacity + Usage Risk Model

### Primary Cost Drivers
1. Postgres storage
2. Postgres CPU for corridor queries and upserts
3. Ingest compute/runtime

### Secondary Cost Drivers
1. Basemap tile requests (depends on active usage, not dataset size directly)
2. Geocode upstream usage (partially mitigated by cache)

### Practical Rule
Treat expansion as a DB/ingest scaling problem first, map tile problem second.

## Performance Guardrails

### Query Performance SLO
- `GET /routes/{id}/leads`:
  - p50: non-regressing
  - p95: non-regressing beyond agreed threshold (define exact value in baseline artifact)

### Ingest SLO
- No OOM or crash for any wave bbox ingest.
- Throughput logged and stable.

### App Stability
- No new sustained 5xx spike post-wave.

## Test Plan

### Backend
1. Ingest chunking unit/integration tests
2. Upsert correctness tests (conflict update behavior unchanged)
3. Stale marker behavior unchanged
4. Route candidate query performance check with EXPLAIN artifacts

### Frontend
1. Map renders and lead points load on routes across new geographies
2. Selection, detail panel, saved lead flows unchanged

### Operational
1. End-to-end runbook test per wave:
   - ingest
   - validate
   - rollback drill

## Rollback Plan
Per-wave rollback must be possible without global data reset.

Minimum rollback capability:
1. Tag ingested records by wave label/source marker.
2. Delete or soft-disable wave-specific rows if gate fails.
3. Restore previous performance baseline.

## Observability and Evidence
Create wave-specific evidence artifacts:
- `docs/evidence/mapexpansion_waveA_<date>.md`
- `docs/evidence/mapexpansion_waveB_<date>.md`
- `docs/evidence/mapexpansion_waveC_<date>.md`

Each artifact must include:
- bbox used
- rows ingested
- runtime
- DB size before/after
- query latency before/after
- decision: proceed/hold

## Implementation Checklist

### Pre-Expansion
- [ ] Baseline artifact committed
- [ ] Ingest chunking implemented
- [ ] Storage control approach implemented
- [ ] Dry-run test executed

### Wave A
- [ ] Ingest complete
- [ ] QA metrics recorded
- [ ] Performance gate passed
- [ ] Rollback drill completed

### Wave B
- [ ] Ingest complete
- [ ] QA metrics recorded
- [ ] Performance gate passed
- [ ] Rollback drill completed

### Wave C
- [ ] Ingest complete
- [ ] QA metrics recorded
- [ ] Performance gate passed
- [ ] Rollback drill completed

### Finalization
- [ ] Post-expansion optimization decisions recorded
- [ ] Roadmap updated
- [ ] Runbook updated

## Immediate Next Actions
1. Implement ingest chunking in `scripts/ingest_overture.py`.
2. Create baseline evidence artifact with current production-like metrics.
3. Define exact Wave A bbox and run a small dry-run ingest.
4. Execute Wave A only after preflight gates pass.
