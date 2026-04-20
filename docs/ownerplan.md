# Phase 12 Owner/Contact Reliability + Employee Count Intelligence

## Source Of Truth
This document is the canonical plan for owner/contact reliability and employee-count intelligence execution in Phase 12.  
If this document conflicts with `docs/roadmap.md`, roadmap ordering/governance wins while this file remains field-level implementation source.

Legacy note: `docs/drafts/ownerplan.d` is superseded by this file.

## Goals
- Harden owner/contact quality with provenance, confidence, and explicit lifecycle behavior.
- Add employee count estimate/band as first-class business intelligence fields.
- Preserve manual overrides as global business-level authority while allowing clear-to-null to resume automation.
- Keep UI changes minimal and avoid Phase 11 redesign scope creep.

## Implemented Contracts
- New candidate provenance table: `business_contact_candidate`.
- New canonical business fields:
  - `employee_count_estimate`
  - `employee_count_band`
  - `employee_count_source`
  - `employee_count_confidence`
  - `employee_count_last_checked_at`
- Promotion rules:
  - manual source is highest confidence and blocks automated overwrite.
  - automated promotion requires strictly higher confidence (or empty target).
  - owner writes from non-manual sources require person-name guard.
  - accepted/rejected candidates are both recorded.
- Validation lifecycle:
  - `owner_name` is part of `VALIDATION_FIELDS`.
  - pin/unpin works with existing validation pin endpoint.
- API updates:
  - `PATCH /saved-leads/{id}` supports `owner_name: string | null` clear semantics.
  - `PATCH /saved-leads/{id}` supports manual employee fields.
  - lead/saved-lead/today responses and exports include employee fields.
  - filter support includes `has_employee_count` and `employee_count_band`.

## Reliability Rules
- Manual owner and manual employee values are global business-level overrides.
- Clearing manual values is explicit (`null`) and re-enables automation.
- Website JSON-LD is preferred automated source for owner and employee extraction.
- Website text extraction is lower confidence fallback.
- OSM operator-based owner extraction is guarded and quality-filtered.

## Telemetry + Evidence
- Logging counters/events:
  - `owner_manual_overwrite_blocked`
  - `employee_manual_overwrite_blocked`
  - `owner_promotion` (accepted/rejected)
  - `employee_promotion` (accepted/rejected)
- Daily aggregation script:
  - `backend/scripts/aggregate_contact_metrics.py`
  - writes daily snapshot to `docs/evidence/phase12_contact_metrics_<date>.json`

## Test Focus Checklist
- Person-name guard correctness (accept/reject matrix).
- Employee extraction parsing quality.
- Promotion precedence and manual lock behavior.
- `PATCH /saved-leads/{id}` set/clear semantics.
- Response/export field parity for employee intelligence fields.
- No regression in route->lead->save->note workflows.
