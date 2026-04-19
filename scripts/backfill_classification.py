#!/usr/bin/env python3
from __future__ import annotations

import argparse

from sqlalchemy import create_engine, select, text

from backend.app.services.classification_service import classify


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill insurance_class from categories")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--batch-size", type=int, default=5000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = create_engine(args.database_url)

    fetch_sql = text(
        """
        SELECT id, name, category_primary, category_secondary, source_payload_json
        FROM business
        ORDER BY created_at ASC
        """
    )

    update_sql = text("UPDATE business SET insurance_class = :insurance_class, is_blue_collar = :is_blue_collar, updated_at = now() WHERE id = :id")

    with engine.begin() as conn:
        rows = conn.execute(fetch_sql).mappings().all()
        updates = []
        for row in rows:
            source_payload = row["source_payload_json"] or {}
            taxonomy = source_payload.get("taxonomy") if isinstance(source_payload, dict) else {}
            hierarchy = taxonomy.get("hierarchy", []) if isinstance(taxonomy, dict) else []
            insurance_class, is_blue_collar = classify(row["category_primary"], hierarchy, row["name"])
            updates.append({"id": str(row["id"]), "insurance_class": insurance_class, "is_blue_collar": is_blue_collar})

            if len(updates) >= args.batch_size:
                conn.execute(update_sql, updates)
                print(f"updated={len(updates)}")
                updates = []

        if updates:
            conn.execute(update_sql, updates)
            print(f"updated={len(updates)}")


if __name__ == "__main__":
    main()
