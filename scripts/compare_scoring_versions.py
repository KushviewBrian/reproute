#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx
from sqlalchemy import bindparam, create_engine, text


def _to_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare lead rankings between v1 and v2 scoring")
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument("--token", required=True, help="Bearer token")
    parser.add_argument("--route-id", action="append", required=True, help="Route UUID (repeat allowed)")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--database-url", help="Optional DB URL for outcome proxy metrics")
    parser.add_argument("--output", help="Optional output file path")
    return parser.parse_args()


def _fetch_route(client: httpx.Client, *, base_url: str, route_id: str, token: str, score_version: str, limit: int) -> dict:
    resp = client.get(
        f"{base_url.rstrip('/')}/routes/{route_id}/leads",
        params={"min_score": 0, "limit": limit, "score_version": score_version},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _outcome_by_business(engine, business_ids: list[str]) -> dict[str, dict[str, int]]:
    if not business_ids:
        return {}
    sql = text(
        """
        SELECT
          b.id::text AS business_id,
          CASE WHEN EXISTS (
            SELECT 1 FROM saved_lead sl WHERE sl.business_id = b.id
          ) THEN 1 ELSE 0 END AS saved,
          CASE WHEN (
            EXISTS (
              SELECT 1 FROM saved_lead sl
              WHERE sl.business_id = b.id
                AND sl.status IN ('called', 'visited', 'follow_up')
            )
            OR EXISTS (
              SELECT 1 FROM note n
              WHERE n.business_id = b.id
                AND COALESCE(n.outcome_status, '') IN ('called', 'visited', 'follow_up')
            )
          ) THEN 1 ELSE 0 END AS contacted
        FROM business b
        WHERE b.id::text IN :business_ids
        """
    ).bindparams(bindparam("business_ids", expanding=True))
    with engine.begin() as conn:
        rows = conn.execute(sql, {"business_ids": business_ids}).mappings().all()
    return {
        row["business_id"]: {
            "saved": int(row["saved"] or 0),
            "contacted": int(row["contacted"] or 0),
        }
        for row in rows
    }


def main() -> None:
    args = parse_args()
    top_k = max(1, min(args.top_k, args.limit))
    lines: list[str] = []
    route_summaries: list[dict] = []
    total_overlap = 0.0
    total_abs_rank_delta = 0.0

    engine = create_engine(_to_sync_url(args.database_url)) if args.database_url else None

    with httpx.Client() as client:
        for route_id in args.route_id:
            t0 = time.perf_counter()
            v1 = _fetch_route(
                client,
                base_url=args.api_base_url,
                route_id=route_id,
                token=args.token,
                score_version="v1",
                limit=args.limit,
            )
            v2 = _fetch_route(
                client,
                base_url=args.api_base_url,
                route_id=route_id,
                token=args.token,
                score_version="v2",
                limit=args.limit,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            v1_leads = v1.get("leads", [])
            v2_leads = v2.get("leads", [])
            v1_top = [str(x.get("business_id")) for x in v1_leads[:top_k]]
            v2_top = [str(x.get("business_id")) for x in v2_leads[:top_k]]
            v1_rank = {bid: idx + 1 for idx, bid in enumerate(v1_top)}
            v2_rank = {bid: idx + 1 for idx, bid in enumerate(v2_top)}

            overlap_ids = sorted(set(v1_top).intersection(v2_top))
            overlap_rate = len(overlap_ids) / max(top_k, 1)
            abs_rank_delta = (
                sum(abs(v1_rank[bid] - v2_rank[bid]) for bid in overlap_ids) / max(len(overlap_ids), 1)
            )

            route_summary = {
                "route_id": route_id,
                "latency_ms": round(elapsed_ms, 1),
                "top_k": top_k,
                "top_k_overlap_rate": round(overlap_rate, 4),
                "avg_abs_rank_delta_overlap": round(abs_rank_delta, 3),
                "v1_top_business_ids": v1_top,
                "v2_top_business_ids": v2_top,
            }

            if engine is not None:
                all_ids = sorted(set(v1_top + v2_top))
                outcomes = _outcome_by_business(engine, all_ids)
                v1_saved = sum(outcomes.get(bid, {}).get("saved", 0) for bid in v1_top)
                v2_saved = sum(outcomes.get(bid, {}).get("saved", 0) for bid in v2_top)
                v1_contacted = sum(outcomes.get(bid, {}).get("contacted", 0) for bid in v1_top)
                v2_contacted = sum(outcomes.get(bid, {}).get("contacted", 0) for bid in v2_top)
                route_summary.update(
                    {
                        "v1_top_saved_rate": round(v1_saved / max(top_k, 1), 4),
                        "v2_top_saved_rate": round(v2_saved / max(top_k, 1), 4),
                        "v1_top_contacted_rate": round(v1_contacted / max(top_k, 1), 4),
                        "v2_top_contacted_rate": round(v2_contacted / max(top_k, 1), 4),
                    }
                )

            total_overlap += overlap_rate
            total_abs_rank_delta += abs_rank_delta
            route_summaries.append(route_summary)

            line = (
                f"route={route_id} latency_ms={elapsed_ms:.1f} overlap={overlap_rate:.3f} "
                f"avg_abs_rank_delta={abs_rank_delta:.2f}"
            )
            print(line)
            lines.append(line)

    if not route_summaries:
        raise SystemExit("No route comparisons succeeded.")

    summary = {
        "routes_compared": len(route_summaries),
        "avg_top_k_overlap_rate": round(total_overlap / len(route_summaries), 4),
        "avg_abs_rank_delta_overlap": round(total_abs_rank_delta / len(route_summaries), 3),
        "route_summaries": route_summaries,
    }
    print(json.dumps(summary, indent=2))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
