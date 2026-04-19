from __future__ import annotations

import math
from datetime import datetime, timezone


FIT_SCORES = {
    "Auto Service": 95,
    "Contractor / Trades": 90,
    "Retail": 85,
    "Food & Beverage": 75,
    "Personal Services": 75,
    "Medical / Clinic": 70,
    "Professional / Office": 65,
    "Light Industrial": 55,
    "Other Commercial": 40,
    "Exclude": 5,
}


def clamp_score(value: float) -> int:
    return max(0, min(int(round(value)), 100))


def normalize_geo_key(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized or "global"


def distance_band(meters: float) -> str:
    if meters <= 750:
        return "near"
    if meters <= 1500:
        return "mid"
    return "far"


def distance_score(meters: float) -> int:
    if meters <= 250:
        return 100
    if meters <= 750:
        return 80
    if meters <= 1500:
        return 60
    if meters <= 3000:
        return 35
    return 10


def distance_score_v2(meters: float) -> int:
    # Smooth exponential decay to avoid bucket cliffs.
    return clamp_score(100 * math.exp(-meters / 1400.0))


def actionability_score(has_address: bool, has_phone: bool, has_website: bool, confidence: float | None) -> int:
    base = 10
    if has_address:
        base += 40
    if has_phone:
        base += 25
    if has_website:
        base += 25
    if confidence is not None and confidence < 0.7:
        base = int(base * max(confidence, 0.5))
    return min(base, 100)


def actionability_score_v2(
    *,
    has_address: bool,
    has_phone: bool,
    has_website: bool,
    confidence: float | None,
    validation_confidence: float | None,
    last_seen_at: datetime | None,
    invalid_field_count: int,
    hard_failure_count: int,
) -> int:
    raw_score = 20.0
    if has_address:
        raw_score += 25
    if has_phone:
        raw_score += 20
    if has_website:
        raw_score += 20
    if confidence is not None:
        raw_score += 15 * max(min(confidence, 1.0), 0.0)
    if validation_confidence is not None:
        raw_score += 20 * max(min(validation_confidence / 100.0, 1.0), 0.0)
    if last_seen_at:
        age_days = max((datetime.now(timezone.utc) - last_seen_at).days, 0)
        freshness = max(0.5, 1.0 - (age_days / 180.0))
        raw_score *= freshness
    score = clamp_score(raw_score)
    # Penalize leads with repeated invalid/hard validation failures.
    score -= min(20.0, (max(invalid_field_count, 0) * 3.5) + (max(hard_failure_count, 0) * 6.0))
    return clamp_score(score)


def fit_score_v2(
    insurance_class: str | None,
    confidence: float | None,
    validation_confidence: float | None,
    name: str | None,
    is_blue_collar: bool = False,
) -> int:
    base = float(FIT_SCORES.get(insurance_class or "Other Commercial", 40))
    if insurance_class == "Exclude":
        return 0
    if confidence is not None:
        base = base * (0.85 + (0.15 * max(min(confidence, 1.0), 0.0)))
    if validation_confidence is not None:
        base = base * (0.9 + 0.1 * max(min(validation_confidence / 100.0, 1.0), 0.0))
    base = max(base - name_quality_penalty(name), 0.0)
    if is_blue_collar:
        base = min(base + 5.0, 100.0)
    return clamp_score(base)


def name_quality_penalty(name: str | None) -> float:
    normalized = " ".join((name or "").strip().split())
    if not normalized:
        return 12.0
    lowered = normalized.lower()
    generic_only = {
        "llc",
        "inc",
        "corp",
        "co",
        "company",
        "business",
        "services",
        "solutions",
        "group",
        "holdings",
    }
    tokens = [t for t in lowered.replace(".", " ").split() if t]
    if tokens and all(token in generic_only for token in tokens):
        return 10.0
    # Mostly numeric or too short names are often weak-quality records.
    alnum = "".join(ch for ch in normalized if ch.isalnum())
    if len(alnum) < 4:
        return 8.0
    digit_ratio = (sum(ch.isdigit() for ch in alnum) / len(alnum)) if alnum else 0.0
    if digit_ratio >= 0.45:
        return 6.0
    return 0.0


def explain(insurance_class: str | None, fit: int, distance_m: float, has_phone: bool, has_website: bool) -> dict:
    fit_label = "Strong" if fit >= 85 else "Good" if fit >= 70 else "Moderate"
    distance_label = "Very close" if distance_m <= 250 else "Close" if distance_m <= 750 else "Moderate distance"

    if has_phone and has_website:
        actionability = "Has phone and website"
    elif has_phone:
        actionability = "Has phone"
    elif has_website:
        actionability = "Has website"
    else:
        actionability = "Limited contact detail"

    return {
        "fit": f"{fit_label} fit: {insurance_class or 'Unknown'}",
        "distance": f"{distance_label} ({int(distance_m)}m from route)",
        "actionability": actionability,
    }


def feedback_score_v2(
    *,
    geo_key: str | None = None,
    insurance_class: str | None,
    has_phone: bool,
    has_website: bool,
    distance_m: float,
    priors: dict,
    smoothing: int,
    min_samples: int,
) -> int:
    return feedback_signal_v2(
        geo_key=geo_key,
        insurance_class=insurance_class,
        has_phone=has_phone,
        has_website=has_website,
        distance_m=distance_m,
        priors=priors,
        smoothing=smoothing,
        min_samples=min_samples,
    )["score"]


def feedback_signal_v2(
    *,
    geo_key: str | None = None,
    insurance_class: str | None,
    has_phone: bool,
    has_website: bool,
    distance_m: float,
    priors: dict,
    smoothing: int,
    min_samples: int,
) -> dict:
    band = distance_band(distance_m)
    normalized_geo = normalize_geo_key(geo_key)
    segment_key_local = (normalized_geo, insurance_class, has_phone, has_website, band)
    segment_key_global = ("global", insurance_class, has_phone, has_website, band)
    segment = priors.get("segments", {}).get(segment_key_local) or priors.get("segments", {}).get(segment_key_global)
    globals_by_geo = priors.get("globals_by_geo", {})
    global_prior = globals_by_geo.get(normalized_geo) or priors.get("global", {"prior_save": 0.20, "prior_contact": 0.08, "sample_size": 0})

    if not segment or int(segment.get("sample_size", 0)) < min_samples:
        blended_save = float(global_prior.get("prior_save", 0.20))
        blended_contact = float(global_prior.get("prior_contact", 0.08))
        sample_size = int(global_prior.get("sample_size", 0))
    else:
        n = int(segment.get("sample_size", 0))
        k = max(int(smoothing), 1)
        seg_save = float(segment.get("prior_save", global_prior.get("prior_save", 0.20)))
        seg_contact = float(segment.get("prior_contact", global_prior.get("prior_contact", 0.08)))
        g_save = float(global_prior.get("prior_save", 0.20))
        g_contact = float(global_prior.get("prior_contact", 0.08))
        blended_save = ((n * seg_save) + (k * g_save)) / (n + k)
        blended_contact = ((n * seg_contact) + (k * g_contact)) / (n + k)
        sample_size = n

    score = clamp_score(((blended_save * 0.6) + (blended_contact * 0.4)) * 100.0)
    return {"score": score, "sample_size": sample_size, "geo_key": normalized_geo}


def score_weights_v2(feedback_sample_size: int) -> tuple[float, float, float, float]:
    # Increase feedback influence only when there's enough historical evidence.
    evidence_ratio = max(0.0, min(float(feedback_sample_size) / 200.0, 1.0))
    feedback_w = 0.12 + (0.13 * evidence_ratio)
    remaining = 1.0 - feedback_w
    fit_w = remaining * 0.45
    distance_w = remaining * 0.30
    action_w = remaining * 0.25
    return fit_w, distance_w, action_w, feedback_w


def score_candidate(candidate: dict) -> dict:
    fit = FIT_SCORES.get(candidate.get("insurance_class") or "Other Commercial", 40)
    if candidate.get("is_blue_collar"):
        fit = min(fit + 5, 100)
    dist = distance_score(float(candidate["distance_from_route_m"]))
    act = actionability_score(
        has_address=bool(candidate.get("has_address")),
        has_phone=bool(candidate.get("has_phone")),
        has_website=bool(candidate.get("has_website")),
        confidence=float(candidate["confidence_score"]) if candidate.get("confidence_score") is not None else None,
    )
    final = round(fit * 0.4 + dist * 0.3 + act * 0.3)
    return {
        "fit_score": fit,
        "distance_score": dist,
        "actionability_score": act,
        "final_score": final,
        "explanation": explain(
            insurance_class=candidate.get("insurance_class"),
            fit=fit,
            distance_m=float(candidate["distance_from_route_m"]),
            has_phone=bool(candidate.get("has_phone")),
            has_website=bool(candidate.get("has_website")),
        ),
    }


def score_candidate_v2(
    candidate: dict,
    *,
    priors: dict,
    smoothing: int,
    min_segment_samples: int,
    calibration_version: str,
) -> dict:
    confidence = float(candidate["confidence_score"]) if candidate.get("confidence_score") is not None else None
    validation_confidence = (
        float(candidate["validation_confidence"]) if candidate.get("validation_confidence") is not None else None
    )
    distance_m = float(candidate["distance_from_route_m"])
    geo_key = normalize_geo_key(candidate.get("state"))
    invalid_field_count = int(candidate.get("invalid_field_count") or 0)
    hard_failure_count = int(candidate.get("hard_failure_count") or 0)
    fit = fit_score_v2(
        insurance_class=candidate.get("insurance_class"),
        confidence=confidence,
        validation_confidence=validation_confidence,
        name=candidate.get("name"),
        is_blue_collar=bool(candidate.get("is_blue_collar")),
    )
    dist = distance_score_v2(distance_m)
    act = actionability_score_v2(
        has_address=bool(candidate.get("has_address")),
        has_phone=bool(candidate.get("has_phone")),
        has_website=bool(candidate.get("has_website")),
        confidence=confidence,
        validation_confidence=validation_confidence,
        last_seen_at=candidate.get("last_seen_at"),
        invalid_field_count=invalid_field_count,
        hard_failure_count=hard_failure_count,
    )
    feedback_signal = feedback_signal_v2(
        geo_key=geo_key,
        insurance_class=candidate.get("insurance_class"),
        has_phone=bool(candidate.get("has_phone")),
        has_website=bool(candidate.get("has_website")),
        distance_m=distance_m,
        priors=priors,
        smoothing=smoothing,
        min_samples=min_segment_samples,
    )
    feedback = feedback_signal["score"]
    fit_w, dist_w, act_w, feedback_w = score_weights_v2(int(feedback_signal["sample_size"]))
    final = clamp_score((fit * fit_w) + (dist * dist_w) + (act * act_w) + (feedback * feedback_w))

    rank_reasons: list[str] = []
    if candidate.get("is_blue_collar"):
        rank_reasons.append("Blue collar fit")
    if fit >= 80:
        rank_reasons.append("Strong class fit")
    if dist >= 70:
        rank_reasons.append("Close to route")
    if act >= 70:
        rank_reasons.append("High contactability")
    if feedback >= 65:
        rank_reasons.append("Historically strong outcomes for similar leads")
    if invalid_field_count > 0 or hard_failure_count > 0:
        rank_reasons.append("Quality penalties applied from validation failures")

    explanation = explain(
        insurance_class=candidate.get("insurance_class"),
        fit=fit,
        distance_m=distance_m,
        has_phone=bool(candidate.get("has_phone")),
        has_website=bool(candidate.get("has_website")),
    )
    explanation["actionability"] = f"{explanation['actionability']} (v2 calibrated)"

    return {
        "fit_score_v2": fit,
        "distance_score_v2": dist,
        "actionability_score_v2": act,
        "feedback_score_v2": feedback,
        "final_score_v2": final,
        "calibration_version": calibration_version,
        "explanation_v2": {
            **explanation,
            "rank_reason_v2": rank_reasons,
        },
    }
