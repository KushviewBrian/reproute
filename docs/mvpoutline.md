# RepRoute MVP Outline

## 1) MVP Goal

Build a reliable field prospecting product that independent insurance agents can use weekly to:

1. Generate route-aware leads along their existing drives.
2. Qualify and prioritize them quickly in the field.
3. Track outreach and follow-up without switching tools.
4. Export clean data into downstream workflows.

MVP success is not feature breadth. It is **repeatable field usage with trusted lead quality and clear workflow completion.** An agent should be able to enter a route, glance at the results, and say: "Yes, these look like businesses I would actually stop at."

---

## 2) Target User and Job-To-Be-Done

**Primary user:** Independent or captive field insurance agent prospecting local small commercial businesses.

**Core job:** *"Given today's drive, tell me who to stop at, what's worth my time, and what to do next."*

**Secondary future users:** Agency producers, territory managers, other route-based field sales reps. Not in scope for MVP.

**User context that matters for design decisions:**
- On their phone, between stops, one-handed
- Spotty connectivity in some territories
- Not technical; will not read a manual
- Already has a workflow (even if it's a spreadsheet); MVP must integrate, not replace

---

## 3) MVP Principles

1. **Trust first** — bad data kills adoption. A lead that turns out to be a residence or a closed business poisons the whole list.
2. **Speed second** — route-to-leads must feel instant. Any latency over ~3s needs a visible loading state.
3. **Workflow continuity** — the user can resume where they left off across sessions and devices.
4. **Mobile-first execution** — the entire core flow must work one-handed on a phone in the field.
5. **Offline resilience** — status changes and notes must never be lost due to connectivity.
6. **Progressive disclosure** — show the most important thing first; detail is one tap away, not front and center.

---

## 4) Build Status vs. Feature Target

The table below tracks what is built vs. what still needs to be built for each feature area. Updated April 2026.

| Feature Area | Status |
|---|---|
| Route creation (origin + destination + waypoints + corridor) | Built |
| Lead scoring + ranked list | Built |
| Core filters (score, phone, website, business type) | Built |
| Map/list interoperability | Built |
| Save lead | Built |
| Status pipeline | Built |
| Notes with timestamp | Built |
| CSV export (per-route) | Built |
| PWA setup (manifest + service worker shell) | Built (needs verification) |
| Offline queue for status/notes | Partial — needs reconnect verification |
| Lead validation / reliability indicators | **Not built** |
| Follow-up date tracking + overdue view | **Not built** |
| Today view / daily dashboard | **Not built** |
| CRM-ready export format | **Not built** |
| First-run onboarding | **Not built** |
| Score explanation in UI | Partial — sub-scores exist, display needs work |
| Export all saved leads across routes | **Not built** |

---

## 5) Must-Have MVP Features (Launch Critical)

### 5.1 Lead Discovery Core

- Route creation: origin, destination, optional intermediate stops, corridor width selector.
- Ranked lead list with score + score explanation (see §5.2 for what explanation must contain).
- Core filters: min score, has phone, has website, business type (insurance class).
- Map/list interoperability: selecting a lead in the list highlights its pin on the map; tapping a pin opens the lead detail. Both directions must work.
- Lead detail: business name, address, phone (tap-to-call), website (tap-to-open), score breakdown, validation state (when available).

### 5.2 Score Explanation Requirements

The score explanation must communicate three things to a non-technical field agent in under 5 seconds:

1. **Why this business ranked high** (or low) — e.g., "Strong fit: Auto Service, close to your route."
2. **What data is available** — e.g., "Has phone and website."
3. **Confidence in the data** — e.g., "Website verified" or "Phone format only — not confirmed."

The sub-scores (fit, distance, actionability) exist in the backend. The UI must surface them as plain-language labels, not raw numbers alone.

### 5.3 Lead Quality and Trust

> **Build status: not yet built.** Cross-reference: [leadvalidationplan.md](leadvalidationplan.md) for full spec.

- Lead reliability indicator on each card: `Validated` / `Needs Review` / `Unchecked`.
- Validation checks (Phase 1 of validation plan):
  - Website resolves (HTTP 200–399, stable URL)
  - Phone format plausibility (libphonenumber valid + E.164 normalization)
- Duplicate suppression: near-identical businesses (same name + address within 100m) must not both surface in the same lead list. See §10 for deduplication model.
- Do not mark a business `invalid` solely because a bot-detection system blocked the fetch. Use the `unknown` state in that case.

### 5.4 Sales Workflow Core

> **Build status: status pipeline and notes are built. Follow-up fields are not built.**

- Save lead (idempotent — saving twice does not create duplicates).
- Status pipeline: `saved` → `called` → `visited` → `follow_up` → `not_interested`.
- Notes: free-text, timestamped, supports multiple notes per lead. Outcome and next-action fields optional.
- Follow-up date: `next_follow_up_at` field on saved lead. User can set a date. Overdue leads (past due date, status not resolved) are surfaced prominently.
- Saved view: sortable by follow-up urgency (overdue first, then soonest due, then unsorted).

### 5.5 Today View / Daily Dashboard

> **Build status: not built.**

The Today view is the default landing screen after login. It answers: *"What do I need to do right now?"*

**Contents (in order):**
1. **Overdue follow-ups** — saved leads where `next_follow_up_at < now()` and status is not `visited` or `not_interested`. Show business name, overdue by X days, quick-action buttons.
2. **Due today** — same filter but `next_follow_up_at = today`.
3. **High-priority untouched** — saved leads with score ≥ 70, status = `saved`, no contact attempt. Capped at 5.
4. **Recent route** — last route created, with count of unsaved leads above the score threshold.

**Empty state:** If no follow-ups and no recent route, show a prompt to create a route. Do not show a blank screen.

**Entry point:** Today view is the default tab on app load. Route planning is a second tab. Saved leads is a third tab.

**Sort/filter:** Today view is not filterable — it shows everything due. Filtering happens in the Saved tab.

### 5.6 Data Portability

> **Build status: per-route CSV export is built. CRM format and cross-route export are not built.**

- CSV export: includes business name, address, phone, website, score, status, notes (concatenated), follow-up date, last contact date.
- **CRM-ready preset:** Export a second format mapped for direct import into Agency Management Systems. Minimum target: generic AMS format with columns `first_name`, `last_name` (business name split), `company`, `phone`, `email` (blank), `address`, `city`, `state`, `zip`, `source` (`RepRoute`), `status`, `notes`. This covers most AMS import wizards.
- Cross-route export: export all saved leads across all routes from the Saved tab (not just the current route).

### 5.7 Offline and Sync Reliability

> **Build status: partial. Full offline/reconnect behavior needs verification.**

- Offline queue: note additions made while offline are queued in localStorage (`reproute_offline_note_queue_v1`) and synced automatically on reconnect. **Status changes are not currently queued offline — this is a gap that needs to be built.**
- Sync state indicator: visible indicator when unsynced notes exist. Clears when sync completes.
- Conflict resolution rule: **last write wins by server timestamp.** If the same lead status was changed offline on two devices, the one that syncs last wins. No merge prompt is shown to the user — this edge case is rare enough that complexity is not justified at MVP.
- No data loss guarantee: the note queue is persisted to localStorage, surviving app reload. localStorage is cleared on browser data wipe — acceptable tradeoff for MVP simplicity. Upgrade to IndexedDB if queue size or reliability requirements grow.
- Degraded mode: if the backend is unreachable, the app remains usable for viewing previously loaded leads and adding notes. Route creation requires connectivity.

### 5.8 First-Run Onboarding

> **Build status: not built.**

- On first login (no routes, no saved leads): show a brief onboarding overlay explaining the three-step flow: Plan route → Review leads → Save and track.
- Overlay is dismissible and does not reappear.
- Empty state for lead list (no route yet): prompt to create a route, not a blank panel.
- Empty state for saved tab (nothing saved yet): short explanation of what saving does.
- Score explanation tooltip: on first view of a score badge, a one-time tooltip explains what the number means.

---

## 6) Should-Have Features (Near-Term, Post-Launch)

- Saved filter presets (e.g., "No phone + follow-up due").
- Territory controls: hide already-contacted leads for N days to avoid re-working the same block.
- Route session analytics: viewed / saved / contacted counts per route.
- Corridor polygon overlay on map (showing the actual search area, not just the route line).
- Mini-map inside lead detail drawer.
- Push notifications for due follow-ups (requires PWA notification permission).

---

## 7) Out of Scope for MVP

- Full native iOS/Android apps — PWA is the mobile strategy.
- Team collaboration, shared territories, or role-based org model.
- CRM API writeback (direct sync) — standardized CSV export is sufficient.
- AI-generated outreach content or call scripts.
- Route stop sequence optimization (TSP/VRP) — user orders stops manually.
- Underwriting fit scoring or coverage recommendations.
- Google APIs for routing, geocoding, or place data.

---

## 8) PWA Requirements

The app is built as a PWA from day one. PWA is the mobile strategy — no App Store submission, no separate native build.

**Required for MVP:**
- Installable: web app manifest with name, icons (192px, 512px), `display: standalone`, `start_url`.
- Install prompt: currently shown as a dismissible banner on app load. Target behavior: surface after the first route is created (earn it, not on cold visit). This is a future UX improvement — current behavior is acceptable for MVP.
- iOS install banner: custom banner with instructions (iOS Safari does not auto-prompt).
- Offline caching: service worker caches the app shell (HTML, JS, CSS) so the app loads without a network request. Lead data is not pre-cached — only the shell.
- Offline queue: see §5.7.

**Not required for MVP:**
- Background sync API (use foreground sync on reconnect for simplicity).
- Push notifications (deferred to should-have).

---

## 9) Mobile UX Constraints

"Mobile-first" means these are hard constraints, not aspirations:

| Constraint | Requirement |
|---|---|
| Primary target devices | iPhone SE (375px) through iPhone Pro Max (430px); Android equivalent |
| Minimum touch target size | 44×44px (Apple HIG) for all interactive elements |
| Minimum font size | 14px for body text; 12px absolute minimum for secondary labels |
| One-handed reach zone | Primary actions (save, call, navigate) must be reachable in the bottom 60% of screen |
| No hover-dependent interactions | Nothing critical behind hover — touch only |
| Tap-to-call | Phone numbers are always `<a href="tel:...">` links |
| Map pan/zoom | Must not interfere with scroll on the lead list |
| Landscape support | App must not break in landscape; layout can simplify |

**Testing matrix (minimum before launch):**
- iOS Safari (iPhone SE, iPhone 15)
- Android Chrome (mid-range device)
- Desktop Chrome (1280px wide)

---

## 10) Technical MVP Requirements

### 10.1 Performance Targets

| Operation | Target |
|---|---|
| Route creation + lead retrieval (p95) | < 5s |
| Lead filter/sort interaction (data already loaded) | < 500ms perceived |
| Save/note/status mutation (or queue confirmation) | < 1s |
| Map initial render (50–100 pins) | < 2s on 4G |
| Map pan/zoom responsiveness | 60fps on target devices |

### 10.2 Reliability Targets

- No silent failures on save, note, or status actions — every failure surfaces a user-visible message.
- Retries with exponential backoff for transient upstream failures (ORS, Photon).
- App remains usable in degraded mode when geocoding or routing providers are unavailable (cached results, graceful error states).
- Backend health check (`/health`) monitored with uptime alerting before pilot.

### 10.3 Security

- No secrets in repo or frontend bundles.
- Auth enforced on all lead/user data APIs via Clerk JWT middleware.
- Basic audit trail for note and status changes (timestamps + user ID).
- CORS restricted to known frontend origins only.
- Export size: current backend export cap is 2,000 rows (`fetch_leads(...limit=2000)`). This is the working limit; adjust if query performance degrades under load.

---

## 11) Data Model Additions Needed

The following fields/tables are required for MVP but not yet built. The existing schema (route, business, saved_lead, note) is the baseline.

### 11.1 Validation Fields
Per the [leadvalidationplan.md](leadvalidationplan.md), validation state is stored in a separate table, not flat columns on business:

- Table: `lead_validation_run` (id, business_id, user_id, status, started_at, finished_at)
- Table: `lead_field_validation` (business_id, field_name, state, confidence, evidence_json, last_checked_at, next_check_at, pinned_by_user)

Do **not** add flat columns (`website_ok`, `phone_ok`, `status_confidence`) to the business table — these are incompatible with the validation plan's confidence/evidence model.

### 11.2 Follow-Up Fields
Add to `saved_lead`:
- `next_follow_up_at` (timestamptz, nullable)
- `last_contact_attempt_at` (timestamptz, nullable)

### 11.3 Deduplication Fields
Add to `business` (optional for MVP, required before pilot):
- `canonical_business_id` (uuid, nullable) — points to the authoritative record if this is a duplicate
- `dedupe_group_id` (uuid, nullable) — shared across all records in a duplicate cluster

Deduplication matching logic: same name (fuzzy ≥ 85%) + address within 100m → flag as duplicates. Resolution: keep the record with the most populated fields as canonical.

---

## 12) API Surface Additions Needed

Additions to the existing API (routes, leads, saved-leads, notes, export, geocode):

| Endpoint | Purpose |
|---|---|
| `POST /leads/{id}/validate` | Trigger validation for a business (per validation plan) |
| `GET /leads/{id}/validation` | Read validation state and field confidence |
| `PATCH /saved-leads/{id}` | Already exists; add `next_follow_up_at`, `last_contact_attempt_at` |
| `GET /saved-leads?due_before=...` | Filter saved leads by follow-up due date |
| `GET /saved-leads/today` | Returns today view payload (overdue + due today + untouched high-score) |
| `GET /export/saved-leads.csv` | Cross-route export of all saved leads |

Remove from plan: `POST /saved-leads/reprioritize` — undefined behavior, not needed for MVP.

---

## 13) UX Surfaces Needed

Surfaces that need to be designed and built:

| Surface | Description |
|---|---|
| Today dashboard | Default landing screen; see §5.5 for content spec |
| Follow-up date picker | Date input on saved lead card/detail; shows overdue state |
| Validation badge | Small chip on lead card: `Validated` / `Review` / `Unchecked` |
| Validation evidence drawer | Expandable panel in lead detail showing per-field check results |
| Onboarding overlay | First-run overlay; see §5.8 |
| iOS install banner | Custom "Add to Home Screen" instruction banner |
| Empty states | Route tab (no route yet), Saved tab (nothing saved), Today tab (nothing due) |
| Score explanation tooltip | One-time tooltip on first score badge interaction |

---

## 14) Launch Acceptance Criteria

MVP is launch-ready only when **all** of the following are true:

1. **Full flow completion**: An agent can complete the end-to-end flow in one session without instructions: route → review leads → save → add note → schedule follow-up → export.
2. **Lead quality threshold**: At least 80% of top-10 leads on 5 test routes in the target metro are valid, visitable small commercial businesses. Evaluated by a person familiar with commercial insurance prospecting, using this rubric: physical storefront or office, operating, not residential, not a franchise/chain location with no local decision-making authority.
3. **Offline reliability**: Status changes and notes entered while offline sync correctly after reconnect. Verified by: airplane mode → make changes → reconnect → confirm changes appear on a second device.
4. **Mobile layout**: Core flow (route entry → lead list → lead detail → save → note) has no layout breakage on iOS Safari (iPhone SE) and Android Chrome. No text overflow, no hidden buttons, no tap target collisions.
5. **No silent failures**: Every save, note, status change, and export either succeeds visibly or shows an error. Verified by: force-fail the API and confirm error states appear correctly.
6. **Operational readiness**: Runbook exists for ingestion trigger, quota exhaustion (ORS, Photon, Clerk), and backend outage. Monitoring is active for `/health` with alerting.
7. **Performance evidence**: p95 route creation + lead retrieval ≤ 5s on a real route in the target metro, measured from a mobile device on 4G. Evidence committed to `docs/`.

---

## 15) Delivery Order (Execution Sequence)

Build in this order. Do not start the next layer until the current one passes its acceptance gate.

### Layer 1 — Trust (build first, everything else depends on this)
- Lead validation: website check + phone format check + reliability badge
- Deduplication baseline: suppress exact/near-exact duplicates in lead list
- Score explanation: plain-language labels in lead detail

**Gate:** 80% lead quality threshold (§14.2) passes on 3 test routes.

### Layer 2 — Workflow
- Follow-up date fields on saved lead
- Today view / daily dashboard
- Saved list sorted by follow-up urgency
- Overdue lead visibility

**Gate:** Full flow completion (§14.1) passes end-to-end.

### Layer 3 — Portability
- CRM-ready export format
- Cross-route CSV export from Saved tab

**Gate:** Export opens in target AMS without column mapping errors.

### Layer 4 — Hardening
- Offline queue reconnect verification
- PWA install flow + iOS banner
- First-run onboarding overlay
- Performance measurement + evidence commit
- Mobile QA matrix pass
- Monitoring activation

**Gate:** All §14 launch acceptance criteria pass.

---

## 16) KPIs and Targets

| KPI | Target | Measurement Method |
|---|---|---|
| Route-to-save conversion | ≥ 30% of leads viewed result in a save | `saved_lead` count / `route_candidate` views logged |
| Save-to-contacted conversion | ≥ 50% of saved leads reach `called` or `visited` within 7 days | Status transition timestamps |
| Follow-up completion rate | ≥ 60% of follow-ups marked due are resolved within 3 days of due date | `next_follow_up_at` vs. status update timestamp |
| Weekly active agents (WAU) | ≥ 3 during pilot, growth after | Auth session log |
| Median time: route → first save | < 5 minutes | Route created_at vs. first saved_lead created_at |
| Lead quality score (pilot) | ≥ 80% valid commercial prospects | Manual evaluation per §14.2 rubric |

Baselines should be established in the first 2 weeks of pilot before targets are enforced.

---

## 17) Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Upstream data freshness/accuracy variance | High | High | Selective validation layer ([leadvalidationplan.md](leadvalidationplan.md)); confidence indicators on every lead; periodic ingestion QA |
| ORS rate limit hit under real pilot load | Medium | High | Cache route geometries by origin+destination hash; trigger self-hosted ORS at 70% of monthly quota; runbook committed to docs/ |
| Photon geocoder unavailable or throttled | Medium | Medium | Cloudflare Workers KV cache absorbs most requests; fallback: prompt user to enter full address manually; self-host Photon on contingency VPS |
| Mobile network instability in field | High | Medium | Offline queue (localStorage-backed); degraded mode preserves already-loaded data; sync on reconnect |
| User trust erosion from invalid lead data | High | High | Reliability indicator on every card; `unknown` state is shown, not hidden; validation plan Phase 1 built before pilot |
| Clerk free tier MAU limit hit (50k) | Low | High | Monitor MAU in Clerk dashboard; upgrade plan at 80% utilization; verify current pricing at clerk.com/pricing before budgeting |
| Supabase storage or connection limits | Low | Medium | pgbouncer pooler in use; connection pool capped at 4; monitor DB size monthly |

---

## 18) Definition: Valid Commercial Prospect

Used in §14.2 and §16 lead quality KPI. A lead is a valid commercial prospect if **all** of the following are true:

1. Physical storefront, office, or job site that an agent can visit in person.
2. Currently operating (not permanently closed, not a future opening).
3. Not a residence, home office without signage, or purely online business.
4. Not a franchise location where insurance decisions are made at corporate (e.g., a national chain fast food location). Regional or local franchise operators with local decision authority are acceptable.
5. Business type is within scope for small commercial insurance lines (BOP, commercial auto, workers comp, general liability).

Evaluators apply this rubric by looking up the business on Google Maps Street View + search results. This is a manual QA step, not automated.

---

*MVP success = an agent runs a route, trusts the list, saves leads, and comes back the next week.*
