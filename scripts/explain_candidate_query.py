#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EXPLAIN ANALYZE for route candidate query")
    parser.add_argument("--database-url", required=True, help="Sync postgres URL")
    parser.add_argument("--route-id", required=True, help="Route UUID to analyze")
    parser.add_argument("--corridor-width-meters", type=int, default=1609)
    parser.add_argument("--output", help="Optional output file path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = create_engine(args.database_url)

    explain_sql = text(
        """
        EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
        SELECT
          b.id,
          ST_Distance(b.geom::geography, r.route_geom::geography) AS distance_from_route_m
        FROM business b
        CROSS JOIN route r
        WHERE r.id = :route_id
          AND COALESCE(b.insurance_class, '') != 'Exclude'
          AND ST_DWithin(b.geom::geography, r.route_geom::geography, :corridor_width_meters)
        ORDER BY distance_from_route_m ASC
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(
            explain_sql,
            {
                "route_id": args.route_id,
                "corridor_width_meters": args.corridor_width_meters,
            },
        ).all()

    plan_lines = [row[0] for row in rows]
    plan_text = "\n".join(plan_lines)
    print(plan_text)

    uses_index = ("Index Scan" in plan_text) or ("Bitmap Index Scan" in plan_text)
    print(f"\nindex_used={uses_index}")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(plan_text + f"\n\nindex_used={uses_index}\n", encoding="utf-8")
        print(f"wrote {output_path}")


if __name__ == "__main__":
    main()

