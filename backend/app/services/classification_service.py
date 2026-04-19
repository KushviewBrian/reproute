from __future__ import annotations


BLUE_COLLAR_CLASSES = frozenset({"Auto Service", "Contractor / Trades", "Personal Services"})

BASIC_CATEGORY_MAP = {
    "restaurant": "Food & Beverage",
    "bar": "Food & Beverage",
    "cafe": "Food & Beverage",
    "bakery": "Food & Beverage",
    "auto_repair": "Auto Service",
    "car_wash": "Auto Service",
    "tire_shop": "Auto Service",
    "beauty_salon": "Personal Services",
    "barber": "Personal Services",
    "nail_salon": "Personal Services",
    "dry_cleaning": "Personal Services",
    "lawyer": "Professional / Office",
    "accountant": "Professional / Office",
    "insurance_agency": "Professional / Office",
    "real_estate_agent": "Professional / Office",
    "plumber": "Contractor / Trades",
    "electrician": "Contractor / Trades",
    "hvac": "Contractor / Trades",
    "roofing_contractor": "Contractor / Trades",
    "dentist": "Medical / Clinic",
    "optometrist": "Medical / Clinic",
    "chiropractor": "Medical / Clinic",
    "physical_therapist": "Medical / Clinic",
    "gas_station": "Exclude",
    "hospital": "Exclude",
    "school": "Exclude",
    "place_of_worship": "Exclude",
    "park": "Exclude",
    "government_office": "Exclude",
}

HIERARCHY_TOKEN_MAP = [
    ("eat_and_drink", "Food & Beverage"),
    ("automotive", "Auto Service"),
    ("personal_care", "Personal Services"),
    ("professional_services", "Professional / Office"),
    ("financial_services", "Professional / Office"),
    ("legal_services", "Professional / Office"),
    ("real_estate", "Professional / Office"),
    ("home_improvement", "Contractor / Trades"),
    ("construction", "Contractor / Trades"),
    ("health_and_medical", "Medical / Clinic"),
    ("retail", "Retail"),
    ("education", "Exclude"),
    ("government_and_community", "Exclude"),
    ("parks_outdoors", "Exclude"),
    ("religious", "Exclude"),
]

# Multi-word keywords must come before single-word prefixes that overlap.
NAME_KEYWORDS: list[tuple[str, str]] = [
    ("pressure wash", "Personal Services"),
    ("plumbing", "Contractor / Trades"),
    ("hvac", "Contractor / Trades"),
    ("electric", "Contractor / Trades"),
    ("roofing", "Contractor / Trades"),
    ("weld", "Contractor / Trades"),
    ("fabricat", "Contractor / Trades"),
    ("auto detail", "Auto Service"),
    ("auto glass", "Auto Service"),
    ("auto", "Auto Service"),
    ("detail", "Auto Service"),
    ("repair", "Auto Service"),
    ("tow", "Auto Service"),
    ("restaurant", "Food & Beverage"),
    ("cafe", "Food & Beverage"),
    ("salon", "Personal Services"),
    ("barber", "Personal Services"),
    ("pest", "Personal Services"),
    ("lawn", "Personal Services"),
    ("landscape", "Personal Services"),
    ("painting contractor", "Personal Services"),
    ("paint", "Personal Services"),
    ("cleaning service", "Personal Services"),
    ("clean", "Personal Services"),
    ("locksmith", "Personal Services"),
    ("lock", "Personal Services"),
    ("dental", "Medical / Clinic"),
    ("clinic", "Medical / Clinic"),
    ("law", "Professional / Office"),
    ("accounting", "Professional / Office"),
]


def classify(
    basic_category: str | None,
    taxonomy_hierarchy: list[str] | None,
    name: str | None,
) -> tuple[str, bool]:
    """Return (insurance_class, is_blue_collar)."""
    insurance_class = _classify_class(basic_category, taxonomy_hierarchy, name)
    return insurance_class, insurance_class in BLUE_COLLAR_CLASSES


def _classify_class(
    basic_category: str | None,
    taxonomy_hierarchy: list[str] | None,
    name: str | None,
) -> str:
    if basic_category:
        mapped = BASIC_CATEGORY_MAP.get(basic_category)
        if mapped:
            return mapped

    if taxonomy_hierarchy:
        lower = [token.lower() for token in taxonomy_hierarchy]
        for token, insurance_class in HIERARCHY_TOKEN_MAP:
            if token in lower:
                return insurance_class

    if name:
        n = name.lower()
        for keyword, insurance_class in NAME_KEYWORDS:
            if keyword in n:
                return insurance_class

    return "Other Commercial"
