from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime

import httpx
import pytest

from app.core.config import get_settings
from app.services.validation_service import (
    _classify_request_failure,
    _normalize_phone,
    _overall_label,
    reserve_validation_caps,
    overall_confidence,
    verify_admin_hmac,
    FieldResult,
)
from app.services import validation_service


def test_failure_taxonomy_dns_and_timeout_and_tls() -> None:
    failure, state, _ = _classify_request_failure(httpx.ConnectError("Name or service not known"))
    assert (failure, state) == ("dns", "invalid")

    failure, state, _ = _classify_request_failure(httpx.ConnectTimeout("timed out"))
    assert (failure, state) == ("timeout", "unknown")

    failure, state, _ = _classify_request_failure(httpx.ConnectError("certificate verify failed"))
    assert (failure, state) == ("tls_error", "warning")


def test_phone_normalization() -> None:
    assert _normalize_phone("(317) 555-1212") == "+13175551212"
    assert _normalize_phone("+1 317 555 1212") == "+13175551212"
    assert _normalize_phone("555") is None


def test_overall_confidence_and_labels() -> None:
    results = [
        FieldResult("website", "valid", 90.0, None, None, None, {}, 30),
        FieldResult("phone", "warning", 60.0, None, None, None, {}, 30),
    ]
    score = overall_confidence(results)
    assert score is not None
    assert score >= 70
    assert _overall_label(score) == "Mostly valid"


def test_verify_admin_hmac_rejects_missing_secret(monkeypatch) -> None:
    settings = get_settings()
    original_secret = settings.validation_hmac_secret
    settings.validation_hmac_secret = ""
    try:
        with pytest.raises(PermissionError, match="missing"):
            verify_admin_hmac("1000", "abc")
    finally:
        settings.validation_hmac_secret = original_secret


def test_verify_admin_hmac_rejects_expired_token(monkeypatch) -> None:
    settings = get_settings()
    original_secret = settings.validation_hmac_secret
    original_ttl = settings.validation_admin_token_ttl_seconds
    settings.validation_hmac_secret = "secret"
    settings.validation_admin_token_ttl_seconds = 60

    class _FakeDateTime:
        @staticmethod
        def now(_tz=UTC):
            return datetime.fromtimestamp(2000, tz=UTC)

    monkeypatch.setattr(validation_service, "datetime", _FakeDateTime)
    try:
        with pytest.raises(PermissionError, match="expired"):
            verify_admin_hmac("1900", "abc")
    finally:
        settings.validation_hmac_secret = original_secret
        settings.validation_admin_token_ttl_seconds = original_ttl


def test_verify_admin_hmac_accepts_valid_token(monkeypatch) -> None:
    settings = get_settings()
    original_secret = settings.validation_hmac_secret
    original_ttl = settings.validation_admin_token_ttl_seconds
    settings.validation_hmac_secret = "secret"
    settings.validation_admin_token_ttl_seconds = 60

    ts = 1960
    token = hmac.new(b"secret", str(ts).encode("utf-8"), hashlib.sha256).hexdigest()

    class _FakeDateTime:
        @staticmethod
        def now(_tz=UTC):
            return datetime.fromtimestamp(2000, tz=UTC)

    monkeypatch.setattr(validation_service, "datetime", _FakeDateTime)
    try:
        verify_admin_hmac(str(ts), token)
    finally:
        settings.validation_hmac_secret = original_secret
        settings.validation_admin_token_ttl_seconds = original_ttl


@pytest.mark.asyncio
async def test_reserve_validation_caps_raises_when_counter_unavailable(monkeypatch) -> None:
    async def _incr(_key):
        return None

    async def _expire(_key, _ttl):
        return None

    monkeypatch.setattr(validation_service.redis_client, "incr", _incr)
    monkeypatch.setattr(validation_service.redis_client, "expire", _expire)

    with pytest.raises(RuntimeError, match="counter unavailable"):
        await reserve_validation_caps(uuid.uuid4())


@pytest.mark.asyncio
async def test_reserve_validation_caps_raises_when_limit_exceeded(monkeypatch) -> None:
    settings = get_settings()
    original_daily = settings.validation_daily_cap
    settings.validation_daily_cap = 2

    async def _incr(_key):
        return 3

    async def _expire(_key, _ttl):
        return None

    monkeypatch.setattr(validation_service.redis_client, "incr", _incr)
    monkeypatch.setattr(validation_service.redis_client, "expire", _expire)

    try:
        with pytest.raises(PermissionError, match="cap exceeded"):
            await reserve_validation_caps(uuid.uuid4())
    finally:
        settings.validation_daily_cap = original_daily
