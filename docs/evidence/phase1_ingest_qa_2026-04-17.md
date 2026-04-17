# Phase 1 Ingestion QA Artifact

Date: 2026-04-17
Script: `python scripts/ingest_overture.py --parquet data/indianapolis_places.parquet --database-url "$INGEST_DATABASE_URL"`

Status: Pending execution in an environment with Postgres connectivity.

Reason: local environment does not include Docker/DB runtime (`docker` unavailable), so metrics could not be captured safely in this workspace.

Expected metrics to record after execution:
- processed / upserted row counts
- missing_name_rate
- missing_geometry_rate
- missing_basic_category_rate
- with_phone_rate
- with_website_rate
- open_rate
- permanently_closed_rate
- stale_marked
