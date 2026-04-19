from datetime import datetime, timedelta, timezone

from app.services.scoring_service import (
    actionability_score,
    actionability_score_v2,
    clamp_score,
    distance_score,
    distance_score_v2,
    feedback_score_v2,
    feedback_signal_v2,
    name_quality_penalty,
    score_candidate,
    score_candidate_v2,
    score_weights_v2,
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


def test_feedback_signal_prefers_geo_specific_prior() -> None:
    priors = {
        "global": {"prior_save": 0.20, "prior_contact": 0.10, "sample_size": 500},
        "globals_by_geo": {
            "ca": {"prior_save": 0.50, "prior_contact": 0.20, "sample_size": 220},
            "global": {"prior_save": 0.20, "prior_contact": 0.10, "sample_size": 500},
        },
        "segments": {},
    }
    signal = feedback_signal_v2(
        geo_key="CA",
        insurance_class="Retail",
        has_phone=True,
        has_website=True,
        distance_m=500,
        priors=priors,
        smoothing=20,
        min_samples=25,
    )
    assert signal["geo_key"] == "ca"
    assert signal["score"] == 38


def test_name_quality_penalty_hits_weak_names() -> None:
    assert name_quality_penalty("LLC INC") >= 8
    assert name_quality_penalty("A1") >= 6
    assert name_quality_penalty("Acme Auto Service") == 0


def test_actionability_v2_applies_validation_failure_penalty() -> None:
    high = actionability_score_v2(
        has_address=True,
        has_phone=True,
        has_website=True,
        confidence=0.9,
        validation_confidence=90.0,
        last_seen_at=datetime.now(timezone.utc) - timedelta(days=5),
        invalid_field_count=0,
        hard_failure_count=0,
    )
    penalized = actionability_score_v2(
        has_address=True,
        has_phone=True,
        has_website=True,
        confidence=0.9,
        validation_confidence=90.0,
        last_seen_at=datetime.now(timezone.utc) - timedelta(days=5),
        invalid_field_count=2,
        hard_failure_count=1,
    )
    assert high > penalized


def test_adaptive_weights_shift_toward_feedback_with_more_data() -> None:
    low = score_weights_v2(0)
    high = score_weights_v2(400)
    assert high[3] > low[3]
    assert abs(sum(low) - 1.0) < 1e-9
    assert abs(sum(high) - 1.0) < 1e-9


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
