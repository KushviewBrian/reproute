from __future__ import annotations

import httpx

from app.services.validation_service import (
    _classify_request_failure,
    _normalize_phone,
    _overall_label,
    overall_confidence,
    FieldResult,
)


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
