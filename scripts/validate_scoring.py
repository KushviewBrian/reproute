#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate lead scoring quality/latency on real route IDs")
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument("--token", required=True, help="Bearer token")
    parser.add_argument("--route-id", action="append", required=True, help="Route UUID (repeat 5x)")
    parser.add_argument("--limit", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    headers = {"Authorization": f"Bearer {args.token}"}

    total_ms = 0.0
    total_routes = 0
    total_bad = 0

    with httpx.Client(timeout=20) as client:
        for route_id in args.route_id:
            params = {"min_score": 0, "limit": args.limit}
            start = time.perf_counter()
            resp = client.get(f"{args.api_base_url.rstrip('/')}/routes/{route_id}/leads", params=params, headers=headers)
            elapsed_ms = (time.perf_counter() - start) * 1000.0

            if resp.status_code != 200:
                print(f"route={route_id} status={resp.status_code} body={resp.text[:500]}")
                continue

            payload = resp.json()
            leads = payload.get("leads", [])
            bad_in_top = sum(1 for lead in leads if (lead.get("insurance_class") or "").strip().lower() == "exclude")
            avg_score = round(sum(float(lead.get("final_score") or 0) for lead in leads) / max(len(leads), 1), 1)

            total_ms += elapsed_ms
            total_routes += 1
            total_bad += bad_in_top

            print(
                f"route={route_id} leads={len(leads)} filtered={payload.get('filtered', 0)} "
                f"latency_ms={elapsed_ms:.1f} avg_score={avg_score} excluded_in_top={bad_in_top}"
            )

    if total_routes == 0:
        raise SystemExit("No route validations succeeded.")

    avg_latency_ms = total_ms / total_routes
    print(
        f"\nsummary routes={total_routes} avg_latency_ms={avg_latency_ms:.1f} "
        f"total_excluded_in_top={total_bad}"
    )


if __name__ == "__main__":
    main()

