from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import admin_import
from app.core.config import get_settings


def _snapshot_settings(settings):
    return {
        "environment": settings.environment,
        "admin_import_secret": settings.admin_import_secret,
        "admin_allowed_emails": settings.admin_allowed_emails,
        "admin_import_allowed_roots": settings.admin_import_allowed_roots,
        "ingest_database_url": settings.ingest_database_url,
        "database_url": settings.database_url,
    }


def _restore_settings(settings, values):
    settings.environment = values["environment"]
    settings.admin_import_secret = values["admin_import_secret"]
    settings.admin_allowed_emails = values["admin_allowed_emails"]
    settings.admin_import_allowed_roots = values["admin_import_allowed_roots"]
    settings.ingest_database_url = values["ingest_database_url"]
    settings.database_url = values["database_url"]


def test_require_admin_secret_rejects_missing_secret_in_production() -> None:
    settings = get_settings()
    original = _snapshot_settings(settings)
    settings.environment = "production"
    settings.admin_import_secret = ""
    try:
        with pytest.raises(HTTPException) as exc:
            admin_import._require_admin_secret(None)
        assert exc.value.status_code == 503
    finally:
        _restore_settings(settings, original)


def test_require_admin_email_enforces_allowlist() -> None:
    settings = get_settings()
    original = _snapshot_settings(settings)
    settings.environment = "production"
    settings.admin_allowed_emails = "allowed@example.com"
    try:
        with pytest.raises(HTTPException) as exc:
            admin_import._require_admin_email(SimpleNamespace(email="blocked@example.com"))
        assert exc.value.status_code == 403
    finally:
        _restore_settings(settings, original)


def test_validate_parquet_path_blocks_outside_allowlisted_root(tmp_path: Path) -> None:
    settings = get_settings()
    original = _snapshot_settings(settings)
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside.parquet"
    outside.write_text("data", encoding="utf-8")
    settings.environment = "production"
    settings.admin_import_allowed_roots = str(allowed_root)
    try:
        with pytest.raises(HTTPException) as exc:
            admin_import._validate_parquet_path(str(outside))
        assert exc.value.status_code == 403
    finally:
        _restore_settings(settings, original)


def test_validate_parquet_path_allows_resolved_path_inside_root(tmp_path: Path) -> None:
    settings = get_settings()
    original = _snapshot_settings(settings)
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir(parents=True, exist_ok=True)
    nested = allowed_root / "subdir" / "file.parquet"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("x", encoding="utf-8")
    settings.environment = "production"
    settings.admin_import_allowed_roots = str(allowed_root)
    try:
        resolved = admin_import._validate_parquet_path(str(nested))
        assert resolved == str(nested.resolve())
    finally:
        _restore_settings(settings, original)


def test_sync_database_url_prefers_payload_and_converts_asyncpg_scheme() -> None:
    settings = get_settings()
    original = _snapshot_settings(settings)
    settings.ingest_database_url = ""
    settings.database_url = "postgresql+asyncpg://db_default"
    try:
        out = admin_import._sync_database_url("postgresql+asyncpg://db_payload")
        assert out == "postgresql+psycopg://db_payload"
    finally:
        _restore_settings(settings, original)
