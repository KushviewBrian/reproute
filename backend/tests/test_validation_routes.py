from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import validation as validation_routes
from app.models.user import User
from app.schemas.validation import TriggerValidationRequest


async def _noop_async(*_args, **_kwargs):
    return None


@pytest.mark.asyncio
async def test_run_due_rejects_missing_headers() -> None:
    with pytest.raises(HTTPException) as exc:
        await validation_routes.run_due_validations()
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_run_due_rejects_invalid_hmac(monkeypatch) -> None:
    def _raise(*_args, **_kwargs):
        raise PermissionError("Validation admin token invalid")

    monkeypatch.setattr(validation_routes, "verify_admin_hmac", _raise)
    with pytest.raises(HTTPException) as exc:
        await validation_routes.run_due_validations(
            x_admin_timestamp="123",
            x_admin_token="bad",
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_run_due_success_returns_counts(monkeypatch) -> None:
    monkeypatch.setattr(validation_routes, "verify_admin_hmac", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(validation_routes, "process_queued_runs", _stub_process_queued_runs)
    resp = await validation_routes.run_due_validations(
        limit=7,
        x_admin_timestamp="123",
        x_admin_token="ok",
    )
    assert resp.queued == 7
    assert resp.completed == 6
    assert resp.failed == 1


async def _stub_process_queued_runs(limit: int):
    return (limit, max(limit - 1, 0), 1)


@pytest.mark.asyncio
async def test_trigger_validation_rejects_inaccessible_business(monkeypatch) -> None:
    monkeypatch.setattr(validation_routes, "enforce_rate_limit", _noop_async)
    monkeypatch.setattr(validation_routes, "user_can_access_business", _false_async)
    user = User(id=uuid.uuid4(), email="owner@example.com")
    with pytest.raises(HTTPException) as exc:
        await validation_routes.trigger_validation(
            business_id=uuid.uuid4(),
            payload=TriggerValidationRequest(requested_checks=["website"]),
            user=user,
            db=SimpleNamespace(),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_trigger_validation_rejects_when_cap_exceeded(monkeypatch) -> None:
    monkeypatch.setattr(validation_routes, "enforce_rate_limit", _noop_async)
    monkeypatch.setattr(validation_routes, "user_can_access_business", _true_async)
    monkeypatch.setattr(validation_routes, "reserve_validation_caps", _cap_exceeded_async)
    user = User(id=uuid.uuid4(), email="owner@example.com")
    with pytest.raises(HTTPException) as exc:
        await validation_routes.trigger_validation(
            business_id=uuid.uuid4(),
            payload=TriggerValidationRequest(requested_checks=["website"]),
            user=user,
            db=SimpleNamespace(),
        )
    assert exc.value.status_code == 429


async def _false_async(*_args, **_kwargs):
    return False


async def _true_async(*_args, **_kwargs):
    return True


async def _cap_exceeded_async(*_args, **_kwargs):
    raise PermissionError("Validation cap exceeded")


@pytest.mark.asyncio
async def test_read_validation_state_rejects_inaccessible_business(monkeypatch) -> None:
    monkeypatch.setattr(validation_routes, "user_can_access_business", _false_async)
    user = User(id=uuid.uuid4(), email="owner@example.com")
    with pytest.raises(HTTPException) as exc:
        await validation_routes.read_validation_state(
            business_id=uuid.uuid4(),
            user=user,
            db=SimpleNamespace(),
        )
    assert exc.value.status_code == 404
