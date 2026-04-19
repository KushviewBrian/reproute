from types import SimpleNamespace

from app.services import lead_service


def _settings(**overrides):
    base = {
        "scoring_force_version": "",
        "scoring_v2_enabled": False,
        "scoring_v2_shadow_enabled": True,
        "scoring_default_version": "v1",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_resolve_score_version_defaults_to_v1(monkeypatch) -> None:
    monkeypatch.setattr(lead_service, "get_settings", lambda: _settings())
    assert lead_service.resolve_score_version(None) == "v1"


def test_resolve_score_version_allows_v2_request_in_shadow(monkeypatch) -> None:
    monkeypatch.setattr(lead_service, "get_settings", lambda: _settings(scoring_v2_shadow_enabled=True))
    assert lead_service.resolve_score_version("v2") == "v2"


def test_resolve_score_version_blocks_v2_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        lead_service,
        "get_settings",
        lambda: _settings(scoring_v2_enabled=False, scoring_v2_shadow_enabled=False),
    )
    assert lead_service.resolve_score_version("v2") == "v1"


def test_resolve_score_version_forced_v1_wins(monkeypatch) -> None:
    monkeypatch.setattr(lead_service, "get_settings", lambda: _settings(scoring_force_version="v1"))
    assert lead_service.resolve_score_version("v2") == "v1"


def test_resolve_score_version_forced_v2_requires_enable(monkeypatch) -> None:
    monkeypatch.setattr(
        lead_service,
        "get_settings",
        lambda: _settings(scoring_force_version="v2", scoring_v2_enabled=False),
    )
    assert lead_service.resolve_score_version(None) == "v1"

    monkeypatch.setattr(
        lead_service,
        "get_settings",
        lambda: _settings(scoring_force_version="v2", scoring_v2_enabled=True),
    )
    assert lead_service.resolve_score_version(None) == "v2"


def test_resolve_score_version_default_v2_requires_enable(monkeypatch) -> None:
    monkeypatch.setattr(
        lead_service,
        "get_settings",
        lambda: _settings(scoring_default_version="v2", scoring_v2_enabled=False),
    )
    assert lead_service.resolve_score_version(None) == "v1"

    monkeypatch.setattr(
        lead_service,
        "get_settings",
        lambda: _settings(scoring_default_version="v2", scoring_v2_enabled=True),
    )
    assert lead_service.resolve_score_version(None) == "v2"
