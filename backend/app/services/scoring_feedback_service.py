from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scoring_feedback_prior import ScoringFeedbackPrior


async def load_feedback_priors(
    db: AsyncSession,
    *,
    calibration_version: str,
) -> dict:
    rows = (
        await db.execute(
            select(ScoringFeedbackPrior).where(ScoringFeedbackPrior.calibration_version == calibration_version)
        )
    ).scalars().all()

    segments: dict[tuple[str, str | None, bool, bool, str], dict] = {}
    globals_by_geo: dict[str, dict] = {}
    default_global = {"prior_save": 0.20, "prior_contact": 0.08, "sample_size": 0}

    for row in rows:
        geo_key = (row.geo_key or "global").strip().lower()
        if row.distance_band == "global":
            globals_by_geo[geo_key] = {
                "prior_save": float(row.prior_save),
                "prior_contact": float(row.prior_contact),
                "sample_size": int(row.sample_size),
            }
            continue
        if row.has_phone is None or row.has_website is None:
            continue
        segments[(geo_key, row.insurance_class, bool(row.has_phone), bool(row.has_website), row.distance_band)] = {
            "prior_save": float(row.prior_save),
            "prior_contact": float(row.prior_contact),
            "sample_size": int(row.sample_size),
        }

    return {
        "segments": segments,
        "globals_by_geo": globals_by_geo,
        "global": globals_by_geo.get("global", default_global),
        "calibration_version": calibration_version,
    }
