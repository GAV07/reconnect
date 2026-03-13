# Roadmap: Reconnect

## Milestones

- ✅ **v1.0 Actionable PWA + Rich Email Digests** — Phases 1-3 (shipped 2026-03-09)
- ✅ **v1.1 Network Intelligence** — Phases 4-6 (shipped 2026-03-10)
- 🚧 **v1.2 Intent-Driven Triage** — Phases 7-10 (in progress)

## Phases

<details>
<summary>✅ v1.0 Actionable PWA + Rich Email Digests (Phases 1-3) — SHIPPED 2026-03-09</summary>

- [x] Phase 1: Infrastructure Foundations (2/2 plans) — completed 2026-03-08
- [x] Phase 2: Email Reliability (2/2 plans) — completed 2026-03-09
- [x] Phase 3: PWA Feature Completeness (3/3 plans) — completed 2026-03-09

See: `.planning/milestones/v1.0-ROADMAP.md` for full details.

</details>

<details>
<summary>✅ v1.1 Network Intelligence (Phases 4-6) — SHIPPED 2026-03-10</summary>

- [x] Phase 4: Foundation Fixes + Queue UX (3/3 plans) — completed 2026-03-09
- [x] Phase 5: Dashboard Intelligence (2/2 plans) — completed 2026-03-09
- [x] Phase 6: CLI + Gmail OAuth + Streamlit Removal (2/2 plans) — completed 2026-03-10

See: `.planning/milestones/v1.1-ROADMAP.md` for full details.

</details>

### 🚧 v1.2 Intent-Driven Triage (In Progress)

**Milestone Goal:** Replace score-only queue decisions with a signal system that captures why you'd reach out, drives messaging tone, schedules follow-ups, and learns from triage patterns — while fixing email delivery and enriching sparse profiles.

- [x] **Phase 7: Signal Foundation** - Schema migration, canonical signal service, and cadence definitions (completed 2026-03-12)
- [x] **Phase 8: Email + Signal UI + Profile Content** - Email digest fix, 7-signal queue triage, enriched cards, contact notes, profile fallbacks (completed 2026-03-12)
- [x] **Phase 9: Goals, Sync, and Pipeline Intelligence** - User goals profile, bidirectional sync for new data, cadence re-queuing, signal-informed rescoring (completed 2026-03-12)
- [x] **Phase 10: Draft Tone Adaptation** - Signal-aware AI message generation via Edge Function (completed 2026-03-13)

## Phase Details

### Phase 7: Signal Foundation
**Goal**: The database schema and canonical signal service exist so every subsequent phase has a stable foundation to build on
**Depends on**: Phase 6 (v1.1 complete)
**Requirements**: CAD-01, SIG-03 (schema precondition)
**Success Criteria** (what must be TRUE):
  1. `contact_signals` and `contact_notes` tables exist in both local SQLite and Supabase PostgreSQL with correct columns and anon role grants
  2. New nullable columns on `connections` (latest_signal, cadence_due_at), `outreach_queue` (signal, signal_context, mini_key_factors), and `user_profile` (current_projects, goals_structured) are present in both databases
  3. `signal_service.py` exists with `SIGNAL_ACTIONS` map defining all 7 signals with cadence days, queue status, and priority boost — this is the single source of truth consumed by pipeline and PWA
  4. Existing "skipped" items in `outreach_queue` are backfilled with a default signal intent so the new exclusion logic can read unambiguous triage state
**Plans**: 2 plans
Plans:
- [ ] 07-01-PLAN.md — Models, signal service, and migration SQL
- [ ] 07-02-PLAN.md — Sync integration and comprehensive test suite

### Phase 8: Email + Signal UI + Profile Content
**Goal**: Users can triage contacts via 7 intent signals in the PWA, receive a daily email that directs them to the app, and see meaningful content on every profile regardless of enrichment completeness
**Depends on**: Phase 7
**Requirements**: EMAIL-01, EMAIL-02, EMAIL-03, EMAIL-04, SIG-01, SIG-02, SIG-03, SIG-04, SIG-05, SIG-06, PROF-01, PROF-02, PROF-03, PROF-04, QUX-01, QUX-02
**Success Criteria** (what must be TRUE):
  1. User receives a daily email digest with contact recommendations; digest renders correctly in Gmail on mobile and desktop
  2. Email contains a "Review in App" CTA that deep-links to the PWA queue, and email action vocabulary reflects the signal model (no legacy Reach Out / Snooze buttons)
  3. Queue cards display a 7-signal picker (WARM_LEAD, NURTURE, VALUE_DROP, SYNERGY, RECONNECT, FUTURE_PIVOT, ARCHIVE) replacing the 3-button triage; assigning a signal updates the card badge without removing the card from view
  4. Queue cards show industry chip, first key factor, and last interaction date so users have enough context to choose a signal confidently
  5. User can add and edit free-form notes on any contact; notes appear on queue cards and on the profile page alongside signal history
  6. Profile key factors section shows meaningful content even when enrichment data is sparse; conversation starters are populated from scoring rationale and enrichment fields when activity_log is empty
  7. ARCHIVE signal hides a contact from queue and dashboard while preserving all data; user can filter queue by signal type
**Plans**: 4 plans
Plans:
- [ ] 08-01-PLAN.md — Email digest rebuild + test scaffold + deep link fix
- [ ] 08-02-PLAN.md — Queue signal picker + card context + filter evolution
- [ ] 08-03-PLAN.md — Profile signal history, notes, and content fallbacks
- [ ] 08-04-PLAN.md — Pull sync for signals and notes

### Phase 9: Goals, Sync, and Pipeline Intelligence
**Goal**: User goals inform scoring, signals and notes flow bidirectionally between PWA and pipeline, and cadence re-queuing and signal-informed rescoring run automatically in the daily pipeline
**Depends on**: Phase 8
**Requirements**: PERS-01, PERS-02, PERS-03, PERS-04, CAD-02, CAD-03
**Success Criteria** (what must be TRUE):
  1. User can define current projects and interests in the PWA preferences page; these goals reach the pipeline via pull sync and are included in the LLM scoring prompt, producing more relevant WARM_LEAD identifications
  2. Signals and notes written in the PWA appear in local SQLite on the next sync run; pipeline-computed fields (mini_key_factors, latest_signal cache) appear in the PWA after the next push sync
  3. Contacts with expired cadence automatically re-enter the daily queue using age-based eligibility (signal_assigned_at + cadence_days <= today), not absolute timestamps; ARCHIVE contacts never re-appear
  4. Signal triage patterns adjust scoring dimension weights after at least 25 actions over 14 days, with a ±40% multiplier cap and logged weight history so drift is auditable
**Plans**: 3 plans
Plans:
- [ ] 09-01-PLAN.md — Goals UI + scoring prompt + pull sync
- [ ] 09-02-PLAN.md — Cadence re-queuing in queue generator
- [ ] 09-03-PLAN.md — Signal feedback processor + safety guards + weight history UI

### Phase 10: Draft Tone Adaptation
**Goal**: AI-generated draft messages reflect the intent signal assigned to the contact, producing appropriately toned outreach without any additional user input
**Depends on**: Phase 8
**Requirements**: PERS-05
**Success Criteria** (what must be TRUE):
  1. When generating a draft from a contact with an assigned signal, the Edge Function produces a message with tone appropriate to that signal (e.g., WARM_LEAD produces a direct specific ask; NURTURE produces warm low-pressure copy)
  2. ARCHIVE contacts have the draft button disabled in the PWA — no draft is generated for archived contacts
  3. Draft tone Edge Function deploys successfully and the existing draft flow for contacts without a signal continues to work unchanged
**Plans**: 2 plans
Plans:
- [ ] 10-01-PLAN.md — Edge Function signal-aware prompt branching + ARCHIVE guard
- [ ] 10-02-PLAN.md — PWA signal gate, no-signal nudge, and draft tone badge UI

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure Foundations | v1.0 | 2/2 | Complete | 2026-03-08 |
| 2. Email Reliability | v1.0 | 2/2 | Complete | 2026-03-09 |
| 3. PWA Feature Completeness | v1.0 | 3/3 | Complete | 2026-03-09 |
| 4. Foundation Fixes + Queue UX | v1.1 | 3/3 | Complete | 2026-03-09 |
| 5. Dashboard Intelligence | v1.1 | 2/2 | Complete | 2026-03-09 |
| 6. CLI + Gmail OAuth + Streamlit Removal | v1.1 | 2/2 | Complete | 2026-03-10 |
| 7. Signal Foundation | v1.2 | 2/2 | Complete | 2026-03-12 |
| 8. Email + Signal UI + Profile Content | v1.2 | 4/4 | Complete | 2026-03-12 |
| 9. Goals, Sync, and Pipeline Intelligence | v1.2 | 3/3 | Complete | 2026-03-12 |
| 10. Draft Tone Adaptation | 2/2 | Complete    | 2026-03-13 | - |
