from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import export as export_routes
from app.api.routes import leads as leads_routes
from app.api.routes import notes as notes_routes
from app.api.routes import saved_leads as saved_leads_routes
from app.core import auth as auth_core
from app.core.config import get_settings
from app.main import startup
from app.models.user import User
from app.schemas.note import UpdateNoteRequest
from app.schemas.saved_lead import UpdateSavedLeadRequest


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDb:
    def __init__(self, route=None, note=None, saved_lead=None):
        self._route = route
        self._note = note
        self._saved_lead = saved_lead

    async def get(self, model, _id):  # pragma: no cover - tiny helper
        return self._route

    async def execute(self, query):
        query_text = str(query)
        if "FROM note" in query_text:
            return _FakeScalarResult(self._note)
        if "FROM saved_lead" in query_text:
            return _FakeScalarResult(self._saved_lead)
        return _FakeScalarResult(self._route)

    async def commit(self):  # pragma: no cover
        return None

    async def refresh(self, _obj):  # pragma: no cover
        return None


@pytest.mark.asyncio
async def test_cross_user_route_access_denied(monkeypatch):
    monkeypatch.setattr(leads_routes, "enforce_rate_limit", lambda *args, **kwargs: _noop_async())
    user = User(id=uuid.uuid4(), email="owner@example.com")
    other_user = uuid.uuid4()
    route = SimpleNamespace(id=uuid.uuid4(), user_id=other_user)
    db = _FakeDb(route=route)

    with pytest.raises(HTTPException) as exc:
        await leads_routes.get_route_leads(route.id, user=user, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_cross_user_saved_lead_patch_denied(monkeypatch):
    monkeypatch.setattr(saved_leads_routes, "enforce_rate_limit", lambda *args, **kwargs: _noop_async())
    user = User(id=uuid.uuid4(), email="owner@example.com")
    db = _FakeDb(saved_lead=None)

    with pytest.raises(HTTPException) as exc:
        await saved_leads_routes.update_saved_lead(
            uuid.uuid4(),
            UpdateSavedLeadRequest(status="called"),
            user=user,
            db=db,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_cross_user_note_patch_denied():
    user = User(id=uuid.uuid4(), email="owner@example.com")
    db = _FakeDb(note=None)
    with pytest.raises(HTTPException) as exc:
        await notes_routes.update_note(
            uuid.uuid4(),
            UpdateNoteRequest(note_text="x"),
            user=user,
            db=db,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_cross_user_export_denied(monkeypatch):
    monkeypatch.setattr(export_routes, "enforce_rate_limit", lambda *args, **kwargs: _noop_async())
    user = User(id=uuid.uuid4(), email="owner@example.com")
    route = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    db = _FakeDb(route=route)

    resp = await export_routes.export_route_leads_csv(route.id, user=user, db=db)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_jwt_invalid_signature_rejected(monkeypatch):
    settings = get_settings()
    original = (
        settings.environment,
        settings.clerk_jwks_url,
        settings.clerk_jwt_issuer,
    )
    settings.environment = "production"
    settings.clerk_jwks_url = "https://example.test/jwks"
    settings.clerk_jwt_issuer = "https://issuer.test"
    monkeypatch.setattr(
        auth_core,
        "_verify_token_signature",
        _raise_401_async,
    )
    try:
        with pytest.raises(HTTPException) as exc:
            await auth_core.get_current_user(authorization="Bearer x.y.z", db=SimpleNamespace())
        assert exc.value.status_code == 401
    finally:
        settings.environment, settings.clerk_jwks_url, settings.clerk_jwt_issuer = original


@pytest.mark.asyncio
async def test_jwt_wrong_issuer_rejected(monkeypatch):
    settings = get_settings()
    original = (settings.environment, settings.clerk_jwt_issuer)
    settings.environment = "test"
    settings.clerk_jwt_issuer = "https://good-issuer.test"
    monkeypatch.setattr(auth_core.jwt, "get_unverified_claims", lambda _t: {"iss": "https://wrong.test", "sub": "abc"})
    try:
        with pytest.raises(HTTPException) as exc:
            await auth_core.get_current_user(authorization="Bearer any", db=SimpleNamespace())
        assert exc.value.status_code == 401
    finally:
        settings.environment, settings.clerk_jwt_issuer = original


@pytest.mark.asyncio
async def test_jwt_expired_rejected(monkeypatch):
    settings = get_settings()
    original = settings.environment
    settings.environment = "test"
    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    monkeypatch.setattr(auth_core.jwt, "get_unverified_claims", lambda _t: {"iss": "", "sub": "abc", "exp": expired.timestamp()})
    try:
        with pytest.raises(HTTPException) as exc:
            await auth_core.get_current_user(authorization="Bearer any", db=SimpleNamespace())
        assert exc.value.status_code == 401
    finally:
        settings.environment = original


@pytest.mark.asyncio
async def test_startup_rejects_insecure_tls_in_production(monkeypatch):
    settings = get_settings()
    original = _snapshot_settings(settings)
    settings.environment = "production"
    settings.poc_mode = False
    settings.clerk_jwks_url = "https://example.test/jwks"
    settings.clerk_jwt_issuer = "https://issuer.test"
    settings.database_tls_emergency_insecure_override = False
    monkeypatch.setattr("app.main.is_db_tls_config_secure", lambda: False)
    try:
        with pytest.raises(RuntimeError):
            await startup()
    finally:
        _restore_settings(settings, original)


@pytest.mark.asyncio
async def test_startup_rejects_missing_jwks_url_in_production(monkeypatch):
    settings = get_settings()
    original = _snapshot_settings(settings)
    settings.environment = "production"
    settings.poc_mode = False
    settings.clerk_jwks_url = ""
    settings.clerk_jwt_issuer = "https://issuer.test"
    settings.database_tls_emergency_insecure_override = False
    monkeypatch.setattr("app.main.is_db_tls_config_secure", lambda: True)
    try:
        with pytest.raises(RuntimeError, match="CLERK_JWKS_URL"):
            await startup()
    finally:
        _restore_settings(settings, original)


@pytest.mark.asyncio
async def test_startup_rejects_missing_jwt_issuer_in_production(monkeypatch):
    settings = get_settings()
    original = _snapshot_settings(settings)
    settings.environment = "production"
    settings.poc_mode = False
    settings.clerk_jwks_url = "https://example.test/jwks"
    settings.clerk_jwt_issuer = ""
    settings.database_tls_emergency_insecure_override = False
    monkeypatch.setattr("app.main.is_db_tls_config_secure", lambda: True)
    try:
        with pytest.raises(RuntimeError, match="CLERK_JWT_ISSUER"):
            await startup()
    finally:
        _restore_settings(settings, original)


@pytest.mark.asyncio
async def test_startup_allows_emergency_tls_override_before_sunset(monkeypatch):
    settings = get_settings()
    original = _snapshot_settings(settings)
    settings.environment = "production"
    settings.poc_mode = False
    settings.clerk_jwks_url = "https://example.test/jwks"
    settings.clerk_jwt_issuer = "https://issuer.test"
    settings.database_tls_emergency_insecure_override = True
    settings.database_tls_emergency_override_sunset = date.today() + timedelta(days=10)
    monkeypatch.setattr("app.main.is_db_tls_config_secure", lambda: False)
    try:
        await startup()
    finally:
        _restore_settings(settings, original)


@pytest.mark.asyncio
async def test_startup_rejects_emergency_override_after_sunset(monkeypatch):
    settings = get_settings()
    original = _snapshot_settings(settings)
    settings.environment = "production"
    settings.poc_mode = False
    settings.clerk_jwks_url = "https://example.test/jwks"
    settings.clerk_jwt_issuer = "https://issuer.test"
    settings.database_tls_emergency_insecure_override = True
    settings.database_tls_emergency_override_sunset = date.today() - timedelta(days=1)
    monkeypatch.setattr("app.main.is_db_tls_config_secure", lambda: False)
    try:
        with pytest.raises(RuntimeError):
            await startup()
    finally:
        _restore_settings(settings, original)


async def _noop_async():
    return None


async def _raise_401_async(*_args, **_kwargs):
    raise HTTPException(status_code=401, detail="Invalid token signature")


def _snapshot_settings(settings):
    return {
        "environment": settings.environment,
        "poc_mode": settings.poc_mode,
        "clerk_jwks_url": settings.clerk_jwks_url,
        "clerk_jwt_issuer": settings.clerk_jwt_issuer,
        "database_tls_emergency_insecure_override": settings.database_tls_emergency_insecure_override,
        "database_tls_emergency_override_sunset": settings.database_tls_emergency_override_sunset,
        "validation_hmac_secret": settings.validation_hmac_secret,
        "cors_allow_origin_regex": settings.cors_allow_origin_regex,
    }


def _restore_settings(settings, values):
    settings.environment = values["environment"]
    settings.poc_mode = values["poc_mode"]
    settings.clerk_jwks_url = values["clerk_jwks_url"]
    settings.clerk_jwt_issuer = values["clerk_jwt_issuer"]
    settings.database_tls_emergency_insecure_override = values["database_tls_emergency_insecure_override"]
    settings.database_tls_emergency_override_sunset = values["database_tls_emergency_override_sunset"]
    settings.validation_hmac_secret = values["validation_hmac_secret"]
    settings.cors_allow_origin_regex = values["cors_allow_origin_regex"]


@pytest.mark.asyncio
async def test_startup_rejects_missing_hmac_secret_in_production(monkeypatch):
    settings = get_settings()
    original = _snapshot_settings(settings)
    settings.environment = "production"
    settings.poc_mode = False
    settings.clerk_jwks_url = "https://example.test/jwks"
    settings.clerk_jwt_issuer = "https://issuer.test"
    settings.validation_hmac_secret = ""
    settings.database_tls_emergency_insecure_override = False
    monkeypatch.setattr("app.main.is_db_tls_config_secure", lambda: True)
    monkeypatch.setattr("app.main.cors_origin_regex", None)
    try:
        with pytest.raises(RuntimeError, match="VALIDATION_HMAC_SECRET"):
            await startup()
    finally:
        _restore_settings(settings, original)


@pytest.mark.asyncio
async def test_startup_rejects_invalid_cors_regex(monkeypatch):
    settings = get_settings()
    original = _snapshot_settings(settings)
    settings.environment = "development"
    settings.poc_mode = False
    settings.validation_hmac_secret = "secret"
    monkeypatch.setattr("app.main.is_db_tls_config_secure", lambda: True)
    # Inject an invalid regex via the module-level variable that startup() reads
    monkeypatch.setattr("app.main.cors_origin_regex", "[invalid(regex")
    try:
        with pytest.raises(RuntimeError, match="CORS_ALLOW_ORIGIN_REGEX"):
            await startup()
    finally:
        _restore_settings(settings, original)
