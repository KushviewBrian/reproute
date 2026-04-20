from fastapi.testclient import TestClient
from starlette.responses import Response

from app.core.config import get_settings
from app.main import _apply_security_headers, app


def test_security_headers_are_present() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_gzip_middleware_is_registered() -> None:
    assert any(middleware.cls.__name__ == "GZipMiddleware" for middleware in app.user_middleware)


def test_hsts_header_in_production_mode() -> None:
    settings = get_settings()
    original_environment = settings.environment
    settings.environment = "production"
    try:
        response = _apply_security_headers(Response())
        assert response.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"
    finally:
        settings.environment = original_environment


def test_request_body_limit_enforced() -> None:
    settings = get_settings()
    original_limit = settings.request_body_limit_bytes
    settings.request_body_limit_bytes = 16
    try:
        client = TestClient(app)
        response = client.post("/", content="x" * 32)
        assert response.status_code == 413
        assert response.json().get("detail") == "Request body too large"
    finally:
        settings.request_body_limit_bytes = original_limit


def test_audit_log_emitted_for_auth_denied_mutation(caplog) -> None:
    client = TestClient(app)
    caplog.set_level("INFO")
    response = client.post("/routes", json={})
    assert response.status_code in {401, 422}
    assert any("audit_event" in record.getMessage() and "path=/routes" in record.getMessage() for record in caplog.records)


def test_audit_log_skips_health_endpoint(caplog) -> None:
    client = TestClient(app)
    caplog.set_level("INFO")
    response = client.get("/health")
    assert response.status_code == 200
    assert not any("audit_event" in record.getMessage() and "path=/health" in record.getMessage() for record in caplog.records)
