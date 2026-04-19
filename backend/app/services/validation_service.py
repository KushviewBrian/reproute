from __future__ import annotations

import asyncio
import hashlib
import hmac
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import UUID

import httpx
from sqlalchemy import delete, desc, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import _get_engine
from app.models.business import Business
from app.models.lead_field_validation import LeadFieldValidation
from app.models.lead_validation_run import LeadValidationRun
from app.models.route import Route
from app.models.route_candidate import RouteCandidate
from app.models.saved_lead import SavedLead
from app.utils.redis_client import redis_client


VALIDATION_FIELDS = {"website", "phone"}


@dataclass
class FieldResult:
    field_name: str
    state: str
    confidence: float
    failure_class: str | None
    value_current: str | None
    value_normalized: str | None
    evidence_json: dict
    next_check_days: int


async def user_can_access_business(db: AsyncSession, user_id: UUID, business_id: UUID) -> bool:
    saved_exists = await db.scalar(
        select(func.count())
        .select_from(SavedLead)
        .where(SavedLead.user_id == user_id, SavedLead.business_id == business_id)
    )
    if int(saved_exists or 0) > 0:
        return True
    route_exists = await db.scalar(
        select(func.count())
        .select_from(RouteCandidate)
        .join(Route, Route.id == RouteCandidate.route_id)
        .where(Route.user_id == user_id, RouteCandidate.business_id == business_id)
    )
    return int(route_exists or 0) > 0


async def reserve_validation_caps(user_id: UUID | None) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    day_key = now.strftime("%Y-%m-%d")
    month_key = now.strftime("%Y-%m")
    keys = [
        (f"validation:global:day:{day_key}", settings.validation_daily_cap, 2 * 24 * 60 * 60),
        (f"validation:global:month:{month_key}", settings.validation_monthly_cap, 40 * 24 * 60 * 60),
    ]
    if user_id is not None:
        keys.append((f"validation:user:{user_id}:day:{day_key}", settings.validation_per_user_daily_cap, 2 * 24 * 60 * 60))
    for key, limit, ttl in keys:
        value = await redis_client.incr(key)
        if value is None:
            raise RuntimeError("Validation rate counter unavailable")
        if value == 1:
            await redis_client.expire(key, ttl)
        if int(value) > int(limit):
            raise PermissionError("Validation cap exceeded")


async def enqueue_validation_run(
    db: AsyncSession,
    *,
    business_id: UUID,
    user_id: UUID | None,
    requested_checks: list[str],
) -> LeadValidationRun:
    normalized_checks = [c for c in requested_checks if c in VALIDATION_FIELDS]
    run = LeadValidationRun(
        business_id=business_id,
        user_id=user_id,
        requested_checks=normalized_checks or ["website", "phone"],
        status="queued",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def claim_next_queued_run(db: AsyncSession) -> UUID | None:
    stmt = text(
        """
        WITH next_job AS (
          SELECT id
          FROM lead_validation_run
          WHERE status = 'queued'
          ORDER BY created_at
          FOR UPDATE SKIP LOCKED
          LIMIT 1
        )
        UPDATE lead_validation_run AS r
        SET status = 'running',
            started_at = now(),
            error_message = NULL
        FROM next_job
        WHERE r.id = next_job.id
        RETURNING r.id
        """
    )
    row = (await db.execute(stmt)).first()
    if not row:
        await db.rollback()
        return None
    await db.commit()
    return row[0]


def _overall_label(confidence: float | None) -> str:
    if confidence is None:
        return "Unchecked"
    if confidence >= 80:
        return "Validated"
    if confidence >= 60:
        return "Mostly valid"
    if confidence >= 40:
        return "Needs review"
    return "Low confidence"


def overall_confidence(results: list[FieldResult]) -> float | None:
    if not results:
        return None
    weights = {"website": 35.0, "phone": 30.0}
    total_weight = 0.0
    weighted = 0.0
    for result in results:
        w = weights.get(result.field_name)
        if w is None:
            continue
        weighted += float(result.confidence) * w
        total_weight += w
    if total_weight <= 0:
        return None
    return round(weighted / total_weight, 2)


def _confidence_from_field_rows(fields: list[LeadFieldValidation]) -> float | None:
    weighted_inputs: list[FieldResult] = []
    fallback_values: list[float] = []
    for field in fields:
        if field.confidence is None:
            continue
        confidence = float(field.confidence)
        fallback_values.append(confidence)
        weighted_inputs.append(
            FieldResult(
                field_name=field.field_name,
                state=field.state or "unknown",
                confidence=confidence,
                failure_class=field.failure_class,
                value_current=field.value_current,
                value_normalized=field.value_normalized,
                evidence_json=field.evidence_json or {},
                next_check_days=30,
            )
        )
    conf = overall_confidence(weighted_inputs)
    if conf is not None:
        return conf
    if fallback_values:
        return round(sum(fallback_values) / len(fallback_values), 2)
    return None


async def get_validation_state(db: AsyncSession, business_id: UUID) -> tuple[LeadValidationRun | None, list[LeadFieldValidation], float | None, str]:
    run = (
        await db.execute(
            select(LeadValidationRun)
            .where(LeadValidationRun.business_id == business_id)
            .order_by(desc(LeadValidationRun.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    fields = (
        await db.execute(
            select(LeadFieldValidation).where(LeadFieldValidation.business_id == business_id).order_by(LeadFieldValidation.field_name.asc())
        )
    ).scalars().all()
    if not fields:
        return run, [], None, "Unchecked"
    conf = _confidence_from_field_rows(list(fields))
    return run, list(fields), conf, _overall_label(conf)


def verify_admin_hmac(timestamp_header: str, token_header: str) -> None:
    settings = get_settings()
    secret = settings.validation_hmac_secret.strip()
    if not secret:
        raise PermissionError("Validation HMAC secret missing")
    try:
        now_ts = int(datetime.now(UTC).timestamp())
        ts = int(timestamp_header)
        ttl = int(settings.validation_admin_token_ttl_seconds)
    except (TypeError, ValueError) as exc:
        raise PermissionError("Validation admin token invalid") from exc
    if ttl <= 0:
        raise PermissionError("Validation admin token invalid")
    if abs(now_ts - ts) > ttl:
        raise PermissionError("Validation admin token expired")
    expected = hmac.new(secret.encode("utf-8"), str(ts).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, token_header):
        raise PermissionError("Validation admin token invalid")


def _truncate_evidence(payload: dict, max_bytes: int = 8192) -> dict:
    raw = str(payload)
    if len(raw.encode("utf-8")) <= max_bytes:
        return payload
    return {"truncated": True, "sample": raw[: max_bytes // 2]}


def _classify_request_failure(exc: Exception) -> tuple[str, str, float]:
    msg = str(exc).lower()
    if isinstance(exc, httpx.ConnectTimeout):
        return "timeout", "unknown", 35.0
    if isinstance(exc, httpx.ReadTimeout):
        return "timeout", "unknown", 35.0
    if isinstance(exc, httpx.ConnectError):
        if any(token in msg for token in ("name or service not known", "nodename nor servname", "getaddrinfo")):
            return "dns", "invalid", 20.0
        if "certificate verify failed" in msg:
            return "tls_error", "warning", 35.0
        return "network", "unknown", 40.0
    return "network", "unknown", 40.0


import json as _json
import re as _re


def _extract_owner_from_html(html):
    # Returns (name, source) or (None, None)
    for script_match in _RE_JSONLD.finditer(html):
        try:
            data = _json.loads(script_match.group(1))
            data_list = data if isinstance(data, list) else [data]
            for item in data_list:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") == "Person":
                    name = (item.get("name") or "").strip()
                    if name:
                        return name, "website_jsonld"
                for key in ("employee", "founder", "owner"):
                    person = item.get(key)
                    if isinstance(person, dict) and person.get("@type") == "Person":
                        name = (person.get("name") or "").strip()
                        if name:
                            return name, "website_jsonld"
        except Exception:
            continue
    for pattern in _OWNER_TEXT_PATTERNS:
        m = pattern.search(html)
        if m:
            name = m.group(1).strip()
            words = name.split()
            if 1 <= len(words) <= 5 and len(name) <= 60 and not any(c.isdigit() for c in name):
                return name, "website_text"
    return None, None


_RE_JSONLD = _re.compile(
    r"<script[^>]+type=(?:[\x22\x27])[^\x22\x27]*ld[+]json(?:[\x22\x27])[^>]*>(.*?)</script>",
    _re.IGNORECASE | _re.DOTALL,
)
_OWNER_TEXT_PATTERNS = [
    _re.compile(r"[Oo]wner[:\s]+([A-Z][a-zA-Z\s\-]{4,40})", _re.MULTILINE),
    _re.compile(r"[Ff]ounded by[:\s]+([A-Z][a-zA-Z\s\-]{4,40})", _re.MULTILINE),
    _re.compile(r"[Cc]ontact\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)", _re.MULTILINE),
]


async def _validate_website(website: str | None) -> FieldResult:
    settings = get_settings()
    if not website:
        return FieldResult(
            field_name="website",
            state="unknown",
            confidence=0.0,
            failure_class="missing",
            value_current=None,
            value_normalized=None,
            evidence_json={"detail": "website missing"},
            next_check_days=30,
        )
    normalized = website.strip()
    if not normalized.startswith("http"):
        normalized = f"https://{normalized}"
    parsed = urlparse(normalized)
    if not parsed.netloc:
        return FieldResult(
            field_name="website",
            state="warning",
            confidence=20.0,
            failure_class="parse_error",
            value_current=website,
            value_normalized=None,
            evidence_json={"detail": "invalid URL"},
            next_check_days=14,
        )
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=settings.validation_http_timeout_seconds, follow_redirects=True) as client:
                resp = await client.get(normalized)
            if resp.status_code in {403, 429}:
                return FieldResult(
                    field_name="website",
                    state="unknown",
                    confidence=45.0,
                    failure_class="bot_blocked",
                    value_current=website,
                    value_normalized=str(resp.url),
                    evidence_json={"status_code": resp.status_code},
                    next_check_days=7,
                )
            if resp.status_code >= 400:
                return FieldResult(
                    field_name="website",
                    state="invalid",
                    confidence=20.0,
                    failure_class="http_error",
                    value_current=website,
                    value_normalized=str(resp.url),
                    evidence_json={"status_code": resp.status_code},
                    next_check_days=14,
                )
            owner_name, owner_source = _extract_owner_from_html(resp.text)
            return FieldResult(
                field_name="website",
                state="valid",
                confidence=85.0,
                failure_class=None,
                value_current=website,
                value_normalized=str(resp.url),
                evidence_json={
                    "status_code": resp.status_code,
                    "content_length": len(resp.text),
                    "owner_name": owner_name,
                    "owner_name_source": owner_source,
                },
                next_check_days=30,
            )
        except Exception as exc:  # pragma: no cover - behavior covered by classifier unit tests
            failure_class, state, confidence = _classify_request_failure(exc)
            if failure_class in {"timeout", "network"} and attempt == 0:
                await asyncio.sleep(settings.validation_retry_delay_seconds)
                continue
            return FieldResult(
                field_name="website",
                state=state,
                confidence=confidence,
                failure_class=failure_class,
                value_current=website,
                value_normalized=normalized,
                evidence_json={"error": str(exc), "attempts": attempt + 1},
                next_check_days=7,
            )

    return FieldResult(
        field_name="website",
        state="unknown",
        confidence=35.0,
        failure_class="network",
        value_current=website,
        value_normalized=normalized,
        evidence_json={"error": "unreachable"},
        next_check_days=7,
    )


def _normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D+", "", phone)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) >= 8:
        return f"+{digits}"
    return None


async def _validate_phone(phone: str | None, website_evidence: FieldResult | None) -> FieldResult:
    normalized = _normalize_phone(phone)
    if not phone:
        return FieldResult(
            field_name="phone",
            state="unknown",
            confidence=0.0,
            failure_class="missing",
            value_current=None,
            value_normalized=None,
            evidence_json={"detail": "phone missing"},
            next_check_days=30,
        )
    if not normalized:
        return FieldResult(
            field_name="phone",
            state="invalid",
            confidence=20.0,
            failure_class="parse_error",
            value_current=phone,
            value_normalized=None,
            evidence_json={"detail": "phone format invalid"},
            next_check_days=14,
        )
    corroborated = False
    if website_evidence and website_evidence.state == "valid":
        text_blob = str(website_evidence.evidence_json)
        corroborated = normalized[-10:] in text_blob
    return FieldResult(
        field_name="phone",
        state="valid" if corroborated else "warning",
        confidence=80.0 if corroborated else 55.0,
        failure_class=None if corroborated else "uncorroborated",
        value_current=phone,
        value_normalized=normalized,
        evidence_json={"corroborated_on_website": corroborated},
        next_check_days=30,
    )


async def upsert_field_validation(db: AsyncSession, business_id: UUID, result: FieldResult) -> None:
    now = datetime.now(UTC)
    stmt = (
        insert(LeadFieldValidation)
        .values(
            business_id=business_id,
            field_name=result.field_name,
            value_current=result.value_current,
            value_normalized=result.value_normalized,
            state=result.state,
            confidence=result.confidence,
            evidence_json=_truncate_evidence(result.evidence_json),
            failure_class=result.failure_class,
            last_checked_at=now,
            next_check_at=now + timedelta(days=result.next_check_days),
        )
        .on_conflict_do_update(
            constraint="uq_lead_field_validation_business_field",
            set_={
                "value_current": result.value_current,
                "value_normalized": result.value_normalized,
                "state": result.state,
                "confidence": result.confidence,
                "evidence_json": _truncate_evidence(result.evidence_json),
                "failure_class": result.failure_class,
                "last_checked_at": now,
                "next_check_at": now + timedelta(days=result.next_check_days),
                "updated_at": func.now(),
            },
        )
    )
    await db.execute(stmt)


async def process_run_by_id(
    db: AsyncSession,
    run_id: UUID,
    *,
    reserve_caps_for_run: bool = False,
) -> tuple[LeadValidationRun, list[FieldResult]]:
    run = await db.get(LeadValidationRun, run_id)
    if run is None:
        raise LookupError("Validation run not found")
    run.status = "running"
    run.started_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(run)

    business = await db.get(Business, run.business_id)
    if business is None:
        run.status = "failed"
        run.error_message = "Business not found"
        run.finished_at = datetime.now(UTC)
        await db.commit()
        return run, []

    all_checks = [c for c in (run.requested_checks or ["website", "phone"]) if c in VALIDATION_FIELDS]
    # Exclude fields the user has pinned — pinned fields are authoritative and skipped by automation.
    pinned_fields: set[str] = set()
    if all_checks:
        pin_rows = (
            await db.execute(
                select(LeadFieldValidation.field_name).where(
                    LeadFieldValidation.business_id == run.business_id,
                    LeadFieldValidation.field_name.in_(all_checks),
                    LeadFieldValidation.pinned_by_user.is_(True),
                )
            )
        ).scalars().all()
        pinned_fields = set(pin_rows)
    checks = [c for c in all_checks if c not in pinned_fields]
    results: list[FieldResult] = []
    website_result: FieldResult | None = None

    try:
        if reserve_caps_for_run:
            await reserve_validation_caps(run.user_id)
        if "website" in checks:
            website_result = await _validate_website(business.website)
            results.append(website_result)
            await upsert_field_validation(db, business.id, website_result)
        if "phone" in checks:
            phone_result = await _validate_phone(business.phone, website_result)
            results.append(phone_result)
            await upsert_field_validation(db, business.id, phone_result)
        business.last_validated_at = datetime.now(UTC)
        run.status = "done"
        run.error_message = None
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
    finally:
        run.finished_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(run)
    return run, results


async def process_queued_runs(limit: int) -> tuple[int, int, int]:
    engine, session_local = _get_engine()
    _ = engine
    queued = 0
    completed = 0
    failed = 0
    lock = asyncio.Lock()

    async def worker() -> None:
        nonlocal queued, completed, failed
        first = True
        while True:
            async with lock:
                if queued >= limit:
                    return
                queued += 1
            # Jitter between fetches: 500ms–2000ms, skipped on the very first job
            if not first:
                await asyncio.sleep(random.uniform(0.5, 2.0))
            first = False
            async with session_local() as db:
                run_id = await claim_next_queued_run(db)
                if run_id is None:
                    async with lock:
                        queued -= 1
                    return
                run, _results = await process_run_by_id(db, run_id, reserve_caps_for_run=True)
                async with lock:
                    if run.status == "done":
                        completed += 1
                    else:
                        failed += 1

    workers = [asyncio.create_task(worker()) for _ in range(2)]
    await asyncio.gather(*workers)
    return queued, completed, failed


async def set_field_pin(
    db: AsyncSession,
    business_id: UUID,
    field_name: str,
    pinned: bool,
) -> LeadFieldValidation | None:
    row = (
        await db.execute(
            select(LeadFieldValidation).where(
                LeadFieldValidation.business_id == business_id,
                LeadFieldValidation.field_name == field_name,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    row.pinned_by_user = pinned
    await db.commit()
    await db.refresh(row)
    return row


async def prune_old_validation_runs(db: AsyncSession, *, retain_days: int = 30) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=retain_days)
    result = await db.execute(
        delete(LeadValidationRun).where(LeadValidationRun.created_at < cutoff)
    )
    await db.commit()
    return int(result.rowcount or 0)
