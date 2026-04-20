Architecture Review (Owner/Contact Sourcing)

Key findings (highest impact first):

1. Website owner extraction is implemented but not persisted to `business.owner_name`.
- Extraction happens in `backend/app/services/validation_service.py:349`, but `process_run_by_id` only upserts `website`/`phone` field validations and never calls `_write_owner_name` (`backend/app/services/validation_service.py:523`, `backend/app/services/validation_service.py:527`).
- Net effect: strongest source (`website_jsonld`) is mostly unused for canonical owner name.

2. Owner data is a single global field on `business`, including manual edits.
- Manual owner entry writes directly to shared `Business` record (`backend/app/api/routes/saved_leads.py:430`).
- This can propagate one user’s possibly-wrong manual input to all users.

3. OSM owner extraction quality controls are weak.
- OSM uses first matching element/tag and accepts raw `operator/owner` without person-name filtering (`backend/app/services/osm_enrichment_service.py:35`, `backend/app/services/osm_enrichment_service.py:158`).
- This likely introduces business entity names (“LLC”, chain operators) as “owner”.

4. Manual owner name cannot be cleared via API despite spec intent.
- Code only applies manual write when `owner_name is not None` (`backend/app/api/routes/saved_leads.py:430`).
- Wrong manual values can become sticky.

5. Validation system does not treat owner as a first-class validated field.
- `VALIDATION_FIELDS` only includes website/phone (`backend/app/services/validation_service.py:29`).
- No owner pinning/validation lifecycle, despite Phase 10 spec direction (`docs/phase10_lead_intelligence.md:188`).

6. There are no owner-name-focused tests (extraction precedence, false positives, overwrite rules).
- No owner-name assertions currently exist under `backend/tests`.

Best improvement path (pragmatic):

1. Immediate (highest ROI):
- On successful website validation, if extracted owner exists, call `_write_owner_name(...)` with `website_jsonld`/`website_text`.
- Add a strict `is_probable_person_name()` guard before any non-manual write (reject LLC/Inc/Services, URLs, emails, long phrases, numeric-heavy strings).
- Improve OSM selection: score candidates by name similarity + distance, then evaluate operator text quality before accepting.

2. Data-model upgrade (reliability):
- Add `business_contact_candidate` table (source, value, role, confidence, evidence, observed_at, promoted_at).
- Promote to `business.owner_name` only when threshold/consensus is met; keep manual as hard override.
- Keep source provenance and conflict history instead of only one final field.

3. User-control and safety:
- Support `owner_name: null` to clear manual override and resume automated sourcing.
- Add owner-level pin/unpin semantics explicitly (separate from website/phone validation fields).

4. Measurement (required to improve reliably):
- Track: owner coverage %, source mix, overwrite rate, manual correction rate, and sampled precision by source.
- Use those metrics to retune confidence weights and source precedence.
