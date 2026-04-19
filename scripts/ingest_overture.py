#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from shapely import wkb
from sqlalchemy import create_engine, text

from backend.app.services.classification_service import classify


def _json_default(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    if hasattr(value, "tolist"):
        return value.tolist()
    return str(value)


def _json_clean(value):
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: _json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_clean(v) for v in value]
    if hasattr(value, "tolist"):
        return _json_clean(value.tolist())
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    return value


def _to_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if hasattr(value, "tolist"):
        converted = value.tolist()
        if isinstance(converted, list):
            return converted
        return [converted]
    return [value]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Overture places parquet into PostGIS")
    parser.add_argument("--parquet", help="Path to Overture GeoParquet file")
    parser.add_argument("--bbox", help="Bounding box as minLng,minLat,maxLng,maxLat")
    parser.add_argument("--label", default="metro", help="Label used when downloading by bbox")
    parser.add_argument("--database-url", required=True, help="Sync postgres URL")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    if not args.parquet and not args.bbox:
        parser.error("Either --parquet or --bbox is required")
    return args


def _extract_point(geometry: object) -> tuple[float | None, float | None]:
    lng = None
    lat = None
    if isinstance(geometry, dict):
        coords = geometry.get("coordinates")
        if coords and len(coords) >= 2:
            lng = float(coords[0])
            lat = float(coords[1])
    elif isinstance(geometry, (bytes, bytearray, memoryview)):
        point = wkb.loads(bytes(geometry))
        if getattr(point, "geom_type", None) == "Point":
            lng = float(point.x)
            lat = float(point.y)
    return lng, lat


def _download_by_bbox(bbox: str, label: str) -> str:
    out_dir = Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{label.replace(' ', '_').lower()}_places.parquet"
    cmd = [
        "overturemaps",
        "download",
        f"--bbox={bbox}",
        "--type=place",
        "-f=geoparquet",
        f"-o={output}",
    ]
    print(f"running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "overturemaps download failed.\n"
            f"stdout:\n{proc.stdout[-2000:]}\n"
            f"stderr:\n{proc.stderr[-2000:]}"
        )
    return str(output)


def normalize_row(row: dict) -> dict | None:
    names = row.get("names") or {}
    name = names.get("primary") if isinstance(names, dict) else None
    if not name:
        return None

    lng, lat = _extract_point(row.get("geometry"))
    if lng is None or lat is None:
        return None

    operating_status = row.get("operating_status")
    if operating_status == "permanently_closed":
        return None

    addresses = _to_list(row.get("addresses"))
    addr0 = addresses[0] if addresses else {}
    phones = _to_list(row.get("phones"))
    websites = _to_list(row.get("websites"))
    taxonomy = row.get("taxonomy") or {}
    hierarchy = taxonomy.get("hierarchy") if isinstance(taxonomy, dict) else None

    insurance_class, is_blue_collar = classify(
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
        "lng": lng,
        "lat": lat,
        "is_blue_collar": is_blue_collar,
        "has_phone": bool(phones),
        "has_website": bool(websites),
        "has_address": bool(addr0),
        "source_payload_json": json.dumps(_json_clean(row), default=_json_default, allow_nan=False),
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }


def upsert_batch(engine, rows: list[dict]) -> None:
    sql = text(
        """
        INSERT INTO business (
          id, external_source, external_id, name, category_primary, category_secondary,
          insurance_class, is_blue_collar, address_line1, city, state, postal_code, phone, website,
          operating_status, confidence_score, geom, has_phone, has_website, has_address,
          source_payload_json, last_seen_at
        ) VALUES (
          :id, :external_source, :external_id, :name, :category_primary, :category_secondary,
          :insurance_class, :is_blue_collar, :address_line1, :city, :state, :postal_code, :phone, :website,
          :operating_status, :confidence_score, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
          :has_phone, :has_website, :has_address, CAST(:source_payload_json AS jsonb), :last_seen_at
        )
        ON CONFLICT (external_source, external_id) DO UPDATE SET
          name = EXCLUDED.name,
          category_primary = EXCLUDED.category_primary,
          category_secondary = EXCLUDED.category_secondary,
          insurance_class = EXCLUDED.insurance_class,
          is_blue_collar = EXCLUDED.is_blue_collar,
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


def mark_stale_overture_records(engine, refresh_started_at: datetime) -> int:
    sql = text(
        """
        UPDATE business
        SET
          operating_status = 'possibly_closed',
          updated_at = now()
        WHERE external_source = 'overture'
          AND last_seen_at IS NOT NULL
          AND last_seen_at < :refresh_started_at
          AND COALESCE(operating_status, '') <> 'possibly_closed'
        """
    )
    with engine.begin() as conn:
        result = conn.execute(sql, {"refresh_started_at": refresh_started_at})
    return int(result.rowcount or 0)


def main() -> None:
    args = parse_args()
    refresh_started_at = datetime.now(timezone.utc)
    parquet_path = args.parquet or _download_by_bbox(args.bbox, args.label)
    print(f"loading parquet={parquet_path}")

    conn = duckdb.connect()
    rows = conn.execute(f"SELECT * FROM read_parquet('{parquet_path}')").fetchdf().to_dict("records")

    engine = create_engine(args.database_url)

    batch: list[dict] = []
    processed = 0
    upserted = 0
    missing_name = 0
    missing_geometry = 0
    missing_basic_category = 0
    with_phone = 0
    with_website = 0
    status_open = 0
    permanently_closed = 0

    for raw in rows:
        processed += 1

        names = raw.get("names") or {}
        name = names.get("primary") if isinstance(names, dict) else None
        if not name:
            missing_name += 1

        lng, lat = _extract_point(raw.get("geometry"))
        if lng is None or lat is None:
            missing_geometry += 1

        if not raw.get("basic_category"):
            missing_basic_category += 1

        phones = _to_list(raw.get("phones"))
        websites = _to_list(raw.get("websites"))
        if phones:
            with_phone += 1
        if websites:
            with_website += 1
        if raw.get("operating_status") == "open":
            status_open += 1
        if raw.get("operating_status") == "permanently_closed":
            permanently_closed += 1

        normalized = normalize_row(raw)
        if not normalized:
            continue
        batch.append(normalized)

        if len(batch) >= args.batch_size:
            upsert_batch(engine, batch)
            upserted += len(batch)
            batch = []
        if processed % 10000 == 0:
            print(f"processed={processed} upserted={upserted}")

    if batch:
        upsert_batch(engine, batch)
        upserted += len(batch)
    stale_marked = mark_stale_overture_records(engine, refresh_started_at)
    print(
        f"stale_record_update refresh_started_at={refresh_started_at.isoformat()} "
        f"stale_marked={stale_marked}"
    )

    def pct(value: int) -> float:
        if processed == 0:
            return 0.0
        return round((value / processed) * 100.0, 2)

    print(
        "done "
        f"processed={processed} upserted={upserted} "
        f"missing_name_rate={pct(missing_name)}% "
        f"missing_geometry_rate={pct(missing_geometry)}% "
        f"missing_basic_category_rate={pct(missing_basic_category)}% "
        f"with_phone_rate={pct(with_phone)}% "
        f"with_website_rate={pct(with_website)}% "
        f"open_rate={pct(status_open)}% "
        f"permanently_closed_rate={pct(permanently_closed)}% "
        f"stale_marked={stale_marked}"
    )


if __name__ == "__main__":
    main()
