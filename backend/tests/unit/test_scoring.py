from app.services.scoring_service import actionability_score, distance_score, score_candidate


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
