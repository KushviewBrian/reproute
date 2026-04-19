#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text


def _to_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recompute scoring feedback priors from existing outcomes")
    parser.add_argument("--database-url", required=True, help="Database URL (asyncpg or psycopg)")
    parser.add_argument("--calibration-version", default="v2-default")
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--output", help="Optional output path for JSON summary")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = create_engine(_to_sync_url(args.database_url))

    recompute_sql = text(
        """
        WITH base AS (
          SELECT
            ls.route_id,
            ls.business_id,
            COALESCE(NULLIF(lower(trim(b.state)), ''), 'unknown') AS geo_key,
            b.insurance_class,
            COALESCE(b.has_phone, false) AS has_phone,
            COALESCE(b.has_website, false) AS has_website,
            CASE
              WHEN rc.distance_from_route_m <= 750 THEN 'near'
              WHEN rc.distance_from_route_m <= 1500 THEN 'mid'
              ELSE 'far'
            END AS distance_band,
            CASE WHEN EXISTS (
              SELECT 1 FROM saved_lead sl
              WHERE sl.business_id = ls.business_id
            ) THEN 1 ELSE 0 END AS was_saved,
            CASE WHEN (
              EXISTS (
                SELECT 1 FROM saved_lead sl
                WHERE sl.business_id = ls.business_id
                  AND sl.status IN ('called', 'visited', 'follow_up')
              )
              OR EXISTS (
                SELECT 1 FROM note n
                WHERE n.business_id = ls.business_id
                  AND COALESCE(n.outcome_status, '') IN ('called', 'visited', 'follow_up')
              )
            ) THEN 1 ELSE 0 END AS was_contacted
          FROM lead_score ls
          JOIN route_candidate rc
            ON rc.route_id = ls.route_id
           AND rc.business_id = ls.business_id
          JOIN business b
            ON b.id = ls.business_id
          WHERE ls.created_at >= (now() - make_interval(days => :lookback_days))
        ),
        grouped AS (
          SELECT
            geo_key,
            insurance_class,
            has_phone,
            has_website,
            distance_band,
            COUNT(*)::int AS sample_size,
            SUM(was_saved)::int AS save_count,
            SUM(was_contacted)::int AS contacted_count,
            (SUM(was_saved)::numeric / NULLIF(COUNT(*), 0))::numeric(6,5) AS prior_save,
            (SUM(was_contacted)::numeric / NULLIF(COUNT(*), 0))::numeric(6,5) AS prior_contact
          FROM base
          GROUP BY geo_key, insurance_class, has_phone, has_website, distance_band
        ),
        geo_global_rows AS (
          SELECT
            geo_key,
            NULL::text AS insurance_class,
            NULL::boolean AS has_phone,
            NULL::boolean AS has_website,
            'global'::text AS distance_band,
            COUNT(*)::int AS sample_size,
            SUM(was_saved)::int AS save_count,
            SUM(was_contacted)::int AS contacted_count,
            (SUM(was_saved)::numeric / NULLIF(COUNT(*), 0))::numeric(6,5) AS prior_save,
            (SUM(was_contacted)::numeric / NULLIF(COUNT(*), 0))::numeric(6,5) AS prior_contact
          FROM base
          GROUP BY geo_key
        ),
        all_global_row AS (
          SELECT
            'global'::text AS geo_key,
            NULL::text AS insurance_class,
            NULL::boolean AS has_phone,
            NULL::boolean AS has_website,
            'global'::text AS distance_band,
            COUNT(*)::int AS sample_size,
            SUM(was_saved)::int AS save_count,
            SUM(was_contacted)::int AS contacted_count,
            (SUM(was_saved)::numeric / NULLIF(COUNT(*), 0))::numeric(6,5) AS prior_save,
            (SUM(was_contacted)::numeric / NULLIF(COUNT(*), 0))::numeric(6,5) AS prior_contact
          FROM base
        )
        SELECT * FROM grouped
        UNION ALL
        SELECT * FROM geo_global_rows
        UNION ALL
        SELECT * FROM all_global_row
        """
    )

    insert_sql = text(
        """
        INSERT INTO scoring_feedback_prior (
          id,
          calibration_version,
          geo_key,
          insurance_class,
          has_phone,
          has_website,
          distance_band,
          sample_size,
          save_count,
          contacted_count,
          prior_save,
          prior_contact
        ) VALUES (
          :id,
          :calibration_version,
          :geo_key,
          :insurance_class,
          :has_phone,
          :has_website,
          :distance_band,
          :sample_size,
          :save_count,
          :contacted_count,
          :prior_save,
          :prior_contact
        )
        """
    )

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM scoring_feedback_prior WHERE calibration_version = :calibration_version"),
            {"calibration_version": args.calibration_version},
        )

        rows = conn.execute(recompute_sql, {"lookback_days": args.lookback_days}).mappings().all()
        if not rows:
            raise SystemExit("No scoring rows found for lookback window; priors not written.")

        conn.execute(
            insert_sql,
            [
                {
                    "id": str(uuid.uuid4()),
                    "calibration_version": args.calibration_version,
                    "geo_key": row["geo_key"],
                    "insurance_class": row["insurance_class"],
                    "has_phone": row["has_phone"],
                    "has_website": row["has_website"],
                    "distance_band": row["distance_band"],
                    "sample_size": int(row["sample_size"] or 0),
                    "save_count": int(row["save_count"] or 0),
                    "contacted_count": int(row["contacted_count"] or 0),
                    "prior_save": float(row["prior_save"] or 0.0),
                    "prior_contact": float(row["prior_contact"] or 0.0),
                }
                for row in rows
            ],
        )

    global_row = next((row for row in rows if row["distance_band"] == "global" and row["geo_key"] == "global"), None)
    summary = {
        "calibration_version": args.calibration_version,
        "lookback_days": args.lookback_days,
        "segments_written": len([row for row in rows if row["distance_band"] != "global"]),
        "geo_global_rows": len([row for row in rows if row["distance_band"] == "global" and row["geo_key"] != "global"]),
        "global": {
            "sample_size": int(global_row["sample_size"] or 0) if global_row else 0,
            "prior_save": float(global_row["prior_save"] or 0.0) if global_row else 0.0,
            "prior_contact": float(global_row["prior_contact"] or 0.0) if global_row else 0.0,
        },
    }
    print(json.dumps(summary, indent=2))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
