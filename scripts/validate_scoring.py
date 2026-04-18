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
    parser.add_argument("--output", help="Optional output file path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    headers = {"Authorization": f"Bearer {args.token}"}

    total_ms = 0.0
    total_routes = 0
    total_bad = 0
    total_other_unknown = 0
    total_leads = 0
    lines: list[str] = []

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
            other_unknown = sum(
                1
                for lead in leads
                if (lead.get("insurance_class") or "").strip().lower() in {"other", "unknown"}
            )
            avg_score = round(sum(float(lead.get("final_score") or 0) for lead in leads) / max(len(leads), 1), 1)

            total_ms += elapsed_ms
            total_routes += 1
            total_bad += bad_in_top
            total_other_unknown += other_unknown
            total_leads += len(leads)

            line = (
                f"route={route_id} leads={len(leads)} filtered={payload.get('filtered', 0)} "
                f"latency_ms={elapsed_ms:.1f} avg_score={avg_score} excluded_in_top={bad_in_top} "
                f"other_unknown_in_top={other_unknown}"
            )
            print(line)
            lines.append(line)

    if total_routes == 0:
        raise SystemExit("No route validations succeeded.")

    avg_latency_ms = total_ms / total_routes
    other_unknown_rate = round((total_other_unknown / max(total_leads, 1)) * 100.0, 2)
    summary = (
        f"\nsummary routes={total_routes} avg_latency_ms={avg_latency_ms:.1f} "
        f"total_excluded_in_top={total_bad} other_unknown_rate={other_unknown_rate}%"
    )
    print(summary)
    lines.append(summary.strip())
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
