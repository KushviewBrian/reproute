from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.business_contact_candidate import BusinessContactCandidate

logger = logging.getLogger(__name__)

SOURCE_CONFIDENCE: dict[str, float] = {
    "manual": 1.0,
    "website_jsonld": 0.90,
    "website_text": 0.65,
    "osm_operator": 0.60,
    "unknown": 0.10,
}

_ENTITY_TOKENS = {
    "llc", "inc", "ltd", "corp", "corporation", "co", "company", "group", "services",
    "service", "enterprises", "enterprise", "holdings", "partners", "plumbing", "roofing",
    "hvac", "electric", "electricity", "contracting", "industries", "solutions", "shop",
}

_PERSON_FRAGMENT_RE = re.compile(r"^[A-Za-z][A-Za-z .'\-]{0,58}[A-Za-z.]$")
_WORD_RE = re.compile(r"[A-Za-z]+")


def resolved_confidence(source: str, fallback: float | None = None) -> float:
    return SOURCE_CONFIDENCE.get(source, float(fallback or 0.0))


def is_probable_person_name(value: str | None) -> bool:
    if value is None:
        return False
    raw = value.strip()
    if not raw or len(raw) < 2 or len(raw) > 60:
        return False
    lowered = raw.lower()
    if "@" in lowered or "http://" in lowered or "https://" in lowered:
        return False
    if any(ch.isdigit() for ch in raw):
        return False
    if not _PERSON_FRAGMENT_RE.match(raw):
        return False
    words = [w for w in _WORD_RE.findall(raw) if w]
    if not (1 <= len(words) <= 4):
        return False
    if any(w.lower() in _ENTITY_TOKENS for w in words):
        return False
    return True


def employee_count_band_from_estimate(estimate: int | None) -> str | None:
    if estimate is None:
        return None
    if estimate < 1:
        return None
    if estimate <= 10:
        return "1-10"
    if estimate <= 50:
        return "11-50"
    if estimate <= 200:
        return "51-200"
    if estimate <= 500:
        return "201-500"
    if estimate <= 1000:
        return "501-1000"
    return "1000+"


def _value_hash(field_key: str, value_text: str | None, value_numeric: int | None) -> str:
    text_norm = (value_text or "").strip().lower()
    raw = f"{field_key}|{text_norm}|{'' if value_numeric is None else int(value_numeric)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def record_contact_candidate(
    db: AsyncSession,
    *,
    business_id,
    field_key: str,
    source: str,
    confidence: float,
    value_text: str | None = None,
    value_numeric: int | None = None,
    evidence_json: dict[str, Any] | None = None,
    accepted: bool = False,
) -> None:
    now = datetime.now(UTC)
    hash_value = _value_hash(field_key, value_text, value_numeric)
    stmt = (
        insert(BusinessContactCandidate)
        .values(
            id=uuid.uuid4(),
            business_id=business_id,
            field_key=field_key,
            value_text=value_text,
            value_numeric=value_numeric,
            source=source,
            confidence=confidence,
            evidence_json=evidence_json or {},
            observed_at=now,
            promoted_at=now if accepted else None,
            is_active=bool(accepted),
            value_hash=hash_value,
        )
        .on_conflict_do_update(
            constraint="uq_bcc_business_field_source_hash",
            set_={
                "confidence": confidence,
                "evidence_json": evidence_json or {},
                "observed_at": now,
                "promoted_at": now if accepted else BusinessContactCandidate.promoted_at,
                "is_active": True if accepted else BusinessContactCandidate.is_active,
            },
        )
    )
    await db.execute(stmt)
    if accepted:
        await db.execute(
            update(BusinessContactCandidate)
            .where(
                BusinessContactCandidate.business_id == business_id,
                BusinessContactCandidate.field_key == field_key,
                BusinessContactCandidate.value_hash != hash_value,
                BusinessContactCandidate.is_active.is_(True),
            )
            .values(is_active=False)
        )


async def promote_owner_name(
    db: AsyncSession,
    business: Business,
    *,
    owner_name: str | None,
    source: str,
    confidence: float | None = None,
    evidence_json: dict[str, Any] | None = None,
) -> bool:
    new_conf = resolved_confidence(source, confidence)
    candidate = (owner_name or "").strip() or None

    if source != "manual" and not is_probable_person_name(candidate):
        await record_contact_candidate(
            db,
            business_id=business.id,
            field_key="owner_name",
            source=source,
            confidence=new_conf,
            value_text=candidate,
            evidence_json=evidence_json,
            accepted=False,
        )
        return False

    existing_conf = float(business.owner_name_confidence or 0.0)
    existing_source = business.owner_name_source or ""
    accepted = False
    if existing_source == "manual" and source != "manual":
        accepted = False
        logger.info("owner_manual_overwrite_blocked business_id=%s source=%s", business.id, source)
    elif business.owner_name is None or new_conf > existing_conf or source == "manual":
        business.owner_name = candidate
        business.owner_name_source = source
        business.owner_name_confidence = new_conf
        business.owner_name_last_checked_at = datetime.now(UTC)
        accepted = True

    await record_contact_candidate(
        db,
        business_id=business.id,
        field_key="owner_name",
        source=source,
        confidence=new_conf,
        value_text=candidate,
        evidence_json=evidence_json,
        accepted=accepted,
    )
    logger.info(
        "owner_promotion business_id=%s accepted=%s source=%s confidence=%.3f has_value=%s",
        business.id,
        accepted,
        source,
        new_conf,
        bool(candidate),
    )
    return accepted


async def promote_employee_count(
    db: AsyncSession,
    business: Business,
    *,
    estimate: int | None,
    band: str | None,
    source: str,
    confidence: float | None = None,
    evidence_json: dict[str, Any] | None = None,
) -> bool:
    if estimate is not None:
        estimate = int(estimate)
    if estimate is not None and (estimate < 1 or estimate > 5_000_000):
        return False
    normalized_band = (band or "").strip() or employee_count_band_from_estimate(estimate)
    if estimate is None and not normalized_band:
        return False

    new_conf = resolved_confidence(source, confidence)
    existing_conf = float(business.employee_count_confidence or 0.0)
    existing_source = business.employee_count_source or ""
    accepted = False

    if existing_source == "manual" and source != "manual":
        accepted = False
        logger.info("employee_manual_overwrite_blocked business_id=%s source=%s", business.id, source)
    elif business.employee_count_estimate is None and business.employee_count_band is None:
        accepted = True
    elif source == "manual":
        accepted = True
    elif new_conf > existing_conf:
        accepted = True

    if accepted:
        business.employee_count_estimate = estimate
        business.employee_count_band = normalized_band
        business.employee_count_source = source
        business.employee_count_confidence = new_conf
        business.employee_count_last_checked_at = datetime.now(UTC)

    await record_contact_candidate(
        db,
        business_id=business.id,
        field_key="employee_count_estimate",
        source=source,
        confidence=new_conf,
        value_numeric=estimate,
        value_text=str(estimate) if estimate is not None else None,
        evidence_json=evidence_json,
        accepted=accepted,
    )
    await record_contact_candidate(
        db,
        business_id=business.id,
        field_key="employee_count_band",
        source=source,
        confidence=new_conf,
        value_text=normalized_band,
        evidence_json=evidence_json,
        accepted=accepted,
    )
    logger.info(
        "employee_promotion business_id=%s accepted=%s source=%s confidence=%.3f estimate=%s band=%s",
        business.id,
        accepted,
        source,
        new_conf,
        estimate,
        normalized_band,
    )
    return accepted
