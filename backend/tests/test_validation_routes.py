from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import validation as validation_routes
from app.models.user import User
from app.schemas.validation import PinFieldRequest, TriggerValidationRequest


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


@pytest.mark.asyncio
async def test_trigger_validation_returns_503_when_counter_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(validation_routes, "enforce_rate_limit", _noop_async)
    monkeypatch.setattr(validation_routes, "user_can_access_business", _true_async)
    monkeypatch.setattr(validation_routes, "reserve_validation_caps", _counter_unavailable_async)
    user = User(id=uuid.uuid4(), email="owner@example.com")
    with pytest.raises(HTTPException) as exc:
        await validation_routes.trigger_validation(
            business_id=uuid.uuid4(),
            payload=TriggerValidationRequest(requested_checks=["website"]),
            user=user,
            db=SimpleNamespace(),
        )
    assert exc.value.status_code == 503


async def _false_async(*_args, **_kwargs):
    return False


async def _true_async(*_args, **_kwargs):
    return True


async def _cap_exceeded_async(*_args, **_kwargs):
    raise PermissionError("Validation cap exceeded")


async def _counter_unavailable_async(*_args, **_kwargs):
    raise RuntimeError("Validation rate counter unavailable")


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


@pytest.mark.asyncio
async def test_trigger_validation_success_runs_and_returns_run_id(monkeypatch) -> None:
    monkeypatch.setattr(validation_routes, "enforce_rate_limit", _noop_async)
    monkeypatch.setattr(validation_routes, "user_can_access_business", _true_async)
    monkeypatch.setattr(validation_routes, "reserve_validation_caps", _noop_async)
    monkeypatch.setattr(validation_routes, "enqueue_validation_run", _enqueue_run_stub)
    monkeypatch.setattr(validation_routes, "process_run_by_id", _process_run_stub)

    run_id = uuid.uuid4()
    user = User(id=uuid.uuid4(), email="owner@example.com")
    resp = await validation_routes.trigger_validation(
        business_id=run_id,
        payload=TriggerValidationRequest(requested_checks=["website"]),
        user=user,
        db=SimpleNamespace(),
    )
    assert resp.run_id == run_id
    assert resp.status == "done"


@pytest.mark.asyncio
async def test_read_validation_state_success_includes_overall_label(monkeypatch) -> None:
    monkeypatch.setattr(validation_routes, "user_can_access_business", _true_async)
    monkeypatch.setattr(validation_routes, "get_validation_state", _get_state_stub)

    user = User(id=uuid.uuid4(), email="owner@example.com")
    resp = await validation_routes.read_validation_state(
        business_id=uuid.uuid4(),
        user=user,
        db=SimpleNamespace(),
    )
    assert resp.overall_label == "Mostly valid"
    assert resp.run is not None
    assert len(resp.fields) == 1


@pytest.mark.asyncio
async def test_trigger_validation_cross_user_business_denied(monkeypatch) -> None:
    """User B cannot trigger validation on a business they do not own or have on a route."""
    monkeypatch.setattr(validation_routes, "enforce_rate_limit", _noop_async)
    # user_can_access_business returns False for this user/business combination
    monkeypatch.setattr(validation_routes, "user_can_access_business", _false_async)
    other_users_business_id = uuid.uuid4()
    attacker = User(id=uuid.uuid4(), email="attacker@example.com")
    with pytest.raises(HTTPException) as exc:
        await validation_routes.trigger_validation(
            business_id=other_users_business_id,
            payload=TriggerValidationRequest(requested_checks=["website", "phone"]),
            user=attacker,
            db=SimpleNamespace(),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_read_validation_state_cross_user_business_denied(monkeypatch) -> None:
    """User B cannot read validation state for a business they do not own or have on a route."""
    monkeypatch.setattr(validation_routes, "user_can_access_business", _false_async)
    attacker = User(id=uuid.uuid4(), email="attacker@example.com")
    with pytest.raises(HTTPException) as exc:
        await validation_routes.read_validation_state(
            business_id=uuid.uuid4(),
            user=attacker,
            db=SimpleNamespace(),
        )
    assert exc.value.status_code == 404


async def _enqueue_run_stub(_db, *, business_id, user_id, requested_checks):
    _ = user_id, requested_checks
    return SimpleNamespace(id=business_id, status="queued")


async def _process_run_stub(_db, _run_id):
    return SimpleNamespace(id=_run_id, status="done"), []


async def _get_state_stub(_db, _business_id):
    run = SimpleNamespace(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        status="done",
        requested_checks=["website", "phone"],
        started_at=None,
        finished_at=None,
        error_message=None,
    )
    field = SimpleNamespace(
        field_name="website",
        state="valid",
        confidence=85.0,
        failure_class=None,
        value_current="https://example.com",
        value_normalized="https://example.com",
        evidence_json={"status_code": 200},
        last_checked_at=None,
        next_check_at=None,
        pinned_by_user=False,
    )
    return run, [field], 72.5, "Mostly valid"


# ---------------------------------------------------------------------------
# Pin/unpin endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pin_field_denied_for_inaccessible_business(monkeypatch) -> None:
    monkeypatch.setattr(validation_routes, "user_can_access_business", _false_async)
    user = User(id=uuid.uuid4(), email="owner@example.com")
    with pytest.raises(HTTPException) as exc:
        await validation_routes.pin_validation_field(
            business_id=uuid.uuid4(),
            field_name="website",
            payload=PinFieldRequest(pinned=True),
            user=user,
            db=SimpleNamespace(),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_pin_field_returns_404_when_field_not_found(monkeypatch) -> None:
    monkeypatch.setattr(validation_routes, "user_can_access_business", _true_async)
    monkeypatch.setattr(validation_routes, "set_field_pin", _noop_async)  # returns None
    user = User(id=uuid.uuid4(), email="owner@example.com")
    with pytest.raises(HTTPException) as exc:
        await validation_routes.pin_validation_field(
            business_id=uuid.uuid4(),
            field_name="website",
            payload=PinFieldRequest(pinned=True),
            user=user,
            db=SimpleNamespace(),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_pin_field_success(monkeypatch) -> None:
    monkeypatch.setattr(validation_routes, "user_can_access_business", _true_async)
    monkeypatch.setattr(validation_routes, "set_field_pin", _pin_stub)
    user = User(id=uuid.uuid4(), email="owner@example.com")
    resp = await validation_routes.pin_validation_field(
        business_id=uuid.uuid4(),
        field_name="website",
        payload=PinFieldRequest(pinned=True),
        user=user,
        db=SimpleNamespace(),
    )
    assert resp.field_name == "website"
    assert resp.pinned_by_user is True


async def _pin_stub(_db, _business_id, field_name, pinned):
    return SimpleNamespace(field_name=field_name, pinned_by_user=pinned)


# ---------------------------------------------------------------------------
# Prune endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prune_rejects_missing_headers() -> None:
    with pytest.raises(HTTPException) as exc:
        await validation_routes.prune_validations(db=SimpleNamespace())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_prune_rejects_invalid_hmac(monkeypatch) -> None:
    def _raise(*_args, **_kwargs):
        raise PermissionError("Validation admin token invalid")
    monkeypatch.setattr(validation_routes, "verify_admin_hmac", _raise)
    with pytest.raises(HTTPException) as exc:
        await validation_routes.prune_validations(
            x_admin_timestamp="123",
            x_admin_token="bad",
            db=SimpleNamespace(),
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_prune_success_returns_deleted_count(monkeypatch) -> None:
    monkeypatch.setattr(validation_routes, "verify_admin_hmac", lambda *_a, **_k: None)
    monkeypatch.setattr(validation_routes, "prune_old_validation_runs", _prune_stub)
    resp = await validation_routes.prune_validations(
        retain_days=30,
        x_admin_timestamp="123",
        x_admin_token="ok",
        db=SimpleNamespace(),
    )
    assert resp.deleted == 42


async def _prune_stub(_db, *, retain_days):
    _ = retain_days
    return 42
