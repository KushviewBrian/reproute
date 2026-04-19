# Phase 10 — Lead Intelligence Spec
## Sorting, Grouping, Blue-Collar Category, and Owner Contact

**Status:** Planning  
**Roadmap phase:** 10  
**Blocking dependencies:** Phase 9 complete (or in sustained pilot with stable data); Phase 5 validation system active  
**Supporting migration:** `alembic/versions/0006_blue_collar_and_owner_contact.py`

---

## 1. Purpose and Scope

This spec covers the full design for Phase 10. It is the source of truth for implementation details that are summarized in the roadmap.

Phase 10 deepens lead handling quality and rep control across every tab without a UI overhaul:

- **Blue-collar meta-category** — derived grouping from existing `insurance_class` values; scoring bonus; filter and sort support
- **Owner/contact name** — multi-source extraction (JSON-LD, OSM operator tag, website text heuristics, manual rep entry); confidence-labeled; pinnable via validation system
- **Server-side sorting** — 9 sort modes replacing the current client-side-only sort
- **Server-side filtering** — 13 new filter params across leads and saved leads
- **Grouping** — 7 `group_by` modes; grouped response schema with section headers
- **Today view improvements** — 2 new sections; user-configurable section order
- **Export enhancements** — 6 new columns; grouped CSV export mode

---

## 2. Blue-Collar Meta-Category (10-A)

### 2.1 Definition

Blue-collar is a **derived boolean**, not a new `insurance_class` value. It is computed from existing classification and never shown as a raw insurance class in the UI.

```
is_blue_collar = insurance_class IN (
  'Auto Service',
  'Contractor / Trades',
  'Personal Services'
)
```

These three classes share the properties that matter for insurance targeting: hands-on work, owner-operated, in-person customer interaction, physical risk exposure, and high likelihood of being underinsured or unreviewed in years.

### 2.2 Extended Category Mappings

The following business types currently fall to `Other Commercial` and must be reclassified into blue-collar classes as part of this phase:

| Business type | Correct `insurance_class` | `is_blue_collar` |
|---|---|---|
| Auto detailing | Auto Service | true |
| Auto glass repair | Auto Service | true |
| Towing / roadside | Auto Service | true |
| Welding / fabrication | Contractor / Trades | true |
| Pest control | Contractor / Trades | true |
| Landscaping / lawn care | Contractor / Trades | true |
| Pressure washing | Contractor / Trades | true |
| Painting contractor | Contractor / Trades | true |
| Locksmith | Personal Services | true |
| Cleaning services | Personal Services | true |

These mappings are added to `classification_service.py` keyword tables. Name keyword additions:

```python
# Additional blue-collar name signals
"detail", "tow", "weld", "fabricat", "pest", "lawn", "landscap",
"pressure wash", "paint contractor", "locksmith", "clean"
```

### 2.3 Database Column

```sql
ALTER TABLE business
  ADD COLUMN is_blue_collar BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX idx_business_is_blue_collar ON business (is_blue_collar);

-- Backfill from existing insurance_class
UPDATE business
SET is_blue_collar = TRUE
WHERE insurance_class IN ('Auto Service', 'Contractor / Trades', 'Personal Services');
```

Backfill runs once in migration `0006`. Going forward, `is_blue_collar` is set synchronously in `classification_service.classify()` and on every `ingest_overture.py` upsert.

### 2.4 Classification Service Changes

`classify()` currently returns `(insurance_class: str)`. After this phase it returns:

```python
@dataclass
class ClassificationResult:
    insurance_class: str
    is_blue_collar: bool
```

All callers updated: `ingest_overture.py`, `backfill_classification.py`, and any route/lead retrieval that calls classification inline.

### 2.5 Scoring Bonus

`fit_score` receives a +5 additive bonus when `is_blue_collar = True`. This is applied after the base fit score is computed, before normalization to 0–100 range.

- Does not affect `distance_score` or `actionability_score`
- Does not change v1 vs v2 gating — applies in both paths
- Score explanation label: "Blue collar fit ↑" appended to the fit explanation when the bonus is active
- Regression guardrail: top-20 rank order overlap vs pre-bonus must be ≥ 85% on the 5 Phase 3 validation routes

---

## 3. Owner / Contact Name (10-B)

### 3.1 Motivation

Reps walking into a business cold have a higher conversion rate when they can ask for the owner by name. Even a 50%-confidence name is better than nothing. The system must label confidence clearly so reps do not embarrass themselves with stale or wrong names.

### 3.2 Database Columns

```sql
ALTER TABLE business
  ADD COLUMN owner_name                TEXT,
  ADD COLUMN owner_name_source         TEXT,      -- see enum below
  ADD COLUMN owner_name_confidence     REAL,      -- 0.0–1.0
  ADD COLUMN owner_name_last_checked_at TIMESTAMPTZ;

CREATE INDEX idx_business_owner_name ON business (owner_name)
  WHERE owner_name IS NOT NULL;
```

**`owner_name_source` enum values:**

| Value | Meaning | Confidence |
|---|---|---|
| `manual` | Rep entered directly | 1.0 |
| `website_jsonld` | JSON-LD `Person` or `LocalBusiness.employee` schema | 0.85 |
| `osm_operator` | OSM `operator` tag via Overpass | 0.70 |
| `website_text` | Heuristic text pattern from website crawl | 0.50 |
| `unknown` | Source could not be determined | 0.30 |

### 3.3 Extraction Sources (Priority Order)

**Source 1 — JSON-LD Person schema (confidence 0.85)**

During the Phase 5 website validation fetch, the JSON-LD payload is already being parsed. Extend `validation_service.py` to additionally look for:

```json
{ "@type": "Person", "name": "..." }
{ "@type": "LocalBusiness", "employee": { "@type": "Person", "name": "..." } }
{ "@type": "LocalBusiness", "founder": { "@type": "Person", "name": "..." } }
```

Extract the first `name` found. Strip titles (Mr., Mrs., Dr., etc.) from the stored value. Store as-is including first-name-only results.

**Source 2 — OSM `operator` tag (confidence 0.70)**

The Overpass fetch in `osm_enrichment_service.py` retrieves all tags already. Add `operator` to `_extract_tags()`. The `operator` tag on OSM nodes frequently contains the sole proprietor's name for small businesses (e.g., `"Joe's Auto Repair"` → skip; `"Joe Martinez"` → keep). Apply a heuristic: if `operator` value contains a space, no business keywords (`LLC`, `Inc`, `Co`, `Services`, etc.), and is 3–40 characters, treat as a person name.

**Source 3 — Website text heuristics (confidence 0.50)**

Secondary pass during Phase 5 website crawl (after JSON-LD parse). Scan `<h1>`, `<h2>`, `<h3>`, `<footer>`, and `<meta name="author">` for patterns:

```
"Owner: <Name>"
"Owned by <Name>"
"Founded by <Name>"
"Contact <Name>"
"Meet <Name>"
"<Name>, Owner"
"<Name>, Proprietor"
```

Extract the captured group. Normalize whitespace. Truncate at 60 characters. Reject if the result contains `@`, `http`, or more than 4 words (likely a sentence fragment).

**Source 4 — Manual rep entry (confidence 1.0)**

`PATCH /saved-leads/{id}` gains an `owner_name` field. When a rep sets it:
- Write directly to `business.owner_name`
- Set `owner_name_source = 'manual'`
- Set `owner_name_confidence = 1.0`
- This write is permanent — automated extraction will never overwrite it

### 3.4 Write Rules

These rules govern all automated writes to `owner_name`:

1. **Never overwrite `manual` source** — if `owner_name_source = 'manual'`, skip all automated extraction for this business
2. **Only upgrade confidence** — only write if the new source's confidence > existing `owner_name_confidence` (or `owner_name` is NULL)
3. **Never clear on failure** — if the website fetch fails or returns no name, leave existing `owner_name` untouched
4. **Freshness gate** — skip re-extraction if `owner_name_last_checked_at > now() - 60 days` (unless `force=true`)

### 3.5 Validation Integration

`owner_name` is added as a pinnable field in `lead_field_validation`:

- `field_name = 'owner_name'`
- `state` mirrors confidence: ≥0.80 → `validated`, 0.60–0.79 → `mostly_valid`, 0.40–0.59 → `needs_review`, <0.40 → `low_confidence`
- Displayed in the evidence drawer with source label
- A manually entered owner name is treated as pinned by default — automated runs skip it

### 3.6 API Changes

**Response schema additions** (`GET /leads`, `GET /saved-leads`):
```json
{
  "owner_name": "John Martinez",
  "owner_name_source": "website_jsonld",
  "owner_name_confidence": 0.85
}
```

**New filter params:**
- `has_owner_name=true` — leads where `owner_name IS NOT NULL`

**`PATCH /saved-leads/{id}` body addition:**
```json
{ "owner_name": "John Martinez" }
```
Sets source to `manual`, confidence to `1.0`. Pass `null` to clear a manual entry (and allow automated extraction to resume).

### 3.7 UI Elements

- **Lead card:** owner name displayed below business name when present; confidence chip: `High` (≥0.80), `Medium` (0.50–0.79), `Low` (<0.50) with appropriate color
- **Lead detail:** editable text field labeled "Owner / Contact"; source label in muted text below ("Source: Website · High confidence"); "Re-check" button triggers a fresh JSON-LD pass for that business only
- **Evidence drawer:** `owner_name` row alongside website/phone/address/hours rows; pin control behaves identically

---

## 4. Expanded Server-Side Sorting (10-C)

### 4.1 Current State

Sort is entirely client-side. The backend returns leads in `final_score DESC` order always. The frontend has a `sortBy` state variable (`score` or `business_type`) that re-sorts the already-fetched array. This means pagination is broken for any sort order other than score.

### 4.2 New Query Params

Both `GET /leads` and `GET /saved-leads` accept:

```
?sort_by=<value>&sort_dir=asc|desc
```

**Allowed `sort_by` values:**

| Value | SQL | Default dir | Applies to |
|---|---|---|---|
| `score` | `final_score DESC` | desc | both |
| `blue_collar_score` | `is_blue_collar DESC, final_score DESC` | desc | both |
| `name` | `business.name` | asc | both |
| `distance` | `distance_m` | asc | both |
| `validation_confidence` | `lead_field_validation.overall_confidence NULLS LAST` | desc | both |
| `owner_name` | `business.owner_name NULLS LAST` | asc | both |
| `follow_up_date` | `next_follow_up_at NULLS LAST` | asc | saved only |
| `last_contact` | `last_contact_attempt_at NULLS LAST` | desc | saved only |
| `saved_at` | `saved_lead.created_at` | desc | saved only |

- Unknown `sort_by` value → 422 with message `"Invalid sort_by value. Allowed: score, blue_collar_score, name, distance, ..."`
- `sort_dir` overrides the default direction for any `sort_by` value
- Secondary tiebreaker for all single-column sorts: `business.name ASC`
- `blue_collar_score` is always two-column — `sort_dir` applies to `final_score` only (blue collar flag always sorts DESC first)

### 4.3 Frontend Changes

- Remove client-side sort logic from the leads list and saved list
- Sort controls send params to the API; re-fetch on change
- Preserve selected sort in URL params (enables back-button and share)
- `sort_by=score` is the default (backward-compatible with current behavior)

---

## 5. Expanded Server-Side Filtering (10-D)

All new params are additive (AND). All invalid values return 422 with a descriptive error.

### 5.1 New params — `GET /leads`

| Param | Type | SQL condition |
|---|---|---|
| `blue_collar` | bool | `business.is_blue_collar = :val` |
| `has_owner_name` | bool | `business.owner_name IS [NOT] NULL` |
| `min_validation_confidence` | float 0–1 | `lfv.overall_confidence >= :val OR lfv IS NULL` (when true, require non-null) |
| `validation_state` | enum | `lfv.overall_state = :val` |
| `operating_status` | enum | `business.operating_status = :val` |
| `score_band` | enum: high/medium/low | `final_score >= 70` / `40–69` / `< 40` |

### 5.2 New params — `GET /saved-leads` (in addition to above)

| Param | Type | SQL condition |
|---|---|---|
| `has_notes` | bool | `EXISTS (SELECT 1 FROM note WHERE saved_lead_id = sl.id)` |
| `saved_after` | date | `sl.created_at >= :val` |
| `saved_before` | date | `sl.created_at <= :val` |
| `overdue_only` | bool | `sl.next_follow_up_at < now() AND sl.status NOT IN ('called','visited','not_interested')` |
| `untouched_only` | bool | `sl.last_contact_attempt_at IS NULL` |

### 5.3 Existing params — confirm correct behavior

- `min_score` — already implemented; confirm it coexists with `score_band` (if both provided, the more restrictive wins)
- `has_phone`, `has_website` — already implemented; no change
- `insurance_class[]` — already implemented; ensure multi-value still works with new filters
- `status[]` — already implemented for saved leads; ensure multi-value array syntax works

---

## 6. Grouping (10-E)

### 6.1 Query Param

```
GET /leads?group_by=<value>
GET /saved-leads?group_by=<value>
```

No `group_by` = flat list response (current behavior, fully backward-compatible).

### 6.2 Response Schema

**Grouped:**
```json
{
  "groups": [
    {
      "key": "blue_collar",
      "label": "Blue Collar",
      "count": 12,
      "leads": [ ...lead objects... ]
    },
    {
      "key": "other",
      "label": "Other",
      "count": 34,
      "leads": [ ...lead objects... ]
    }
  ]
}
```

**Flat (no group_by):**
```json
{
  "leads": [ ...lead objects... ]
}
```

### 6.3 Group Modes

| `group_by` | Sections | Section order |
|---|---|---|
| `insurance_class` | One per class | Blue-collar classes first, then by avg fit score desc |
| `blue_collar` | Blue Collar, Other | Fixed |
| `score_band` | High (≥70), Medium (40–69), Low (<40) | High first |
| `validation_state` | Validated, Mostly valid, Needs review, Low confidence, Unchecked | Best first |
| `follow_up_urgency` | Overdue, Due Today, Upcoming, No Date | Most urgent first |
| `contact_status` | Contacted, Saved/Untouched, Not Interested | Active first |
| `owner_name_status` | Has Owner Name, No Owner Name | Has name first |

Rules:
- Empty sections (0 leads) are omitted from the response entirely
- Within each section, `sort_by` and `sort_dir` apply as normal
- `group_by` and `sort_by` can be combined freely
- Unknown `group_by` value → 422

### 6.4 Frontend Behavior

- Section headers rendered between groups with `label` and `count` badge
- Each section is collapsible; collapsed state stored in `localStorage` keyed by `group_by` value
- Collapsed sections show only the header + count, no lead rows
- Default: all sections expanded

---

## 7. Today View Improvements (10-F)

### 7.1 New Sections

**Blue Collar Today:**
- Leads where `is_blue_collar = true` AND (`next_follow_up_at <= now()` OR `next_follow_up_at <= today end`)
- Capped at 5 leads, sorted by `next_follow_up_at ASC`
- Shown only when at least 1 qualifying lead exists

**Has Owner Name:**
- Unsaved leads (not yet in `saved_lead`) from recent routes where `owner_name IS NOT NULL` AND `final_score >= 60`
- Capped at 5 leads, sorted by `final_score DESC`
- Purpose: "ready to approach" — rep has a name, lead is high quality, not yet worked
- Shown only when at least 1 qualifying lead exists

### 7.2 Default Section Order

```
1. Overdue          (existing)
2. Due Today        (existing)
3. Blue Collar Today    (new)
4. High Priority Untouched  (existing)
5. Has Owner Name       (new)
6. Recent Route     (existing)
```

### 7.3 User-Configurable Order

A `user_preferences` table stores section order per user:

```sql
CREATE TABLE user_preferences (
  user_id      TEXT PRIMARY KEY,
  today_section_order  TEXT[],  -- array of section keys in user's preferred order
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`GET /saved-leads/today` reads from `user_preferences` and applies the stored order. Missing sections (new sections added after user set preference) are appended at the end in default order.

`PATCH /user/preferences` endpoint:
```json
{ "today_section_order": ["overdue", "blue_collar_today", "due_today", ...] }
```

Unknown section keys in the stored order are silently ignored (forward-compatible).

### 7.4 Response Schema Extension

`GET /saved-leads/today` gains two new top-level keys:
```json
{
  "overdue": [...],
  "due_today": [...],
  "blue_collar_today": [...],   // new
  "high_priority_untouched": [...],
  "has_owner_name": [...],      // new
  "recent_route": { ... }
}
```

All existing keys are unchanged — backward-compatible. New keys are always present (empty array when no qualifying leads).

---

## 8. Export Enhancements (10-G)

### 8.1 New Columns

Appended to the end of both per-route and cross-route CSV exports. No existing columns are reordered.

| Column header | Value |
|---|---|
| `is_blue_collar` | `TRUE` / `FALSE` |
| `owner_name` | Name string or empty |
| `owner_name_source` | Source enum value or empty |
| `owner_name_confidence` | `"85%"` format or empty |
| `validation_state` | Label string (`Validated`, `Mostly valid`, etc.) or `Unchecked` |
| `operating_status` | `open`, `possibly_closed`, or `unknown` |

`owner_name_confidence` is exported as a percentage string (e.g., `"85%"`) for readability in AMS and Excel, not as a raw float.

### 8.2 Grouped CSV Export

`GET /export/saved-leads.csv?group_by=insurance_class`

Produces a CSV where each group is preceded by a blank row and a header row:

```
,,,,,,
GROUP: Auto Service (12 leads),,,,,,
Joe's Auto,,555-1234,...
```

The header row format: `GROUP: <label> (<count> leads)` in the first column, rest empty.

Only the cross-route export (`/export/saved-leads.csv`) supports `group_by`. The per-route export (`/export/routes/{id}/leads.csv`) always produces a flat list.

All existing `group_by` values from section 6.3 are supported. Unknown value → 422.

---

## 9. Migration Summary (0006)

File: `alembic/versions/0006_blue_collar_and_owner_contact.py`

```sql
-- Up
ALTER TABLE business
  ADD COLUMN is_blue_collar               BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN owner_name                   TEXT,
  ADD COLUMN owner_name_source            TEXT,
  ADD COLUMN owner_name_confidence        REAL,
  ADD COLUMN owner_name_last_checked_at   TIMESTAMPTZ;

CREATE INDEX idx_business_is_blue_collar
  ON business (is_blue_collar);

CREATE INDEX idx_business_owner_name
  ON business (owner_name)
  WHERE owner_name IS NOT NULL;

CREATE TABLE user_preferences (
  user_id               TEXT PRIMARY KEY,
  today_section_order   TEXT[],
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Backfill
UPDATE business
SET is_blue_collar = TRUE
WHERE insurance_class IN ('Auto Service', 'Contractor / Trades', 'Personal Services');

-- Down
DROP TABLE IF EXISTS user_preferences;
DROP INDEX IF EXISTS idx_business_owner_name;
DROP INDEX IF EXISTS idx_business_is_blue_collar;
ALTER TABLE business
  DROP COLUMN IF EXISTS owner_name_last_checked_at,
  DROP COLUMN IF EXISTS owner_name_confidence,
  DROP COLUMN IF EXISTS owner_name_source,
  DROP COLUMN IF EXISTS owner_name,
  DROP COLUMN IF EXISTS is_blue_collar;
```

---

## 10. Test Coverage Plan

### Unit tests (new)

- `test_classification_blue_collar.py`
  - All 10 new category mappings produce correct `insurance_class` and `is_blue_collar = True`
  - Existing classes unchanged
  - `classify()` return type is `ClassificationResult`

- `test_owner_name_extraction.py`
  - JSON-LD Person schema → confidence 0.85
  - JSON-LD no Person → no name written
  - OSM operator tag person-name heuristic: passes (person name), fails (company name with LLC)
  - Website text heuristics: each pattern variant produces expected output
  - Write rules: manual never overwritten, lower confidence not overwritten by lower, NULL cleared by any source

- `test_lead_sorting.py`
  - All 9 `sort_by` values produce correctly ordered results on fixture data
  - Unknown `sort_by` → 422
  - `sort_dir` override works for all values
  - `blue_collar_score` always puts `is_blue_collar=True` rows first regardless of `sort_dir`

- `test_lead_filtering.py`
  - All 13 new filter params individually
  - Three combined filters (AND logic produces correct intersection)
  - Invalid enum value → 422 with descriptive message

- `test_lead_grouping.py`
  - All 7 `group_by` modes produce correct section keys and lead assignment
  - Empty sections absent from response
  - No `group_by` → flat `{"leads": [...]}` response
  - Unknown `group_by` → 422
  - `group_by` + `sort_by` combined: each section is internally sorted correctly

- `test_today_view_sections.py`
  - Blue Collar Today section: present when qualifying leads exist, absent when not
  - Has Owner Name section: present when qualifying unsaved leads exist, absent when not
  - User-configurable order respected from `user_preferences`
  - New sections absent from response when empty (not null — empty array)

- `test_export_columns.py`
  - New columns present in both per-route and cross-route CSV
  - `owner_name_confidence` exported as percentage string
  - Grouped CSV has separator rows in correct positions between groups
  - Per-route export ignores `group_by` param

### Regression checks

- Existing `insurance_class` filter and sort behavior unchanged
- Scoring v1/v2 top-20 rank overlap ≥ 85% vs pre-blue-collar-bonus on Phase 3 test routes
- Export existing columns in same positions (AMS import mapping not broken)
- `GET /saved-leads/today` existing section keys (`overdue`, `due_today`, `high_priority_untouched`, `recent_route`) still present and correct

---

## 11. Exit Criteria

1. `is_blue_collar = TRUE` on ≥ 95% of Auto Service, Contractor / Trades, and Personal Services rows in a test ingestion run (spot-check query)
2. All 10 new category mappings verified against a test fixture with known inputs
3. `owner_name` populated for ≥ 20% of saved leads after one enrichment + validation pass on a staging dataset of ≥ 50 saved leads with websites
4. Manual `owner_name` entry round-trips correctly; confirmed not overwritten by a subsequent automated enrichment run
5. All 9 sort modes produce correctly ordered results on a real dataset (3 test routes, manual inspection)
6. All new filter params work correctly in combination on a real dataset
7. All 7 grouping modes produce valid response schema; empty groups absent
8. Today view Blue Collar Today and Has Owner Name sections appear when qualifying leads exist, absent when they do not
9. Export: all 6 new columns present, `owner_name_confidence` as percentage, grouped export has correct separator rows
10. +5 blue-collar bonus top-20 rank overlap ≥ 85% vs pre-bonus on Phase 3 validation routes
11. All new unit tests pass; full suite remains green (105+ passing baseline)
