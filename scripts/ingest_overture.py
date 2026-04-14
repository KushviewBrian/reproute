#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone

import duckdb
from sqlalchemy import create_engine, text

from backend.app.services.classification_service import classify


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Overture places parquet into PostGIS")
    parser.add_argument("--parquet", required=True, help="Path to Overture GeoParquet file")
    parser.add_argument("--database-url", required=True, help="Sync postgres URL")
    parser.add_argument("--batch-size", type=int, default=1000)
    return parser.parse_args()


def normalize_row(row: dict) -> dict | None:
    names = row.get("names") or {}
    name = names.get("primary") if isinstance(names, dict) else None
    if not name:
        return None

    geometry = row.get("geometry")
    if not geometry:
        return None

    coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if not coords or len(coords) < 2:
        return None

    operating_status = row.get("operating_status")
    if operating_status == "permanently_closed":
        return None

    addresses = row.get("addresses") or []
    addr0 = addresses[0] if addresses else {}
    phones = row.get("phones") or []
    websites = row.get("websites") or []
    taxonomy = row.get("taxonomy") or {}
    hierarchy = taxonomy.get("hierarchy") if isinstance(taxonomy, dict) else None

    insurance_class = classify(
        basic_category=row.get("basic_category"),
        taxonomy_hierarchy=hierarchy or [],
        name=name,
    )

    return {
        "id": str(uuid.uuid4()),
        "external_source": "overture",
        "external_id": row.get("id"),
        "name": name,
        "category_primary": row.get("basic_category"),
        "category_secondary": taxonomy.get("primary") if isinstance(taxonomy, dict) else None,
        "insurance_class": insurance_class,
        "address_line1": addr0.get("freeform") if isinstance(addr0, dict) else None,
        "city": addr0.get("locality") if isinstance(addr0, dict) else None,
        "state": addr0.get("region") if isinstance(addr0, dict) else None,
        "postal_code": addr0.get("postcode") if isinstance(addr0, dict) else None,
        "phone": phones[0] if phones else None,
        "website": websites[0] if websites else None,
        "operating_status": operating_status,
        "confidence_score": row.get("confidence"),
        "lng": float(coords[0]),
        "lat": float(coords[1]),
        "has_phone": bool(phones),
        "has_website": bool(websites),
        "has_address": bool(addr0),
        "source_payload_json": json.dumps(row),
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }


def upsert_batch(engine, rows: list[dict]) -> None:
    sql = text(
        """
        INSERT INTO business (
          id, external_source, external_id, name, category_primary, category_secondary,
          insurance_class, address_line1, city, state, postal_code, phone, website,
          operating_status, confidence_score, geom, has_phone, has_website, has_address,
          source_payload_json, last_seen_at
        ) VALUES (
          :id, :external_source, :external_id, :name, :category_primary, :category_secondary,
          :insurance_class, :address_line1, :city, :state, :postal_code, :phone, :website,
          :operating_status, :confidence_score, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
          :has_phone, :has_website, :has_address, CAST(:source_payload_json AS jsonb), :last_seen_at
        )
        ON CONFLICT (external_source, external_id) DO UPDATE SET
          name = EXCLUDED.name,
          category_primary = EXCLUDED.category_primary,
          category_secondary = EXCLUDED.category_secondary,
          insurance_class = EXCLUDED.insurance_class,
          address_line1 = EXCLUDED.address_line1,
          city = EXCLUDED.city,
          state = EXCLUDED.state,
          postal_code = EXCLUDED.postal_code,
          phone = EXCLUDED.phone,
          website = EXCLUDED.website,
          operating_status = EXCLUDED.operating_status,
          confidence_score = EXCLUDED.confidence_score,
          geom = EXCLUDED.geom,
          has_phone = EXCLUDED.has_phone,
          has_website = EXCLUDED.has_website,
          has_address = EXCLUDED.has_address,
          source_payload_json = EXCLUDED.source_payload_json,
          last_seen_at = EXCLUDED.last_seen_at,
          updated_at = now()
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, rows)


def main() -> None:
    args = parse_args()
    conn = duckdb.connect()
    rows = conn.execute(f"SELECT * FROM read_parquet('{args.parquet}')").fetchdf().to_dict("records")

    engine = create_engine(args.database_url)

    batch: list[dict] = []
    processed = 0
    inserted = 0

    for raw in rows:
        processed += 1
        normalized = normalize_row(raw)
        if not normalized:
            continue
        batch.append(normalized)

        if len(batch) >= args.batch_size:
            upsert_batch(engine, batch)
            inserted += len(batch)
            print(f"processed={processed} upserted={inserted}")
            batch = []

    if batch:
        upsert_batch(engine, batch)
        inserted += len(batch)

    print(f"done processed={processed} upserted={inserted}")


if __name__ == "__main__":
    main()
