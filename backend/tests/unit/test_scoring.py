from datetime import datetime, timedelta, timezone

from app.services.scoring_service import (
    actionability_score,
    clamp_score,
    distance_score,
    distance_score_v2,
    feedback_score_v2,
    score_candidate,
    score_candidate_v2,
)


def test_distance_score_buckets() -> None:
    assert distance_score(100) == 100
    assert distance_score(500) == 80
    assert distance_score(1200) == 60
    assert distance_score(2500) == 35
    assert distance_score(3500) == 10


def test_actionability_with_confidence_modifier() -> None:
    raw = actionability_score(has_address=True, has_phone=True, has_website=False, confidence=0.6)
    assert raw < 100
    assert raw >= 30


def test_score_candidate_shape() -> None:
    scored = score_candidate(
        {
            "insurance_class": "Auto Service",
            "distance_from_route_m": 220,
            "has_address": True,
            "has_phone": True,
            "has_website": True,
            "confidence_score": 0.95,
        }
    )
    assert scored["final_score"] >= 80
    assert "fit" in scored["explanation"]


def test_clamp_score_bounds() -> None:
    assert clamp_score(-3.2) == 0
    assert clamp_score(500.0) == 100
    assert clamp_score(67.49) == 67


def test_distance_score_v2_smooth_decay() -> None:
    near = distance_score_v2(100)
    mid = distance_score_v2(1200)
    far = distance_score_v2(3200)
    assert near > mid > far
    assert 0 <= far <= 100


def test_feedback_score_v2_falls_back_to_global_under_min_samples() -> None:
    priors = {
        "global": {"prior_save": 0.40, "prior_contact": 0.20, "sample_size": 1000},
        "segments": {
            ("Auto Service", True, True, "near"): {"prior_save": 1.0, "prior_contact": 1.0, "sample_size": 3}
        },
    }
    score = feedback_score_v2(
        insurance_class="Auto Service",
        has_phone=True,
        has_website=True,
        distance_m=200,
        priors=priors,
        smoothing=20,
        min_samples=25,
    )
    assert score == 32


def test_score_candidate_v2_deterministic_and_explained() -> None:
    candidate = {
        "insurance_class": "Auto Service",
        "distance_from_route_m": 300,
        "has_address": True,
        "has_phone": True,
        "has_website": True,
        "confidence_score": 0.95,
        "validation_confidence": 88,
        "last_seen_at": datetime.now(timezone.utc) - timedelta(days=10),
    }
    priors = {
        "global": {"prior_save": 0.30, "prior_contact": 0.15, "sample_size": 100},
        "segments": {
            ("Auto Service", True, True, "near"): {"prior_save": 0.42, "prior_contact": 0.21, "sample_size": 80}
        },
    }
    first = score_candidate_v2(
        candidate,
        priors=priors,
        smoothing=20,
        min_segment_samples=25,
        calibration_version="v2-default",
    )
    second = score_candidate_v2(
        candidate,
        priors=priors,
        smoothing=20,
        min_segment_samples=25,
        calibration_version="v2-default",
    )

    assert first == second
    assert 0 <= first["fit_score_v2"] <= 100
    assert 0 <= first["distance_score_v2"] <= 100
    assert 0 <= first["actionability_score_v2"] <= 100
    assert 0 <= first["feedback_score_v2"] <= 100
    assert 0 <= first["final_score_v2"] <= 100
    assert first["explanation_v2"]["fit"]
    assert first["explanation_v2"]["distance"]
    assert first["explanation_v2"]["actionability"]
