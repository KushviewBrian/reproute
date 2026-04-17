# RepRoute Dataset Expansion Plan

## 1) Objective

Increase lead coverage and quality without breaking free-tier limits or introducing legal/licensing risk.

Success criteria:
- More valid SMB prospects per route
- Fewer missing phone/website/address fields
- No major increase in paid usage during MVP/pilot

---

## 2) Current State

The `business` table is the canonical POI store. Key columns relevant to expansion:

- `external_source` / `external_id` — deduplication key (`uq_business_external` unique constraint)
- `source_payload_json` — full raw payload from source
- `last_seen_at` — set on every upsert; used to detect stale records
- `last_validated_at` — set by the validation system (see `leadvalidationplan.md`)
- `has_phone`, `has_website`, `has_address` — derived boolean flags

The ingest pipeline is `scripts/ingest_overture.py`. It downloads GeoParquet via the `overturemaps` CLI (or accepts a local file path) and upserts using `ON CONFLICT (external_source, external_id) DO UPDATE`. Permanently closed records are skipped at normalization time.

**There is no multi-source merge model yet.** The current architecture assumes one canonical `business` row per `(external_source, external_id)` pair. Secondary source enrichment is implemented as **column-level merge only**: supplemental values from OSM or city data are stored as additional columns on the existing row, not as parallel records. A full multi-record canonical merge pipeline is deferred to Phase 2+.

---

## 3) Expansion Strategy (Free-First)

Use a **layered source model**:

1. **Primary corpus:** Overture Places (monthly full refresh)
2. **Secondary enrichment:** OSM/Overpass tags for selected leads
3. **Tertiary local authority data:** business licenses/registrations (target metro only)

Do not run expensive enrichment over the full corpus.
Only enrich:
- Saved leads
- Top N leads per route (default N=20)

---

## 4) Data Sources and Role

### 4.1 Overture Places (Primary)

Role:
- Base business inventory for all scoring/search.

Cadence:
- Monthly refresh, aligned to Overture release cycle (typically first week of each month).

Mechanism:
- Re-run `scripts/ingest_overture.py --bbox=<LAUNCH_METRO_BBOX> --database-url=<URL>`.
- The script handles download via `overturemaps download`, normalization, and upsert.
- Permanently closed records are skipped during normalization.

Stale record handling (gap — needs implementation):
- Businesses present in DB but absent from a refresh are not currently marked stale.
- Fix: after each full refresh run, execute `UPDATE business SET operating_status = 'possibly_closed' WHERE external_source = 'overture' AND last_seen_at < <refresh_start_time>`.
- Do not hard-delete; mark for manual review or downstream validation.

Why:
- Large global POI coverage
- Open data with well-documented licensing (see §11 for details)
- Already integrated

### 4.2 OSM/Overpass (Selective Enrichment)

Role:
- Fill missing `phone`, `website`, `address` fields on selected leads.
- Add corroboration for confidence scoring.

Cadence:
- On-demand for selected leads only
- Skip re-enrichment if enriched within last 30 days unless `force=true`

Overpass public endpoint limits (must be respected):
- Max 2 simultaneous connections
- Requests should include `[out:json][timeout:25]`
- Do not run bulk queries against the public endpoint; if enrichment volume exceeds ~500 queries/day, run a local Overpass instance via Docker instead.

Example query shape for a single business by coordinates:
```
[out:json][timeout:25];
(
  node(around:50,{lat},{lng})["name"~"{name}",i];
  way(around:50,{lat},{lng})["name"~"{name}",i];
);
out body;
```

Extract: `phone` from `contact:phone` or `phone` tag; `website` from `website` or `contact:website`; `opening_hours` as a supplemental signal.

Constraints:
- No bulk scraping behavior.
- Attribute OSM data per ODbL requirements.

### 4.3 Local Government / Open Data (Target Metro)

Role:
- Improve commercial validity in the launch metro.
- Cross-check business existence and address consistency.

Cadence:
- Monthly or quarterly depending on source update frequency.

Scope:
- Restricted to the launch metro bbox (same `LAUNCH_METRO_BBOX` used for Overture).
- Do not ingest multi-metro government data during pilot.

Why:
- Often higher trust for local business records.
- Strongly improves local precision for the specific geography we're selling into.

---

## 5) Schema Changes Required

### 5.1 Enrichment provenance columns (add to `business`)

To track which fields came from secondary sources and when, add:

```sql
ALTER TABLE business
  ADD COLUMN osm_enriched_at     TIMESTAMPTZ,
  ADD COLUMN osm_phone           TEXT,
  ADD COLUMN osm_website         TEXT,
  ADD COLUMN city_license_verified_at TIMESTAMPTZ;
```

Do not overwrite the Overture-sourced `phone`/`website` columns with OSM values directly — store them separately so the canonical field selection logic can apply the priority order. Merge into the primary column only when Overture has no value.

### 5.2 Canonical field selection priority

When merging values from multiple sources:

1. User-pinned values (always win — requires a `pinned_fields JSONB` column, not yet implemented)
2. City license dataset values (where available)
3. Overture values
4. OSM enrichment values

Timestamp-based override: do **not** implement automatic lower-authority overrides based on recency during MVP. The risk of silently degrading data quality (e.g., an OSM vandal edit overwriting a known-good Overture value) outweighs the benefit until per-field provenance tracking and audit logging are in place. For now, the priority order above is fixed. Revisit after pilot data shows the actual frequency of Overture vs OSM conflicts.

### 5.3 `business_source_record` (Phase 2+, defer for now)

A full multi-source record store with a merge candidate pipeline is appropriate once there are 2+ active enrichment sources with meaningful conflict rates. For MVP, the column-level approach in §5.1 is sufficient and avoids schema complexity.

Do not build `business_source_record`, `business_merge_state`, or `business_match_candidate` tables during Phase A/B. Revisit after pilot data shows actual conflict frequency.

---

## 6) Deduplication

### 6.1 Within-source dedup

Already handled by `ON CONFLICT (external_source, external_id) DO UPDATE` in the ingest script. No additional work needed for same-source duplicates.

### 6.2 Cross-source dedup (for when OSM/city data produces a net-new business row)

If a secondary source introduces a record that isn't already in the `business` table (no Overture match), check for near-duplicate before inserting:

Matching priority:
1. Exact website domain match + within 100m
2. Exact phone match (normalized E.164) + within 100m
3. Name similarity (trigram ≥ 0.85) + address similarity + within 100m

Distance guardrail: 100m in urban areas. Do not relax this for pilot.

If a match is found, enrich the existing row rather than inserting a new one. Log the match for review.

---

## 7) Enrichment Scope and Quotas

To protect free tiers, enforce hard caps. The values below are conservative safety margins — adjust upward once Render and DB usage baselines are established.

Global defaults:
- `MAX_ENRICHMENTS_PER_DAY = 100`
- `MAX_ENRICHMENTS_PER_USER_PER_DAY = 15`
- `MAX_ENRICHMENTS_PER_MONTH = 2000`

These are driven by:
- Overpass public endpoint courtesy limits (~500/day comfortable ceiling)
- Render free-tier CPU headroom for background jobs

Selection policy:
- Always allow saved leads (within cap)
- Route enrichment: top 20 by score
- Skip leads enriched in last 30 days unless `force=true`

Fetch constraints:
- Max 1 outbound lookup per lead per run
- Timeout 5s, retry once on transient failure only

---

## 8) Usage Impact Forecast (Qualitative)

With selective enrichment (saved leads + top 20 per route):

| Service | Impact |
|---|---|
| Supabase/Postgres | Moderate — new columns, more writes per enrichment run |
| Render | Primary impact — CPU/network during enrichment background jobs |
| Upstash Redis | Low — cap counters and queue metadata |
| Cloudflare Pages/R2 | Negligible |
| ORS/Photon | None — dataset expansion is separate from route/geocode volume |

With full-corpus enrichment:
- Render and DB usage will spike heavily and will exceed free plans quickly. Do not do this.

---

## 9) Operational Plan

### Phase A — Foundation (1 week)

Extend existing pipeline, do not replace it.

- Add stale record detection to `scripts/ingest_overture.py` (mark `possibly_closed` after refresh).
- Add `osm_enriched_at`, `osm_phone`, `osm_website` columns to `business` via migration.
- Write Overpass fetch utility: point lookup by lat/lng/name, extract phone/website/opening_hours.
- Add enrichment quota counter (Upstash Redis key `enrich:day:{date}` and `enrich:user:{uid}:{date}`).

Exit criteria:
- Monthly Overture refresh marks stale rows correctly (spot-check 20+ records).
- Overpass fetch utility returns phone or website for ≥ 50% of test leads with known OSM presence.
- Quota counter blocks requests at cap without errors.

### Phase B — Selective Enrichment Runner (1 week)

- Build background job: query top-N unsaved leads per route + all saved leads with missing contact fields.
- Apply freshness skip logic (skip if `osm_enriched_at > now() - 30 days`).
- Column-level merge only: write OSM values to `osm_phone`/`osm_website`; copy into primary `phone`/`website` only when the primary column is null (priority rules from §5.2). No multi-record canonical merge.
- Trigger on: new lead save, route generation (async, not blocking).

Exit criteria:
- Contact field completeness (`has_phone OR has_website`) improves by ≥ 10% for saved leads after one enrichment pass.
- No user-visible latency regression on route load or lead save.
- Daily cap respected — enrichment stops at limit with log entry.

### Phase C — Local Authority Data (1–2 weeks, launch metro only)

- Identify and evaluate the city/county open data source for the launch metro.
- Confirm license permits commercial use before ingesting anything.
- Build one-off normalization script (similar pattern to `ingest_overture.py`).
- Cross-check against existing `business` rows: enrich matches, flag net-new records for review.

Exit criteria:
- At least 100 businesses cross-checked and address accuracy sampled manually.
- No license or attribution issues.

### Phase D — Quality Validation (ongoing)

- Sample 20 top leads per week and measure:
  - Contact field completeness (phone + website)
  - Valid commercial prospect rate (per definition in `mvpoutline.md` §18)
  - Duplicate suppression quality (no obvious same-business duplicates in route output)

Exit criteria:
- Quality metrics improve vs baseline without cost blow-up.

---

## 10) Monitoring and Guardrails

Track daily:
- Enrichment jobs run / succeeded / failed
- Leads enriched
- Daily cap utilization (alert if cap reached before noon)
- Average OSM hit rate (how often Overpass returned usable data)

Alerts:
- Daily enrichment cap reached before noon
- Job failure rate > 10%
- DB write errors or lock contention spikes
- Monthly refresh script fails or produces < expected row count

---

## 11) Licensing and Attribution

Before adding any source:

1. Confirm the license permits your commercial use case.
2. Record the license name, version, and attribution requirements in this document.
3. Track source at field/provenance level where the license requires it.
4. Exclude sources with unclear or restrictive terms.

### 11.1 Overture Places

**Do not assume Overture Places is purely ODbL.** Overture Maps Foundation publishes Places data assembled from multiple contributing sources, each of which may carry its own license terms. As of recent releases:

- Some records originate from OSM (ODbL)
- Some records originate from Meta, Microsoft, and other contributors under their own terms
- The Overture dataset as a whole is distributed under the **CDLA-Permissive-2.0** license (Community Data License Agreement), not ODbL

Key implications:
- CDLA-Permissive-2.0 is permissive — attribution is required but share-alike is not.
- Some source data within the Overture bundle may carry additional per-source terms. Overture publishes a per-record `sources` field in the schema that identifies contributing sources.
- Attribution: the `source_payload_json` column already stores the raw Overture record; the `sources` field within it identifies contributing sources per record.

**Action required before ingesting:**
- Read the current Overture attribution guidance at [overturemaps.org/attribution](https://overturemaps.org/attribution/) — this changes with each release.
- Do not hardcode a single attribution string. Surface attribution per-record using the `sources` field where legally required.
- If in doubt, treat the most restrictive source within a record (typically ODbL-derived OSM content) as the governing license for that record.

### 11.2 OpenStreetMap / Overpass

- License: **ODbL 1.0**
- Attribution required: Yes — "© OpenStreetMap contributors"
- Share-alike applies to derived databases. Storing OSM-derived field values (phone, website) in the `business` table constitutes a derived database under ODbL. Ensure your terms of service and data export paths comply with ODbL share-alike if you expose this data externally.
- Attribution must be visible to end users wherever OSM-derived data is displayed.

### 11.3 Local Government / Open Data

- License varies by jurisdiction. Common licenses: CC BY 4.0, CC0, US Government open data (no copyright).
- Confirm the specific license before ingesting any source.
- Record the license name and attribution text for each city/county source added.

### 11.4 Source table

| Source | License | Attribution required | Share-alike |
|---|---|---|---|
| Overture Places | CDLA-Permissive-2.0 (dataset); individual records may include ODbL-licensed OSM content | Yes — see per-record `sources` field and current Overture attribution guidance | No (CDLA-Permissive); per-record ODbL content: yes |
| OpenStreetMap / Overpass | ODbL 1.0 | Yes — "© OpenStreetMap contributors" | Yes — derived databases |
| Local government open data | Varies | Confirm per source | Varies |

Keep this table updated alongside any new source additions. Re-verify Overture license terms on each major release.

---

## 12) MVP Recommendation

For MVP/pilot, implement only:
- Overture monthly refresh (already working — add stale detection)
- Selective Overpass enrichment for saved leads + top 20 per route
- Column-level provenance (§5.1) for OSM fields
- Within-source dedup (already working via upsert constraint)

Defer:
- Full multi-source record store (`business_source_record` tables)
- Full-corpus enrichment
- Broad multi-metro government dataset ingestion
- Cross-source merge candidate pipeline

This gives maximum quality gain per unit of free-tier usage.
