from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from app.db.session import _get_engine
from app.models.business import Business


@dataclass
class DailyContactMetrics:
    generated_at: str
    owner_coverage_pct: float
    employee_coverage_pct: float
    owner_source_mix: dict[str, int]
    employee_source_mix: dict[str, int]


async def build_metrics() -> DailyContactMetrics:
    _, SessionLocal = _get_engine()
    async with SessionLocal() as db:
        total = int((await db.scalar(select(func.count()).select_from(Business))) or 0)
        owner_with = int((await db.scalar(select(func.count()).select_from(Business).where(Business.owner_name.is_not(None)))) or 0)
        employee_with = int((await db.scalar(select(func.count()).select_from(Business).where(Business.employee_count_estimate.is_not(None)))) or 0)

        owner_mix_rows = (
            await db.execute(
                select(Business.owner_name_source, func.count())
                .where(Business.owner_name_source.is_not(None))
                .group_by(Business.owner_name_source)
            )
        ).all()
        employee_mix_rows = (
            await db.execute(
                select(Business.employee_count_source, func.count())
                .where(Business.employee_count_source.is_not(None))
                .group_by(Business.employee_count_source)
            )
        ).all()

    def _pct(numerator: int) -> float:
        if total <= 0:
            return 0.0
        return round((numerator / total) * 100.0, 2)

    return DailyContactMetrics(
        generated_at=datetime.now(UTC).isoformat(),
        owner_coverage_pct=_pct(owner_with),
        employee_coverage_pct=_pct(employee_with),
        owner_source_mix={str(src): int(count) for src, count in owner_mix_rows},
        employee_source_mix={str(src): int(count) for src, count in employee_mix_rows},
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate daily owner/employee coverage metrics.")
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output path. Defaults to docs/evidence/phase12_contact_metrics_<date>.json",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    metrics = await build_metrics()
    default_path = Path("docs/evidence") / f"phase12_contact_metrics_{datetime.now(UTC).date().isoformat()}.json"
    out_path = Path(args.out) if args.out else default_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(metrics), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
