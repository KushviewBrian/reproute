from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import contact_intelligence as ci


def test_person_name_guard_accepts_reasonable_names() -> None:
    assert ci.is_probable_person_name("Jane Doe") is True
    assert ci.is_probable_person_name("A. Smith") is True


def test_person_name_guard_rejects_entities_and_noise() -> None:
    assert ci.is_probable_person_name("Acme Roofing LLC") is False
    assert ci.is_probable_person_name("http://example.com") is False
    assert ci.is_probable_person_name("team123") is False


def test_employee_band_from_estimate() -> None:
    assert ci.employee_count_band_from_estimate(5) == "1-10"
    assert ci.employee_count_band_from_estimate(75) == "51-200"
    assert ci.employee_count_band_from_estimate(1200) == "1000+"


@pytest.mark.asyncio
async def test_promote_owner_name_respects_manual_lock(monkeypatch) -> None:
    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(ci, "record_contact_candidate", _noop)
    business = SimpleNamespace(
        id="biz_1",
        owner_name="Manual Person",
        owner_name_source="manual",
        owner_name_confidence=1.0,
        owner_name_last_checked_at=None,
    )
    changed = await ci.promote_owner_name(
        db=None,
        business=business,
        owner_name="Website Person",
        source="website_jsonld",
        confidence=0.9,
    )
    assert changed is False
    assert business.owner_name == "Manual Person"


@pytest.mark.asyncio
async def test_promote_employee_count_uses_confidence_precedence(monkeypatch) -> None:
    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(ci, "record_contact_candidate", _noop)
    business = SimpleNamespace(
        id="biz_2",
        employee_count_estimate=25,
        employee_count_band="11-50",
        employee_count_source="website_text",
        employee_count_confidence=0.65,
        employee_count_last_checked_at=None,
    )
    changed = await ci.promote_employee_count(
        db=None,
        business=business,
        estimate=40,
        band="11-50",
        source="website_jsonld",
        confidence=0.90,
    )
    assert changed is True
    assert business.employee_count_estimate == 40
    assert business.employee_count_source == "website_jsonld"
