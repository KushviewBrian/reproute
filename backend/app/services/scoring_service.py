from __future__ import annotations


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


def score_candidate(candidate: dict) -> dict:
    fit = FIT_SCORES.get(candidate.get("insurance_class") or "Other Commercial", 40)
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
